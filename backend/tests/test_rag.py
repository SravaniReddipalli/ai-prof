from app.rag.rag_service import CANONICAL_UNSUPPORTED_REPLY

def test_tutor_grounded_answer(client, test_workspace, user_token):
    proj_id = test_workspace["project"].id

    res = client.post(
        f"/api/projects/{proj_id}/tutor/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"message": "What is Third Normal Form (3NF)?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_unsupported"] is False
    assert len(data["citations"]) > 0
    # Verify citation attributes
    first_citation = data["citations"][0]
    assert "source" in first_citation
    assert "page" in first_citation
    assert "snippet" in first_citation

def test_tutor_unsupported_question_handling(client, test_workspace, user_token):
    proj_id = test_workspace["project"].id

    # Question completely outside project materials
    res = client.post(
        f"/api/projects/{proj_id}/tutor/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"message": "What is the capital of France?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_unsupported"] is True
    assert CANONICAL_UNSUPPORTED_REPLY in data["reply"]
    assert len(data["citations"]) == 0

def test_tutor_history_and_clear(client, test_workspace, user_token):
    proj_id = test_workspace["project"].id

    # Ask a question to generate history
    client.post(
        f"/api/projects/{proj_id}/tutor/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"message": "Explain transactions and ACID properties."},
    )

    # Fetch history
    res_hist = client.get(
        f"/api/projects/{proj_id}/tutor/history",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert res_hist.status_code == 200
    history = res_hist.json()
    assert len(history) >= 2  # user msg + assistant msg

    # Clear history
    res_clear = client.post(
        f"/api/projects/{proj_id}/tutor/clear",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert res_clear.status_code == 204

    # Verify history is empty
    res_empty = client.get(
        f"/api/projects/{proj_id}/tutor/history",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert len(res_empty.json()) == 0

def test_tutor_grounded_response_quality(client, test_workspace, user_token):
    """
    Verifies that for a multi-part grounded question:
    'What is normalization, and why is 3NF used?'
    the Tutor explains ALL substantive parts of the question (both normalization and 3NF)
    using the retrieved evidence rather than stopping after the first matching concept.
    """
    proj_id = test_workspace["project"].id

    res = client.post(
        f"/api/projects/{proj_id}/tutor/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"message": "What is normalization, and why is 3NF used?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_unsupported"] is False
    assert len(data["citations"]) > 0

    reply = data["reply"]
    # Must NOT return generic placeholder
    assert "fundamental concept discussed in your notes" not in reply.lower()
    # Must NOT contain literal "svgSource:" artifact
    assert "svgsource:" not in reply.lower()
    for cit in data["citations"]:
        assert "svgsource:" not in cit["source"].lower()

    # Must explain BOTH parts: normalization AND 3NF (transitive dependencies)
    assert "normalization" in reply.lower()
    assert "3nf" in reply.lower() or "third normal form" in reply.lower()
    assert "transitive dependencies" in reply.lower() or "primary key" in reply.lower()
    # Must contain citation
    assert "Source:" in reply

def test_tutor_partial_unsupported_multi_part_question(client, test_workspace, user_token):
    """
    Verifies that if evidence supports only part of a multi-part question,
    the Tutor answers the supported part from evidence and clearly declares
    which part is unsupported.
    """
    proj_id = test_workspace["project"].id

    res = client.post(
        f"/api/projects/{proj_id}/tutor/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"message": "What is normalization, and what is quantum entanglement?"},
    )
    assert res.status_code == 200
    data = res.json()
    reply = data["reply"]

    # Answers supported part (normalization)
    assert "normalization" in reply.lower()
    # Clearly declares unsupported part
    assert "quantum entanglement" in reply.lower()
    assert "couldn't find enough information" in reply.lower()
    # Citations present for supported material
    assert len(data["citations"]) > 0
    assert "Source:" in reply

def test_tutor_generic_unsupported_detection(client, test_workspace, user_token):
    """
    Verifies that out-of-domain questions without hardcoded strings (e.g. 'What is the capital of Telangana?')
    are recognized as unsupported through generic evidence inspection.
    """
    proj_id = test_workspace["project"].id

    res = client.post(
        f"/api/projects/{proj_id}/tutor/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"message": "What is the capital of Telangana?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_unsupported"] is True
    assert CANONICAL_UNSUPPORTED_REPLY in data["reply"]
    assert len(data["citations"]) == 0

def test_tutor_no_irrelevant_chunks_in_response(client, test_workspace, user_token):
    """
    End-to-end regression test for the B+ Tree contamination bug.
    Context: relevant normalization/3NF chunks + irrelevant B+ Tree chunk (Page 12).

    Asserts:
    - normalization IS addressed
    - 3NF IS addressed (or declared unsupported if evidence is insufficient)
    - B+ Tree is NOT introduced in the response text
    - Page 12 citation is NOT returned (since Page 12 is B-Tree, not normalization/3NF)
    """
    proj_id = test_workspace["project"].id

    res = client.post(
        f"/api/projects/{proj_id}/tutor/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"message": "What is normalization, and why is 3NF used?"},
    )
    assert res.status_code == 200
    data = res.json()
    reply = data["reply"].lower()

    # Normalization MUST be addressed
    assert "normalization" in reply

    # B+ Tree / B-Tree must NOT be introduced (it is irrelevant to the question)
    assert "b-tree" not in reply, f"Response incorrectly includes B-Tree content: {data['reply'][:200]}"
    assert "b+ tree" not in reply, f"Response incorrectly includes B+ Tree content: {data['reply'][:200]}"
    assert "b+tree" not in reply, f"Response incorrectly includes B+Tree content: {data['reply'][:200]}"

    # Page 12 citation (B-Tree page) must NOT appear
    citation_pages = [c["page"] for c in data["citations"]]
    assert 12 not in citation_pages, f"Citations incorrectly include Page 12 (B-Tree): {data['citations']}"

    # If 3NF evidence exists, it must be addressed; citations must reference only relevant pages
    for cit in data["citations"]:
        assert cit["page"] in (1, 2), f"Citation references unexpected page {cit['page']}"

def test_relevance_filter_excludes_irrelevant_chunks():
    """
    Unit test for RAGService._filter_relevant_chunks.
    Verifies that chunks without substantive keyword overlap with the query are excluded,
    while chunks with matching concept terms are kept.
    """
    from app.rag.rag_service import RAGService

    chunks = [
        {"content": "Normalization eliminates redundancy via 1NF and 2NF.", "material_title": "Notes", "page_number": 1},
        {"content": "3NF removes transitive dependencies from the primary key.", "material_title": "Notes", "page_number": 2},
        {"content": "B-Tree and B+ Tree indexes speed up range queries.", "material_title": "Notes", "page_number": 12},
        {"content": "Relational Joins combine rows from tables.", "material_title": "Notes", "page_number": 18},
    ]
    scores = [0.9, 0.8, 0.7, 0.6]

    # Query about normalization/3NF — should keep chunks 0 and 1, filter out 2 and 3
    relevant, rel_scores = RAGService._filter_relevant_chunks(
        chunks, scores, "What is normalization, and why is 3NF used?"
    )
    relevant_pages = [c["page_number"] for c in relevant]
    assert 1 in relevant_pages, "Normalization chunk should be kept"
    assert 2 in relevant_pages, "3NF chunk should be kept"
    assert 12 not in relevant_pages, "B-Tree chunk should be filtered out"
    assert 18 not in relevant_pages, "Joins chunk should be filtered out"

    # Query about B-Tree — should keep only the B-Tree chunk
    relevant2, _ = RAGService._filter_relevant_chunks(
        chunks, scores, "How do B-Tree indexes work?"
    )
    relevant2_pages = [c["page_number"] for c in relevant2]
    assert 12 in relevant2_pages, "B-Tree chunk should be kept for B-Tree query"
    assert 1 not in relevant2_pages, "Normalization chunk should be filtered for B-Tree query"

    # Completely unrelated query — should keep nothing
    relevant3, _ = RAGService._filter_relevant_chunks(
        chunks, scores, "What is the capital of France?"
    )
    assert len(relevant3) == 0, "No chunks should match an unrelated query"


def test_tutor_typo_normaization(client, test_workspace, user_token):
    """
    Verifies that a query with typo 'normaization' is successfully recognized,
    retrieves the relevant normalization material, and returns a grounded answer with citation.
    """
    proj_id = test_workspace["project"].id

    res = client.post(
        f"/api/projects/{proj_id}/tutor/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"message": "what is normaization??"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_unsupported"] is False
    assert CANONICAL_UNSUPPORTED_REPLY not in data["reply"]
    assert len(data["citations"]) > 0

    citation_pages = [c["page"] for c in data["citations"]]
    assert 1 in citation_pages
    assert 12 not in citation_pages, "B-Tree chunk must not contaminate normalization typo query"


def test_tutor_typo_normlization(client, test_workspace, user_token):
    """
    Verifies that an alternate typo 'normlization' is also recognized generically.
    """
    proj_id = test_workspace["project"].id

    res = client.post(
        f"/api/projects/{proj_id}/tutor/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"message": "what is normlization?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_unsupported"] is False
    assert CANONICAL_UNSUPPORTED_REPLY not in data["reply"]
    assert len(data["citations"]) > 0

    citation_pages = [c["page"] for c in data["citations"]]
    assert 1 in citation_pages
    assert 12 not in citation_pages


def test_tutor_multi_concept_normalization_and_btree(client, test_workspace, user_token):
    """
    Verifies multi-concept query 'what is normalization and B+ tree?'
    returns relevant evidence for EACH concept (Page 1 and Page 12) without extraneous chunks.
    """
    proj_id = test_workspace["project"].id

    res = client.post(
        f"/api/projects/{proj_id}/tutor/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"message": "what is normalization and B+ tree?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_unsupported"] is False

    citation_pages = {c["page"] for c in data["citations"]}
    assert 1 in citation_pages, "Normalization chunk (Page 1) must be cited"
    assert 12 in citation_pages, "B+ Tree chunk (Page 12) must be cited"
    assert 2 not in citation_pages, "3NF chunk (Page 2) was not asked and must not be cited"


def test_tutor_typo_with_unrelated_partial_support(client, test_workspace, user_token):
    """
    Verifies that a typo on supported material combined with an unsupported concept
    correctly answers the supported part and flags the unsupported part.
    """
    proj_id = test_workspace["project"].id

    res = client.post(
        f"/api/projects/{proj_id}/tutor/chat",
        headers={"Authorization": f"Bearer {user_token}"},
        json={"message": "what is normaization, and what is quantum entanglement?"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["is_unsupported"] is False
    assert len(data["citations"]) > 0

    reply = data["reply"].lower()
    assert "couldn't find enough information" in reply
    assert "quantum entanglement" in reply
    citation_pages = [c["page"] for c in data["citations"]]
    assert 1 in citation_pages


def test_relevance_filter_typo_tolerance():
    """
    Unit test for RAGService._filter_relevant_chunks with typos.
    """
    from app.rag.rag_service import RAGService

    chunks = [
        {"content": "Normalization eliminates redundancy via 1NF and 2NF.", "material_title": "DBMS Notes", "page_number": 1},
        {"content": "3NF removes transitive dependencies from the primary key.", "material_title": "DBMS Notes", "page_number": 2},
        {"content": "B-Tree and B+ Tree indexes speed up range queries.", "material_title": "DBMS Notes", "page_number": 12},
        {"content": "Relational Joins combine rows from tables.", "material_title": "DBMS Notes", "page_number": 18},
    ]
    scores = [0.9, 0.8, 0.7, 0.6]

    # Typo 'normaization'
    rel_norma, _ = RAGService._filter_relevant_chunks(chunks, scores, "what is normaization??")
    pages_norma = [c["page_number"] for c in rel_norma]
    assert 1 in pages_norma, "Page 1 should match normaization"
    assert 12 not in pages_norma, "Page 12 (B-Tree) should not match normaization"
    assert 18 not in pages_norma, "Page 18 (Joins) should not match normaization"

    # Typo 'normlization'
    rel_norml, _ = RAGService._filter_relevant_chunks(chunks, scores, "what is normlization?")
    pages_norml = [c["page_number"] for c in rel_norml]
    assert 1 in pages_norml, "Page 1 should match normlization"
    assert 12 not in pages_norml

    # Multi-concept
    rel_multi, _ = RAGService._filter_relevant_chunks(chunks, scores, "what is normalization and B+ tree?")
    pages_multi = [c["page_number"] for c in rel_multi]
    assert 1 in pages_multi
    assert 12 in pages_multi
    assert 2 not in pages_multi
    assert 18 not in pages_multi


def test_text_matcher_unit():
    """
    Unit test for text_matcher module to verify stopword filtering and fuzzy matching constraints.
    """
    from app.rag.text_matcher import extract_query_terms, term_matches_text

    # Stopwords like 'what', 'is', 'used' must be filtered out
    terms = extract_query_terms("What is used for normalization?")
    assert "what" not in terms
    assert "is" not in terms
    assert "used" not in terms
    assert "for" not in terms
    assert "normalization" in terms

    # Meaningful term typos must match
    assert term_matches_text("normaization", "Database Normalization and tables") is True
    assert term_matches_text("normlization", "Database Normalization and tables") is True

    # Completely unrelated words must NOT match
    assert term_matches_text("capital", "Database Normalization and tables") is False
    assert term_matches_text("france", "Database Normalization and tables") is False
    assert term_matches_text("telangana", "Database Normalization and tables") is False

    # Short terms must NOT match other words fuzzily
    assert term_matches_text("3nf", "This chapter covers 2nf form") is False
    assert term_matches_text("tree", "Feel free to explore") is False
    assert term_matches_text("3nf", "Third normal form 3nf details") is True

