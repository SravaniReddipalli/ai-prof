import logging
import json
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from pydantic import BaseModel
from app.core.config import settings
from app.models.models import (
    Concept, ConceptMastery, MasteryHistory, Quiz, QuizQuestion, 
    QuizAttempt, Recommendation, LearningEvent, Project, DocumentChunk
)
from app.ai.openai_service import ai_service
from app.schemas.schemas import (
    QuizResponse, QuizQuestionResponse, QuizAttemptResponse, 
    QuestionResultItem, OpenEndedEvaluation, MasterySummaryResponse,
    ConceptMasteryItem, GrowthItem, RecommendationResponse
)

logger = logging.getLogger(__name__)

def is_non_answer(text: Optional[str]) -> bool:
    """Robustly checks if a submitted open-ended response is empty, trivial, or an explicit non-answer."""
    if not text:
        return True
    cleaned = text.strip().lower()
    if not cleaned:
        return True
    cleaned_alpha = re.sub(r"[^\w\s]", "", cleaned).strip()
    if not cleaned_alpha:
        return True
    if len(cleaned_alpha) <= 3:
        return True

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
    return any(re.search(p, cleaned) for p in non_answer_patterns)

class GeneratedQuizPayload(BaseModel):
    title: str
    difficulty: str
    questions: List[Dict[str, Any]]

