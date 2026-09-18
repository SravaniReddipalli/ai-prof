import re
import difflib
from typing import List, Set

STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "explain", "few", "for", "from", "further", "had", "hadn't",
    "has", "hasn't", "have", "haven't", "having", "he", "her", "here", "hers",
    "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is",
    "isn't", "it", "its", "itself", "just", "me", "more", "most", "my", "myself",
    "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or", "other",
    "ought", "our", "ours", "ourselves", "out", "over", "own", "please", "same",
    "she", "should", "shouldn't", "so", "some", "such", "tell", "than", "that",
    "the", "their", "theirs", "them", "themselves", "then", "there", "these",
    "they", "this", "those", "through", "to", "too", "under", "until", "up", "very",
    "was", "wasn't", "we", "were", "weren't", "what", "when", "where", "which",
    "while", "who", "whom", "why", "with", "would", "wouldn't", "you", "your",
    "yours", "yourself", "yourselves", "describe", "discuss", "give", "help", "show",
    "used", "using", "use", "uses", "called", "based", "like", "also", "well",
    "many", "much", "make", "made", "come", "goes", "going", "done", "need",
    "needs", "want", "take", "get", "got", "set", "let", "say", "said",
}

def extract_query_terms(text: str) -> List[str]:
    """
    Extracts substantive concept terms from a query, normalizing punctuation and case,
    and filtering out stopwords and single-character tokens.
    """
    if not text:
        return []
    words = re.findall(r"\b[a-zA-Z0-9_\-\+]+\b", text.lower())
    return [w for w in words if len(w) >= 2 and w not in STOPWORDS]

def term_matches_text(term: str, text: str, min_fuzzy_ratio: float = 0.82) -> bool:
    """
    Determines whether a concept term matches the given text.
    - Exact match (substring) is checked first.
    - Short terms (length < 5, e.g. '3nf', 'b+', 'key') only match exactly to prevent false cross-concept matches.
    - Meaningful terms (length >= 5) are checked against substantive words in the text using
      fuzzy string similarity (difflib) with a strict ratio threshold and length constraint.
    """
    term_lower = term.lower().strip()
    if not term_lower:
        return False

    text_lower = text.lower()
    # 1. Exact substring check
    if term_lower in text_lower:
        return True

    # 2. Short terms must match exactly (do not fuzzy match '3nf' to '2nf' or 'tree' to 'free')
    if len(term_lower) < 5:
        return False

    # 3. Fuzzy match meaningful terms against substantive words in the text
    text_words = [
        w for w in re.findall(r"\b[a-zA-Z0-9_\-\+]+\b", text_lower)
        if len(w) >= 5 and w not in STOPWORDS
    ]
    if not text_words:
        return False

    # Pre-filter candidates by length difference <= 2
    candidates = [
        w for w in set(text_words)
        if abs(len(w) - len(term_lower)) <= 2
    ]
    if not candidates:
        return False

    close_matches = difflib.get_close_matches(term_lower, candidates, n=1, cutoff=min_fuzzy_ratio)
    return len(close_matches) > 0

def count_term_matches(terms: List[str], text: str, min_fuzzy_ratio: float = 0.82) -> int:
    """Counts how many query terms match the text via exact or fuzzy matching."""
    return sum(1 for t in terms if term_matches_text(t, text, min_fuzzy_ratio=min_fuzzy_ratio))

def score_chunk_relevance(query_terms: List[str], content: str, title: str = "") -> float:
    """
    Scores chunk relevance for the mock/fallback retrieval path.
    Returns an estimated similarity score in [0.0, 1.0].
    """
    if not query_terms:
        return 0.5

    combined = f"{title}\n{content}"
    matches = count_term_matches(query_terms, combined)
    if matches == 0:
        return 0.10

    match_ratio = min(1.0, matches / len(query_terms))
    return round(0.70 + (0.25 * match_ratio), 4)
