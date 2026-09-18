from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional, Any, Dict
from datetime import datetime

# --- AUTH SCHEMAS ---
class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6)
    full_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# --- SPACE SCHEMAS ---
class SpaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    icon: Optional[str] = "folder"
    color: Optional[str] = "indigo"

class SpaceUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None

class SpaceResponse(BaseModel):
    id: str
    user_id: str
    name: str
    description: Optional[str] = None
    icon: str
    color: str
    project_count: Optional[int] = 0
    created_at: datetime

    class Config:
        from_attributes = True


# --- PROJECT SCHEMAS ---
class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    learning_goal: Optional[str] = None

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    learning_goal: Optional[str] = None

class ProjectResponse(BaseModel):
    id: str
    space_id: str
    user_id: str
    name: str
    description: Optional[str] = None
    learning_goal: Optional[str] = None
    material_count: Optional[int] = 0
    concept_count: Optional[int] = 0
    created_at: datetime

    class Config:
        from_attributes = True


# --- MATERIAL SCHEMAS ---
class MaterialResponse(BaseModel):
    id: str
    project_id: str
    title: str
    filename: str
    storage_key: str
    file_size_bytes: int
    page_count: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class MaterialStatusResponse(BaseModel):
    id: str
    status: str
    error_message: Optional[str] = None
    page_count: int


# --- TUTOR SCHEMAS ---
class CitationItem(BaseModel):
    source: str
    page: int
    snippet: str

class TutorChatRequest(BaseModel):
    message: str = Field(..., min_length=1)

class TutorChatResponse(BaseModel):
    message_id: str
    reply: str
    citations: List[CitationItem] = []
    is_unsupported: bool = False
    evidence_score: Optional[float] = None

class MessageHistoryItem(BaseModel):
    id: str
    sender: str
    content: str
    citations: Optional[List[CitationItem]] = None
    is_unsupported: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --- QUIZ & ASSESSMENT SCHEMAS ---
class QuizQuestionResponse(BaseModel):
    id: str
    concept_id: Optional[str] = None
    type: str  # "mcq" or "open_ended"
    question: str
    options: Optional[List[str]] = None
    difficulty: str

    class Config:
        from_attributes = True

class QuizResponse(BaseModel):
    id: str
    project_id: str
    title: str
    difficulty: str
    questions: List[QuizQuestionResponse]
    created_at: datetime

    class Config:
        from_attributes = True

class UserAnswerSubmission(BaseModel):
    question_id: str
    answer: str

class QuizSubmitRequest(BaseModel):
    answers: List[UserAnswerSubmission]

class OpenEndedEvaluation(BaseModel):
    score: float = Field(..., ge=0, le=100)
    what_you_understood: List[str] = []
    concepts_covered: List[str] = []
    missing_concepts: List[str] = []
    feedback: str
    suggested_action: str
    reasoning_quality: str
    confidence: float = Field(..., ge=0, le=1)

class QuestionResultItem(BaseModel):
    question_id: str
    question: str
    type: str
    user_answer: str
    correct_answer: Optional[str] = None
    is_correct: Optional[bool] = None
    explanation: Optional[str] = None
    evaluation: Optional[OpenEndedEvaluation] = None

class QuizAttemptResponse(BaseModel):
    id: str
    quiz_id: str
    score: float
    question_results: List[QuestionResultItem]
    overall_feedback: str
    created_at: datetime


# --- MASTERY & GROWTH SCHEMAS ---
class ConceptMasteryItem(BaseModel):
    concept_id: str
    concept_name: str
    score: float
    status: str  # improving, stable, attention
    assessment_count: int
    mistake_count: int
    last_practiced_at: Optional[datetime] = None

class GrowthItem(BaseModel):
    concept_id: str
    concept_name: str
    previous_score: float
    current_score: float
    trend: str  # improving, stable, attention
    change: float

class MasterySummaryResponse(BaseModel):
    overall_mastery: float
    concepts: List[ConceptMasteryItem]
    growth: List[GrowthItem]


# --- RECOMMENDATION SCHEMAS ---
class RecommendationResponse(BaseModel):
    id: str
    project_id: str
    concept_id: Optional[str] = None
    action: str
    reason: str
    priority: str  # high, medium, low
    is_completed: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --- ANALYTICS SCHEMAS ---
class ProjectAnalyticsResponse(BaseModel):
    project_id: str
    learning_goal: Optional[str]
    total_materials: int
    total_chunks: int
    overall_mastery: float
    quizzes_taken: int
    average_quiz_score: float
    tutor_messages_count: int
    concept_scores: List[Dict[str, Any]]
    recent_events: List[Dict[str, Any]]

class GlobalAnalyticsResponse(BaseModel):
    total_spaces: int
    total_projects: int
    total_materials: int
    total_quizzes_completed: int
    average_platform_score: float
    active_streak_days: int
    recent_activity: List[Dict[str, Any]]


# --- ADMIN SCHEMAS ---
class AIUsageItem(BaseModel):
    id: str
    feature: str
    model: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: float
    success: bool
    error_message: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class BackgroundJobItem(BaseModel):
    id: str
    job_type: str
    status: str
    attempts: int
    max_attempts: int
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class AdminOverviewResponse(BaseModel):
    total_users: int
    total_spaces: int
    total_projects: int
    total_materials: int
    total_quizzes: int
    total_ai_requests: int
    total_ai_cost_usd: float
    failed_ai_requests: int
    active_background_jobs: int
    failed_background_jobs: int

class AdminUserInspectResponse(BaseModel):
    user: UserResponse
    spaces_count: int
    projects_count: int
    quizzes_count: int
    materials_count: int
    recent_activity: List[Dict[str, Any]]
    ai_requests_count: int
    estimated_ai_cost_usd: float