class LearningService:
    @staticmethod
    def get_or_create_masteries(project_id: str, user_id: str, db) -> List[ConceptMastery]:
        """Ensures every concept in the project has a ConceptMastery row for the user."""
        concepts = db.query(Concept).filter(Concept.project_id == project_id).all()
        masteries = []
        for c in concepts:
            cm = db.query(ConceptMastery).filter(
                ConceptMastery.concept_id == c.id,
                ConceptMastery.user_id == user_id,
            ).first()
            if not cm:
                cm = ConceptMastery(
                    concept_id=c.id,
                    project_id=project_id,
                    user_id=user_id,
                    score=50.0,  # Default neutral baseline
                    status="attention",
                    assessment_count=0,
                    mistake_count=0,
                )
                db.add(cm)
                db.commit()
                db.refresh(cm)
            masteries.append(cm)
        return masteries

    @staticmethod
    def select_adaptive_concepts(project_id: str, user_id: str, db, limit: int = 3) -> List[Tuple[Any, str, float]]:
        """
        Deterministic adaptive heuristic to select concepts most needing practice.
        Priority = (100 - mastery) * 0.5 + (mistake_count * 20) * 0.3 + (recency) * 0.2
        """
        masteries = LearningService.get_or_create_masteries(project_id, user_id, db)
        if not masteries:
            # If no concepts extracted yet, create a default concept from project
            project = db.query(Project).filter(Project.id == project_id).first()
            proj_name = project.name if project else "General Fundamentals"
            default_c = Concept(project_id=project_id, name=f"{proj_name} Core", description="Primary course material")
            db.add(default_c)
            db.commit()
            db.refresh(default_c)
            masteries = LearningService.get_or_create_masteries(project_id, user_id, db)

        scored = []
        for m in masteries:
            c = db.query(Concept).filter(Concept.id == m.concept_id).first()
            # Deterministic Priority score
            p_score = (100.0 - m.score) * 0.5 + (min(m.mistake_count, 5) * 20.0) * 0.3
            # Difficulty mapping
            if m.score < 40.0:
                diff = "easy"
            elif m.score <= 70.0:
                diff = "medium"
            else:
                diff = "hard"
            scored.append((c, diff, p_score))

        # Sort highest priority first
        scored.sort(key=lambda x: x[2], reverse=True)
        return scored[:limit]

    @staticmethod
    def generate_adaptive_quiz(project_id: str, user_id: str, db) -> QuizResponse:
        """Generates an adaptive quiz (3 MCQs + 1 Open-ended) targeting learner weaknesses."""
        adaptive_selection = LearningService.select_adaptive_concepts(project_id, user_id, db, limit=3)
        concept_names = [c[0].name for c in adaptive_selection]
        primary_diff = adaptive_selection[0][1] if adaptive_selection else "medium"

        # Fetch representative chunks from project
        chunks = db.query(DocumentChunk).filter(DocumentChunk.project_id == project_id).limit(4).all()
        context_snippets = "\n".join(c.content[:300] for c in chunks) if chunks else "General study material"

        system_prompt = (
            "You are an expert assessment generator. Create an adaptive study quiz containing exactly 4 questions: "
            "3 multiple-choice questions (type: 'mcq') and 1 open-ended conceptual question (type: 'open_ended').\n"
            f"Target Concepts: {', '.join(concept_names)}\n"
            f"Difficulty Level: {primary_diff}\n\n"
            "Requirements:\n"
            "- For MCQ: provide 4 distinct options, specify correct_answer matching one of the options, and a clear explanation.\n"
            "- For Open-Ended: correct_answer should be an exemplary answer, rubric should outline what key elements are required.\n"
            "- Format as valid JSON matching schema with fields: title, difficulty, questions list."
        )

        user_prompt = f"Study Material Context:\n{context_snippets}\nGenerate the 4 quiz questions now."

        # Generate via structured AI service or deterministic fallback
        quiz_payload = ai_service.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_schema=GeneratedQuizPayload,
            db=db,
            feature="quiz_generation",
            user_id=user_id,
            project_id=project_id,
        )

        quiz_title = quiz_payload.title or f"Adaptive Quiz: {', '.join(concept_names[:2])}"
        new_quiz = Quiz(
            project_id=project_id,
            user_id=user_id,
            title=quiz_title,
            difficulty=primary_diff,
        )
        db.add(new_quiz)
        db.commit()
        db.refresh(new_quiz)

        created_questions = []
        raw_questions = quiz_payload.questions if quiz_payload.questions else []
        
        # Fallback if empty
        if not raw_questions:
            raw_questions = [
                {
                    "type": "mcq",
                    "question": f"What is the primary role of {concept_names[0] if concept_names else 'this concept'}?",
                    "options": ["To ensure consistency and structure", "To increase redundant storage", "To bypass memory limits", "None of the above"],
                    "correct_answer": "To ensure consistency and structure",
                    "explanation": "Proper structure and normalization prevent redundancy and enforce integrity.",
                    "difficulty": primary_diff,
                },
                {
                    "type": "mcq",
                    "question": "Which trade-off is typically associated with high concurrency?",
                    "options": ["Increased contention and lock overhead", "Zero CPU usage", "Automatic memory expansion", "Infinite throughput"],
                    "correct_answer": "Increased contention and lock overhead",
                    "explanation": "High concurrency often involves locking and isolation overhead.",
                    "difficulty": primary_diff,
                },
                {
                    "type": "mcq",
                    "question": "How do index structures optimize retrieval performance?",
                    "options": ["By reducing the number of disk I/O reads", "By deleting unused records", "By preventing table updates", "By encrypting database pages"],
                    "correct_answer": "By reducing the number of disk I/O reads",
                    "explanation": "Indexes like B-Trees allow logarithmic search times instead of full table scans.",
                    "difficulty": primary_diff,
                },
                {
                    "type": "open_ended",
                    "question": f"Explain in your own words how {concept_names[0] if concept_names else 'this system'} functions and what problems it solves.",
                    "correct_answer": "Comprehensive explanation covering definition, mechanics, and practical benefits.",
                    "rubric": "Learner must address: definition, operational mechanism, and real-world benefit.",
                    "difficulty": primary_diff,
                }
            ]

        # Associate with concept
        primary_concept_id = adaptive_selection[0][0].id if adaptive_selection else None

        for q in raw_questions:
            q_rec = QuizQuestion(
                quiz_id=new_quiz.id,
                concept_id=primary_concept_id,
                type=q.get("type", "mcq"),
                question=q.get("question", "Question"),
                options=q.get("options"),
                correct_answer=q.get("correct_answer"),
                rubric=q.get("rubric", ""),
                explanation=q.get("explanation", ""),
                difficulty=q.get("difficulty", primary_diff),
            )
            db.add(q_rec)
            db.commit()
            db.refresh(q_rec)
            created_questions.append(
                QuizQuestionResponse(
                    id=q_rec.id,
                    concept_id=q_rec.concept_id,
                    type=q_rec.type,
                    question=q_rec.question,
                    options=q_rec.options,
                    difficulty=q_rec.difficulty,
                )
            )

        # Log quiz started event
        event = LearningEvent(
            user_id=user_id,
            project_id=project_id,
            event_type="QUIZ_STARTED",
            payload={"quiz_id": new_quiz.id, "title": new_quiz.title, "difficulty": new_quiz.difficulty},
        )
        db.add(event)
        db.commit()

        return QuizResponse(
            id=new_quiz.id,
            project_id=new_quiz.project_id,
            title=new_quiz.title,
            difficulty=new_quiz.difficulty,
            questions=created_questions,
            created_at=new_quiz.created_at,
        )

    @staticmethod
    def evaluate_quiz_submission(
        quiz_id: str,
        user_id: str,
        submissions: List[Dict[str, str]],
        db,
    ) -> QuizAttemptResponse:
        """Evaluates MCQ and Open-ended questions, computes scores, and updates mastery."""
        quiz = db.query(Quiz).filter(Quiz.id == quiz_id).first()
        if not quiz:
            raise ValueError("Quiz not found")

        project_id = quiz.project_id
        questions = db.query(QuizQuestion).filter(QuizQuestion.quiz_id == quiz_id).all()
        sub_map = {s["question_id"]: s["answer"] for s in submissions}

        total_score = 0.0
        results: List[QuestionResultItem] = []
        concepts_tested = set()
        mistakes_made = 0
        concept_mistakes: Dict[str, int] = {}

        for q in questions:
            user_ans = sub_map.get(q.id, "").strip()
            if q.concept_id:
                concepts_tested.add(q.concept_id)
                if q.concept_id not in concept_mistakes:
                    concept_mistakes[q.concept_id] = 0

            is_mistake = False
            if q.type == "mcq":
                is_correct = (user_ans.lower() == (q.correct_answer or "").strip().lower())
                q_score = 100.0 if is_correct else 0.0
                if not is_correct:
                    mistakes_made += 1
                    is_mistake = True

                total_score += q_score
                results.append(QuestionResultItem(
                    question_id=q.id,
                    question=q.question,
                    type=q.type,
                    user_answer=user_ans,
                    correct_answer=q.correct_answer,
                    is_correct=is_correct,
                    explanation=q.explanation,
                    evaluation=None,
                ))
            else:
                # Open-ended question evaluation via structured AI output or non-answer guard
                if is_non_answer(user_ans):
                    concept_name = ""
                    if q.concept_id:
                        c_obj = db.query(Concept).filter(Concept.id == q.concept_id).first()
                        if c_obj:
                            concept_name = c_obj.name

                    open_eval = OpenEndedEvaluation(
                        score=0.0,
                        what_you_understood=[],
                        concepts_covered=[],
                        missing_concepts=[concept_name] if concept_name else ["Core concept principles and mechanics"],
                        feedback="No substantive answer or explanation was provided. To earn credit, address the key requirements and mechanics requested in the question.",
                        suggested_action=f"Review the study materials for {concept_name or 'this topic'} and attempt the explanation again.",
                        reasoning_quality="poor",
                        confidence=0.95,
                    )
                    ai_service.log_usage(
                        db=db,
                        feature="assessment_evaluation",
                        model=settings.OPENAI_MODEL,
                        latency_ms=10,
                        input_tokens=max(1, len(user_ans) // 4 + 40),
                        output_tokens=30,
                        success=True,
                        user_id=user_id,
                        project_id=project_id,
                    )
                else:
                    eval_system_prompt = (
                        "You are a rigorous educational evaluator. Grade the learner's answer against the target concept, reference answer, and rubric.\n"
                        f"Question: {q.question}\n"
                        f"Reference Answer: {q.correct_answer}\n"
                        f"Grading Rubric: {q.rubric}\n\n"
                        "CRITICAL EVALUATION RULES:\n"
                        "1. Grade the ACTUAL submitted answer strictly against the Question, Reference Answer, and Rubric.\n"
                        "2. If the learner's answer fails to demonstrate conceptual understanding, is evasive, or irrelevant, award a low score (< 30, or 0 if completely unaddressed).\n"
                        "3. In 'what_you_understood', ONLY list concepts or facts that the learner's submitted answer explicitly and accurately demonstrated. If the answer demonstrates no understanding or is incorrect, 'what_you_understood' MUST be an empty list [].\n"
                        "4. In 'concepts_covered', ONLY list concepts accurately addressed in the answer. If none, return [].\n"
                        "5. 'missing_concepts' must list the required concepts from the rubric/question that were absent or incorrect.\n"
                        "6. Return valid JSON matching the OpenEndedEvaluation schema with: score (0-100), what_you_understood, concepts_covered, missing_concepts, feedback, suggested_action, reasoning_quality, confidence."
                    )
                    open_eval = ai_service.generate_structured(
                        system_prompt=eval_system_prompt,
                        user_prompt=f"Learner's Submitted Answer:\n\"{user_ans}\"",
                        response_schema=OpenEndedEvaluation,
                        db=db,
                        feature="assessment_evaluation",
                        user_id=user_id,
                        project_id=project_id,
                    )
                total_score += open_eval.score
                if open_eval.score < 60.0:
                    mistakes_made += 1
                    is_mistake = True

                results.append(QuestionResultItem(
                    question_id=q.id,
                    question=q.question,
                    type=q.type,
                    user_answer=user_ans,
                    correct_answer=q.correct_answer,
                    is_correct=open_eval.score >= 70.0,
                    explanation=open_eval.feedback,
                    evaluation=open_eval,
                ))

            if is_mistake and q.concept_id:
                concept_mistakes[q.concept_id] = concept_mistakes.get(q.concept_id, 0) + 1

        # Attribute any unassigned mistakes across tested concepts
        attributed_mistakes = sum(concept_mistakes.values())
        unattributed = mistakes_made - attributed_mistakes
        if unattributed > 0 and concepts_tested:
            for cid in concepts_tested:
                concept_mistakes[cid] = concept_mistakes.get(cid, 0) + unattributed

        overall_score = round(total_score / max(len(questions), 1), 1)

        # 1. Update Concept Mastery using deterministic formula
        for concept_id in concepts_tested:
            cm = db.query(ConceptMastery).filter(
                ConceptMastery.concept_id == concept_id,
                ConceptMastery.user_id == user_id,
            ).first()
            if cm:
                prev_score = cm.score
                # Deterministic formula: 0.6 * previous + 0.4 * assessment
                new_score = round((prev_score * 0.6) + (overall_score * 0.4), 1)
                cm.score = new_score
                cm.assessment_count += 1
                c_mistakes = concept_mistakes.get(concept_id, 0)
                cm.mistake_count += c_mistakes
                cm.last_practiced_at = datetime.now(timezone.utc)

                # Growth status classification
                diff = new_score - prev_score
                if diff >= 2.0:
                    cm.status = "improving"
                elif diff <= -2.0 or new_score < 45.0:
                    cm.status = "attention"
                else:
                    cm.status = "stable"

                # Record in MasteryHistory
                history = MasteryHistory(
                    concept_id=concept_id,
                    project_id=project_id,
                    user_id=user_id,
                    previous_score=prev_score,
                    new_score=new_score,
                    trigger_event="QUIZ_COMPLETED",
                )
                db.add(history)
        db.commit()

        # 2. Persist QuizAttempt
        attempt = QuizAttempt(
            quiz_id=quiz_id,
            project_id=project_id,
            user_id=user_id,
            score=overall_score,
            evaluation_details={"results": [r.model_dump() for r in results]},
        )
        db.add(attempt)
        db.commit()
        db.refresh(attempt)

        # 3. Trigger Recommendation Generation based on updated state
        LearningService.generate_recommendation(project_id, user_id, db)

        # 4. Log event
        event = LearningEvent(
            user_id=user_id,
            project_id=project_id,
            event_type="ASSESSMENT_COMPLETED",
            payload={"quiz_id": quiz_id, "score": overall_score, "mistakes": mistakes_made},
        )
        db.add(event)
        db.commit()

        feedback_msg = (
            f"Assessment completed with a score of {overall_score}%. "
            f"{'Excellent comprehension!' if overall_score >= 80 else 'Good effort — review weak areas indicated below.'}"
        )

        return QuizAttemptResponse(
            id=attempt.id,
            quiz_id=quiz_id,
            score=overall_score,
            question_results=results,
            overall_feedback=feedback_msg,
            created_at=attempt.created_at,
        )

    @staticmethod
    def generate_recommendation(project_id: str, user_id: str, db) -> Optional[RecommendationResponse]:
        """Generates actionable 'What should I do next?' based on mastery and mistakes."""
        # Find weakest concept
        weakest = db.query(ConceptMastery, Concept.name).\
            join(Concept, ConceptMastery.concept_id == Concept.id).\
            filter(ConceptMastery.project_id == project_id, ConceptMastery.user_id == user_id).\
            order_by(ConceptMastery.score.asc()).first()

        if not weakest:
            return None

        cm, concept_name = weakest
        if cm.score < 50.0:
            action = f"Review foundational notes on {concept_name} and ask the AI Tutor for a step-by-step example."
            reason = f"Your estimated mastery in {concept_name} is currently at {cm.score:.0f}%, which requires immediate attention."
            priority = "high"
        elif cm.score < 75.0:
            action = f"Attempt a targeted 4-question adaptive quiz focusing on {concept_name} applications."
            reason = f"Your mastery is progressing ({cm.score:.0f}%), but application under timed assessment will reinforce retention."
            priority = "medium"
        else:
            action = f"Explore advanced edge cases with the AI Tutor or proceed to the next module."
            reason = f"Solid understanding demonstrated ({cm.score:.0f}% mastery)."
            priority = "low"

        # Check if identical pending recommendation exists
        existing = db.query(Recommendation).filter(
            Recommendation.project_id == project_id,
            Recommendation.user_id == user_id,
            Recommendation.concept_id == cm.concept_id,
            Recommendation.is_completed == False,
        ).first()

        if not existing:
            rec = Recommendation(
                project_id=project_id,
                user_id=user_id,
                concept_id=cm.concept_id,
                action=action,
                reason=reason,
                priority=priority,
                is_completed=False,
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)
            return RecommendationResponse.model_validate(rec)
        return RecommendationResponse.model_validate(existing)

    @staticmethod
    def get_mastery_summary(project_id: str, user_id: str, db) -> MasterySummaryResponse:
        """Summarizes concept mastery levels and growth trends."""
        masteries = db.query(ConceptMastery, Concept.name).\
            join(Concept, ConceptMastery.concept_id == Concept.id).\
            filter(ConceptMastery.project_id == project_id, ConceptMastery.user_id == user_id).all()

        concept_items = []
        growth_items = []
        total_score = 0.0

        for cm, name in masteries:
            total_score += cm.score
            concept_items.append(ConceptMasteryItem(
                concept_id=cm.concept_id,
                concept_name=name,
                score=cm.score,
                status=cm.status,
                assessment_count=cm.assessment_count,
                mistake_count=cm.mistake_count,
                last_practiced_at=cm.last_practiced_at,
            ))

            # Fetch latest history
            history = db.query(MasteryHistory).filter(
                MasteryHistory.concept_id == cm.concept_id,
                MasteryHistory.user_id == user_id,
            ).order_by(MasteryHistory.created_at.desc()).first()

            prev = history.previous_score if history else cm.score
            change = round(cm.score - prev, 1)
            growth_items.append(GrowthItem(
                concept_id=cm.concept_id,
                concept_name=name,
                previous_score=prev,
                current_score=cm.score,
                trend=cm.status,
                change=change,
            ))

        avg_mastery = round(total_score / max(len(masteries), 1), 1) if masteries else 0.0
        return MasterySummaryResponse(
            overall_mastery=avg_mastery,
            concepts=concept_items,
            growth=growth_items,
        )


learning_service = LearningService()
