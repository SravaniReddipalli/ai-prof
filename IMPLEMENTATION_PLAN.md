# Final Approved Implementation Plan: AI.Prof — AI Study Companion

## 1. Executive Summary & Core Requirements

AI.Prof is an AI-powered learning and growth workspace designed to help learners understand, practice, measure, and continuously improve a skill or knowledge domain.

The application implements the complete authoritative PRD learning loop:
**Space → Project → Material → Document Processing → Knowledge/Retrieval → AI Tutor → Grounded Answer + Citation → Unsupported Question Handling → Adaptive Quiz → Open-Ended Assessment → Mastery → Growth → Analytics → Recommendation → Continue Learning**

---

## 2. Final System Architecture

```
+-------------------------------------------------------------------------------------------------+
|                               React 19 + TypeScript + Vite + Tailwind UI                         |
|  - Built early (Hours 0–4) with Auth context, API client, router, and core workspace layout     |
|  - Clean, professional, robust interface with loading states, error handling, and empty states   |
|  - Routes: Auth, Home, Spaces, Project Dashboard (Overview, Materials, Tutor, Quiz, Mastery,   |
|    Analytics), Admin Dashboard                                                                  |
+-------------------------------------------------------------------------------------------------+
                                                │
                                      REST API (FastAPI)
                                                │
+-------------------------------------------------------------------------------------------------+
|                                     FastAPI Backend Application                                 |
|                                                                                                 |
|  ┌────────────────────────┐  ┌────────────────────────┐  ┌───────────────────────────────────┐  |
|  │ Auth & Security Layer  │  │ Project Isolation Guard│  │ RAG & Tutor Service               │  |
|  │ - JWT (HS256) + Bcrypt │  │ - Strict Ownership     │  │ - Project-scoped vector search    │  |
|  │ - RBAC (User / Admin)  │  │ - No cross-project leak│  │ - Holistic Grounding & Citations  │  |
|  └────────────────────────┘  └────────────────────────┘  │ - Retrieval score logging         │  |
|                                                          └───────────────────────────────────┘  |
|  ┌────────────────────────┐  ┌────────────────────────┐  ┌───────────────────────────────────┐  |
|  │ Adaptive Assessment    │  │ Background Worker Engine│ │ Storage & Observability           │  |
|  │ - Deterministic Heuris.│  │ - FOR UPDATE SKIP LOCKED│  │ - StorageService (Local / S3)    │  |
|  │ - MCQ + Open-ended Eval│  │ - Concurrency-safe claim│  │ - AIUsage tracking (tokens/cost)  │  |
|  │ - Mastery & Growth     │  │ - Non-blocking concept │  │ - Background jobs & Platform logs │  |
|  └────────────────────────┘  └────────────────────────┘  └───────────────────────────────────┘  |
+-------------------------------------------------------------------------------------------------+
                                                │
                     ┌──────────────────────────┴──────────────────────────┐
                     ▼                                                     ▼
+------------------------------------------+          +-----------------------------------------+
|     PostgreSQL + pgvector (Single DB)    |          |            OpenAI API Layer             |
|  - Single production DB architecture     |          |  - gpt-4o / gpt-4o-mini                 |
|  - Vector(1536) cosine distance search   |          |  - text-embedding-3-small (1536 dims)   |
|  - Relational entities & Job queue       |          |  - Structured Pydantic outputs          |
+------------------------------------------+          +-----------------------------------------+
                     │
                     ▼
+------------------------------------------+
|       Storage Abstraction Layer          |
|  - Local storage (dev)                   |
|  - Supabase / S3 Object Storage (prod)   |
+------------------------------------------+
```

---

## 3. Final Architecture Decisions & Invariants

1. **Persistent Object Storage Abstraction**:
   - `StorageService` interface with `upload_file(key, data, content_type)`, `download_file(key)`, `get_url(key)`.
   - `LocalStorageService` for local dev; `S3StorageService` (Supabase Storage / AWS S3 / Cloudflare R2 compatible) for production.
   - Database stores only the object key/path (`materials.storage_key`). Web service and worker can run on separate instances/containers without sharing disks.

2. **RAG & Holistic Unsupported-Question Evaluation**:
   - Similarity retrieval acts as an evidence-quality / candidate filtering mechanism.
   - The system retrieves top-K chunks strictly scoped by `WHERE project_id = :project_id`.
   - LLM evaluates the retrieved evidence as a whole for grounding.
   - The configurable similarity threshold (`RAG_SIMILARITY_THRESHOLD`, default `0.65`) filters out total noise without causing false refusals when relevant context exists.
   - Retrieval scores are logged in `ai_usage` and application logs for observability.

