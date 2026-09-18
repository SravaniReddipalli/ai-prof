# AI.Prof — AI Study Companion

AI.Prof is a full-stack, AI-powered learning and growth workspace designed to help learners deeply understand, practice, measure, and continuously improve their knowledge in any domain.

This project was built as a complete end-to-end prototype for the 36-Hour Full-Stack AI Engineer Challenge.

## 🚀 Core Features & The Learning Loop

The application implements a comprehensive learning loop based on cognitive science and strict project isolation:

1. **Spaces & Projects**: Organize your learning into high-level Spaces (e.g., "Computer Science") and specific Projects (e.g., "Database Systems"). **Strict data isolation ensures your AI Tutor only knows about the materials in your current project.**
2. **Document Processing (Async)**: Upload PDF study materials. A concurrency-safe background worker uses `PyMuPDF` to extract text, chunks it, and generates vector embeddings using OpenAI's `text-embedding-3-small`.
3. **RAG & Grounded AI Tutor**: Chat with an AI Tutor that is strictly grounded in your uploaded materials. 
   - Uses **Cosine Similarity Retrieval** via `pgvector` to find the most relevant chunks.
   - Includes a **Holistic Grounding Evaluation**: If the retrieved evidence is insufficient, the AI Tutor explicitly refuses to answer rather than hallucinating.
   - Provides exact page-level **citations** for every claim.
4. **Adaptive Assessments**: Generate dynamic quizzes based on your weakest concepts. Quizzes include both Multiple Choice and Open-Ended questions.
5. **Structured Evaluation & Mastery**: 
   - Open-ended answers are evaluated using a structured LLM output (Pydantic schemas) against a detailed rubric.
   - A **deterministic mastery heuristic** tracks your score and growth over time.
6. **Actionable Recommendations**: Automatically generates next-step recommendations (e.g., "Review Page 12") based on your specific mistakes and weak points.
7. **Admin Dashboard**: Comprehensive observability into AI token usage, costs, user metrics, and background job states.

## 🏗 System Architecture

- **Frontend**: React 19, TypeScript, Vite, Tailwind CSS, Lucide Icons, Recharts.
- **Backend**: FastAPI, Python 3.13, Pydantic, SQLAlchemy.
- **Database**: PostgreSQL with `pgvector` extension (Serves as both relational store and vector database).
- **Authentication**: JWT (HS256) with bcrypt password hashing.
- **AI/LLM**: OpenAI API (`gpt-4o-mini`, `text-embedding-3-small`).
- **Storage**: Abstracted StorageService supporting both Local FileSystem (for dev) and S3/Supabase (for production).
- **Background Jobs**: Database-backed worker queue utilizing PostgreSQL's `FOR UPDATE SKIP LOCKED` for concurrency-safe job claiming without requiring Celery/Redis.

## 🛠 Getting Started (Local Development)

### Prerequisites
- Python 3.10+
- Node.js 18+
- PostgreSQL 15+ with the `pgvector` extension installed.

### 1. Database Setup
Ensure PostgreSQL is running and create a database named `aiprof`. The `pgvector` extension must be available.

### 2. Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create environment variables
cp .env.example .env
# Edit .env and add your OPENAI_API_KEY. (If omitted, the app uses deterministic mocks for testing).

# Run the backend service (Port 8000)
uvicorn app.main:app --reload

# In a separate terminal, run the background worker daemon:
python -m app.workers.worker
```

### 3. Frontend Setup
```bash
cd frontend
npm install

# Start the Vite development server (Port 5173)
npm run dev
```

### 4. Demo Data Seeding
To quickly populate a demo workspace for testing:
1. Register an account as `admin@aiprof.io`.
2. Visit `http://localhost:5173/admin` and click the "Seed Demo Data" button.
3. This will create a "Database Management Systems" project with pre-processed PDF notes, knowledge chunks, concept masteries, and recommendations.

## 🧪 Testing

The backend includes a comprehensive pytest suite utilizing a temporary in-memory SQLite database (with mocked vector operations).

```bash
cd backend
python -m pytest tests/ -v
```
**Test Coverage Includes:**
- JWT Authentication & RBAC Isolation
- Cross-user and Cross-project Data Isolation Guards
- RAG Vector Retrieval & Citation Verification
- Unsupported Question Refusal Logic
- Adaptive Quiz Generation & Mastery Calculation
- Concurrency-safe Worker Job Claiming

## 📦 Deployment Strategy

- **Database**: Neon Serverless Postgres or Supabase (both support pgvector).
- **Backend API**: Render or Railway (Dockerized FastAPI).
- **Background Worker**: Render Background Worker (running `python -m app.workers.worker` sharing the same DB).
- **Frontend**: Vercel or Netlify.
- **File Storage**: Supabase Storage or AWS S3.

## 🔒 Security & Privacy
- **Strict Data Isolation**: All vector similarity searches explicitly filter `WHERE project_id = :project_id`.
- **Stateless Auth**: JWT-based authentication.
- **No Hallucinations**: The prompt engineering strictly enforces "If evidence is missing, output the canonical refusal string."

---
*Built for the 36-Hour Full-Stack AI Engineer Challenge.*
