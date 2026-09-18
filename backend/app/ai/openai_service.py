import time
import json
import logging
import math
import hashlib
import re
from typing import List, Dict, Any, Optional, Type
from pydantic import BaseModel
from app.core.config import settings
from app.models.models import AIUsage
from app.core.text_matcher import extract_query_terms, count_term_matches

logger = logging.getLogger(__name__)

# Pricing per 1M tokens in USD
PRICING = {
    "gpt-4o-mini": {"input": 0.150 / 1_000_000, "output": 0.600 / 1_000_000},
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "text-embedding-3-small": {"input": 0.020 / 1_000_000, "output": 0.0},
}

def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = PRICING.get(model, PRICING["gpt-4o-mini"])
    return (input_tokens * rates["input"]) + (output_tokens * rates["output"])

def generate_mock_embedding(text: str, dim: int = 1536) -> List[float]:
    """Generates a deterministic pseudo-embedding vector based on text hash for tests/dev."""
    vec = []
    # Seed with SHA256 of text
    h = hashlib.sha256(text.encode("utf-8")).digest()
    for i in range(dim):
        byte_val = h[i % len(h)]
        val = math.sin((i + 1) * (byte_val + 1))
        vec.append(val)
    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / norm for x in vec]


class AIService:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.client = None
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI client: {e}")

    def log_usage(
        self,
        db,
        feature: str,
        model: str,
        latency_ms: int,
        input_tokens: int,
        output_tokens: int,
        success: bool,
        error_message: Optional[str] = None,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        retrieval_scores: Optional[List[float]] = None,
    ):
        """Records an AI interaction to the ai_usage table for observability."""
        if not db:
            return
        try:
            cost = compute_cost(model, input_tokens, output_tokens)
            usage = AIUsage(
                user_id=user_id,
                project_id=project_id,
                feature=feature,
                model=model,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=cost,
                success=success,
                error_message=error_message,
                retrieval_scores=retrieval_scores,
            )
            db.add(usage)
            db.commit()
        except Exception as e:
            logger.error(f"Failed to record AI usage log: {e}")

    def get_embedding(
        self,
        text: str,
        db=None,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> List[float]:
        """Generates 1536-dim vector embedding using text-embedding-3-small or mock."""
        start_time = time.perf_counter()
        model = settings.OPENAI_EMBEDDING_MODEL

        if not self.client:
            # Deterministic mock embedding for dev/testing without active API key
            latency = int((time.perf_counter() - start_time) * 1000)
            est_tokens = max(1, len(text) // 4)
            self.log_usage(db, "embeddings", model, latency, est_tokens, 0, True, user_id=user_id, project_id=project_id)
            return generate_mock_embedding(text)

        try:
            response = self.client.embeddings.create(
                model=model,
                input=text,
            )
            latency = int((time.perf_counter() - start_time) * 1000)
            tokens = response.usage.prompt_tokens if hasattr(response, "usage") else len(text) // 4
            self.log_usage(db, "embeddings", model, latency, tokens, 0, True, user_id=user_id, project_id=project_id)
            return response.data[0].embedding
        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            self.log_usage(db, "embeddings", model, latency, len(text) // 4, 0, False, str(e), user_id=user_id, project_id=project_id)
            logger.warning(f"OpenAI embedding call failed, falling back to deterministic mock: {e}")
            return generate_mock_embedding(text)

    def generate_chat(
        self,
        system_prompt: str,
        messages: List[Dict[str, str]],
        db=None,
        feature: str = "tutor",
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        retrieval_scores: Optional[List[float]] = None,
    ) -> str:
        """Generates chat completion with observability tracking."""
        start_time = time.perf_counter()
        model = settings.OPENAI_MODEL

        if not self.client:
            latency = int((time.perf_counter() - start_time) * 1000)
            reply = self._mock_chat_response(system_prompt, messages)
            self.log_usage(db, feature, model, latency, 150, 80, True, user_id=user_id, project_id=project_id, retrieval_scores=retrieval_scores)
            return reply

        try:
            full_messages = [{"role": "system", "content": system_prompt}] + messages
            response = self.client.chat.completions.create(
                model=model,
                messages=full_messages,
                temperature=0.2,
            )
            latency = int((time.perf_counter() - start_time) * 1000)
            in_tok = response.usage.prompt_tokens if hasattr(response, "usage") else 100
            out_tok = response.usage.completion_tokens if hasattr(response, "usage") else 50
            self.log_usage(db, feature, model, latency, in_tok, out_tok, True, user_id=user_id, project_id=project_id, retrieval_scores=retrieval_scores)
            return response.choices[0].message.content or ""
        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            self.log_usage(db, feature, model, latency, 100, 0, False, str(e), user_id=user_id, project_id=project_id, retrieval_scores=retrieval_scores)
            logger.error(f"OpenAI chat completion error: {e}")
            raise e

    def _mock_chat_response(self, system_prompt: str, messages: List[Dict[str, str]]) -> str:
        """Generic evidence-grounded chat response covering all substantive parts of the user query."""
        canonical_unsupported = "I couldn't find enough information about that in the current Project materials to answer reliably."
        last_msg = messages[-1]["content"].strip() if messages else ""
        if not last_msg:
            return canonical_unsupported

        # Extract evidence section from system prompt
        evidence_section = ""
        if "--- PROJECT MATERIALS EVIDENCE ---" in system_prompt:
            parts = system_prompt.split("--- PROJECT MATERIALS EVIDENCE ---")
            if len(parts) > 1:
                evidence_section = parts[1].split("----------------------------------")[0].strip()

        if not evidence_section or evidence_section == "NO EVIDENCE AVAILABLE.":
            return canonical_unsupported

        # Parse source blocks: [Source <N>: <title> | Page: <page>] \n <snippet>
        chunk_pattern = re.compile(
            r"\[Source\s*\d+:\s*(.*?)\s*\|\s*Page:\s*(\d+)\]\s*\n(.*?)(?=(?:\n\n\[Source|\Z))",
            re.DOTALL
        )
        found_chunks = chunk_pattern.findall(evidence_section)
        if not found_chunks:
            return canonical_unsupported

        # 1. Split query into subquestions / concept parts generically
        raw_clauses = [
            c.strip() for c in re.split(
                r"\?+|;|\n|\band\b|\bas well as\b|\balso\b|,\s*and\s+|,",
                last_msg,
                flags=re.IGNORECASE
            ) if c.strip()
        ]

        sub_parts = []
        for clause in raw_clauses:
            clause_terms = extract_query_terms(clause)
            if clause_terms:
                sub_parts.append({"clause": clause, "terms": clause_terms})

        # Fallback if no structured clauses found
        if not sub_parts:
            all_terms = extract_query_terms(last_msg)
            if not all_terms:
                return canonical_unsupported
            sub_parts = [{"clause": last_msg, "terms": all_terms}]

        # 2. For each sub-part, match against retrieved evidence chunks
        matched_chunks_by_part = []
        unsupported_parts = []
        used_chunk_indices = []
        chosen_chunks = []

        for part in sub_parts:
            terms = part["terms"]
            best_chunk_idx = None
            best_score = 0

            for idx, (mat_title, page_num, content) in enumerate(found_chunks):
                combined = f"{mat_title}\n{content}"
                matches = count_term_matches(terms, combined)
                if matches > best_score:
                    best_score = matches
                    best_chunk_idx = idx

            if best_chunk_idx is not None and best_score > 0:
                matched_chunks_by_part.append((part, found_chunks[best_chunk_idx]))
                if best_chunk_idx not in used_chunk_indices:
                    used_chunk_indices.append(best_chunk_idx)
                    chosen_chunks.append(found_chunks[best_chunk_idx])
            else:
                unsupported_parts.append(part["clause"])

        # 3. If no parts are supported by evidence, trigger canonical unsupported reply
        if not chosen_chunks:
            return canonical_unsupported

        # 4. Synthesize substantive explanation covering all supported parts
        explanations = []
        seen_texts = set()
        for mat_title, page_num, content in chosen_chunks:
            c_clean = content.strip()
            if c_clean not in seen_texts:
                seen_texts.add(c_clean)
                explanations.append(c_clean)

        body_text = "\n\n".join(explanations)

        # 5. If some parts were unsupported in a multi-part query, explicitly declare them
        unsupported_notice = ""
        if unsupported_parts:
            part_str = ", ".join(f"'{p}'" for p in unsupported_parts)
            unsupported_notice = (
                f"\n\nNote: I couldn't find enough information in the current Project materials "
                f"regarding {part_str} to answer that part reliably."
            )

        # 6. Format clean citations from the chosen chunks
        citation_lines = []
        seen_citations = set()
        for mat_title, page_num, _ in chosen_chunks:
            clean_title = mat_title.replace("svgSource:", "").replace("Source:", "").strip()
            cit = f"Source: {clean_title} — Page {page_num}"
            if cit not in seen_citations:
                seen_citations.add(cit)
                citation_lines.append(cit)

        citation_block = "\n".join(citation_lines)

        reply = (
            f"Based on your Project materials:\n\n"
            f"{body_text}"
            f"{unsupported_notice}\n\n"
            f"{citation_block}"
        )
        return reply.replace("svgSource:", "Source:")

    def generate_structured(
        self,
        system_prompt: str,
        user_prompt: str,
        response_schema: Type[BaseModel],
        db=None,
        feature: str = "structured_generation",
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> BaseModel:
        """Generates structured JSON output validated against a Pydantic schema."""
        start_time = time.perf_counter()
        model = settings.OPENAI_MODEL

        if not self.client:
            latency = int((time.perf_counter() - start_time) * 1000)
            # Return appropriate mock structured instance
            mock_inst = self._mock_structured_data(response_schema, system_prompt=system_prompt, user_prompt=user_prompt)
            self.log_usage(db, feature, model, latency, 200, 150, True, user_id=user_id, project_id=project_id)
            return mock_inst

        try:
            schema_json = json.dumps(response_schema.model_json_schema())
            prompt_with_schema = (
                f"{user_prompt}\n\n"
                f"You MUST respond ONLY with a valid JSON object matching this schema:\n"
                f"{schema_json}"
            )
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_with_schema},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
            latency = int((time.perf_counter() - start_time) * 1000)
            in_tok = response.usage.prompt_tokens if hasattr(response, "usage") else 200
            out_tok = response.usage.completion_tokens if hasattr(response, "usage") else 100
            content = response.choices[0].message.content or "{}"
            parsed_json = json.loads(content)
            validated = response_schema.model_validate(parsed_json)
            self.log_usage(db, feature, model, latency, in_tok, out_tok, True, user_id=user_id, project_id=project_id)
            return validated
        except Exception as e:
            latency = int((time.perf_counter() - start_time) * 1000)
            self.log_usage(db, feature, model, latency, 200, 0, False, str(e), user_id=user_id, project_id=project_id)
            logger.warning(f"OpenAI structured call failed or invalid, falling back: {e}")
            return self._mock_structured_data(response_schema, system_prompt=system_prompt, user_prompt=user_prompt)

    def _mock_structured_data(
        self,
        response_schema: Type[BaseModel],
        system_prompt: str = "",
        user_prompt: str = "",
    ) -> BaseModel:
        """Provides deterministic schema-compliant mock objects for dev/testing."""
        name = response_schema.__name__
        if "OpenEndedEvaluation" in name:
            from app.schemas.schemas import OpenEndedEvaluation

            user_ans = ""
            ans_match = re.search(r"Learner's Submitted Answer:\s*[\"']?(.*?)[\"']?$", user_prompt, re.DOTALL | re.IGNORECASE)
            if ans_match:
                user_ans = ans_match.group(1).strip()
            elif user_prompt:
                user_ans = user_prompt.strip()

            cleaned = user_ans.lower()
            cleaned_alpha = re.sub(r"[^\w\s]", "", cleaned).strip()

            non_answer_patterns = [
                r"^(i\s+)?(do\s+not|don'?t|dont)\s+know\b",
                r"^(i\s+)?(have\s+)?no\s+(idea|clue|answer|info|information)\b",
                r"^(i\s+)?(am\s+|m\s+)?not\s+sure\b",
                r"^(i\s+)?(can'?t|cannot|cant)\s+answer\b",
                r"^idk\b",
                r"^dunno\b",
                r"^(skip|pass|none|nothing|na|n\s*/\s*a)\b",
                r"^(i\s+)?(forgot|don'?t\s+remember|dont\s+remember)\b",
                r"^(no\s+concept|not\s+learned|no\s+clue)\b",
                r"^leave\s+blank\b",
                r"^unclear\b",
                r"^who\s+knows\b",
            ]
            is_non = (
                not cleaned_alpha
                or len(cleaned_alpha) <= 3
                or any(re.search(p, cleaned) for p in non_answer_patterns)
            )

            if is_non:
                return OpenEndedEvaluation(
                    score=0.0,
                    what_you_understood=[],
                    concepts_covered=[],
                    missing_concepts=["Core concept principles and mechanics"],
                    feedback="No substantive answer or explanation was provided. To receive credit, address the key requirements and mechanics requested in the question.",
                    suggested_action="Review the study materials for this topic and attempt the explanation again.",
                    reasoning_quality="poor",
                    confidence=0.95,
                )

            # Evaluate conceptual overlap with reference answer / rubric in system_prompt
            prompt_lower = (system_prompt + " " + user_prompt).lower()
            stopwords = {
                "what", "is", "are", "why", "used", "the", "a", "an", "and", "or", "in", "to",
                "for", "of", "with", "how", "learner", "submitted", "answer", "question",
                "reference", "rubric", "must", "address", "explain", "concepts", "covered"
            }
            ref_words = [w for w in re.findall(r"\b[a-zA-Z0-9_\-\+]+\b", prompt_lower) if len(w) >= 4 and w not in stopwords]
            
            user_words = set(re.findall(r"\b[a-zA-Z0-9_\-\+]+\b", cleaned))
            overlap = [w for w in user_words if w in ref_words]

            if len(overlap) >= 2 or len(cleaned.split()) >= 10:
                return OpenEndedEvaluation(
                    score=85.0,
                    what_you_understood=[
                        "Accurately explained the core principles and operational mechanics",
                        "Demonstrated clear conceptual reasoning aligned with the reference material",
                    ],
                    concepts_covered=["Core Definition", "Functional Mechanics"],
                    missing_concepts=["Edge case handling", "Performance trade-offs"],
                    feedback="Strong conceptual explanation demonstrating solid understanding.",
                    suggested_action="Explore advanced edge cases and trade-offs to further master this topic.",
                    reasoning_quality="good",
                    confidence=0.90,
                )
            elif len(overlap) >= 1 or len(cleaned.split()) >= 5:
                return OpenEndedEvaluation(
                    score=45.0,
                    what_you_understood=["Mentioned relevant concept terminology"],
                    concepts_covered=["Introductory concepts"],
                    missing_concepts=["Detailed operational mechanism", "Practical trade-offs"],
                    feedback="Partial understanding demonstrated. Provide more detail on the operational mechanics.",
                    suggested_action="Review the related sections in your course notes to elaborate on the mechanism.",
                    reasoning_quality="fair",
                    confidence=0.80,
                )
            else:
                return OpenEndedEvaluation(
                    score=15.0,
                    what_you_understood=[],
                    concepts_covered=[],
                    missing_concepts=["Core definition", "Underlying mechanics"],
                    feedback="The submitted response does not adequately address the question or rubric criteria.",
                    suggested_action="Carefully review the course materials before attempting this question.",
                    reasoning_quality="poor",
                    confidence=0.85,
                )

        # Default fallback: try default instantiation
        try:
            return response_schema()
        except Exception:
            # Construct minimal mock fields
            mock_dict = {}
            for field_name, field_info in response_schema.model_fields.items():
                if field_info.annotation in (int, float):
                    mock_dict[field_name] = 0
                elif field_info.annotation is str:
                    mock_dict[field_name] = "Sample"
                elif field_info.annotation is bool:
                    mock_dict[field_name] = True
                elif getattr(field_info.annotation, "__origin__", None) is list:
                    mock_dict[field_name] = []
                else:
                    mock_dict[field_name] = None
            return response_schema.model_validate(mock_dict)


ai_service = AIService()