3. **Early Frontend Foundation**:
   - Hours 0–4 establishes the full React application shell, React Router, Tailwind configuration, Axios API client with JWT interceptors, AuthContext, and basic page shells alongside the backend foundation.

4. **Concurrency-Safe Background Worker**:
   - Worker claims jobs using PostgreSQL row locking:
     `UPDATE background_jobs SET status = 'PROCESSING', updated_at = NOW() WHERE id = (SELECT id FROM background_jobs WHERE status = 'QUEUED' ORDER BY created_at ASC FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING *;`
   - Guarantees that multiple concurrent worker processes cannot process the same job.

5. **Non-Blocking Material Readiness**:
   - Once PDF text extraction, chunking, and embeddings are committed, material status is set to `READY`.
   - Concept extraction executes in a safe non-blocking post-step. Failure or timeout in concept extraction does not block material usability.

6. **Secured Demo Seeding**:
   - `POST /api/demo/seed` is strictly protected: requires `role: "admin"` OR `ENVIRONMENT="development"`. Populates the "Database Management Systems (DBMS)" domain.

7. **Compact Tutor Context**:
   - Sliding window of 4–6 recent messages + compact learner summary JSON + top 3–5 project chunks.

8. **Deterministic Assessment & Mastery Heuristics**:
   - Adaptive Priority: `(100 - mastery) * 0.5 + (mistake_freq * 20) * 0.3 + (recency * 5) * 0.2`.
   - Mastery Formula: `new_mastery = round((prev_mastery * 0.6) + (assessment_score * 0.4))`.

9. **Strict Feature Freeze at Hour 24**:
   - After Hour 24, all feature development halts. Work focuses entirely on integration, bug fixing, security, testing, deployment, documentation, and demo verification.

---

## 4. 36-Hour Timeline & Milestones

| Time Window | Milestone | Scope |
|---|---|---|
| **Hours 0–4** | **Foundation (Backend + Early Frontend)** | FastAPI app, PostgreSQL+pgvector setup, StorageService, JWT Auth, React 19 + Vite + Tailwind shell, Router, API client, Auth state. |
| **Hours 4–8** | **Document Processing & Safe Worker** | PyMuPDF extraction, chunking, concurrency-safe worker (SKIP LOCKED), upload endpoint, non-blocking concept extraction. |
| **Hours 8–14** | **RAG, Vector Retrieval & Grounded Tutor** | Embeddings, pgvector query, holistic unsupported handling, exact citations, sliding window context, Tutor chat UI. |
| **Hours 14–20** | **Adaptive Quiz & Mastery Engine** | Adaptive question generation, MCQ & open-ended grading, deterministic mastery formula, growth analyzer, Quiz & Mastery UI. |
| **Hours 20–24** | **Analytics, Admin & End-to-End Loop** | Recommendations widget, project & global analytics, Admin dashboard (Users, AIUsage, Jobs), **Complete Learning Loop Verified**. |
| **--- HOUR 24 ---** | **FEATURE FREEZE** | **Zero new features. Shift exclusively to stabilization, security, tests, deploy, and docs.** |
| **Hours 24–28** | **Stabilization & Critical Testing** | Focused pytest suite (Auth, isolation, RAG, grounding, unsupported refusal, mastery, worker jobs), AI eval dataset test runner. |
| **Hours 28–32** | **Deployment & Production Hardening** | Neon/Supabase DB + pgvector, S3/Supabase storage, Render/Railway backend & worker, Vercel frontend, CORS, security audit. |
| **Hours 32–36** | **Documentation & Final Demo Walkthrough** | Protected demo seed, comprehensive README, architecture docs, PRD compliance matrix, prompt logs, demo verification. |

---

## 5. Verification Plan

### Critical Automated Tests (`pytest`)
- `test_auth.py`: JWT generation, password hashing, 401/403 guards.
- `test_isolation.py`: Cross-user & cross-project access blocks.
- `test_storage.py`: StorageService abstraction (local & S3 interface).
- `test_worker.py`: Concurrency-safe job claiming (`SKIP LOCKED`), state transitions (`QUEUED` -> `PROCESSING` -> `READY`/`FAILED`).
- `test_rag.py`: Project-scoped vector search, citation structure, holistic unsupported rejection.
- `test_adaptive_quiz.py`: Adaptive concept prioritization heuristic, MCQ grading, open-ended evaluation schema.
- `test_mastery.py`: Deterministic mastery calculation and growth status.

### Curated AI Evaluation Dataset (`backend/app/ai/eval_dataset.json`)
- Grounded Q&A case
- Unsupported Q&A case
- Citation correctness case
- Project boundary isolation case
- Structured output schema validation case
