export interface User {
  id: string;
  email: string;
  full_name: string;
  role: 'user' | 'admin';
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Space {
  id: string;
  user_id: string;
  name: string;
  description?: string;
  icon: string;
  color: string;
  project_count: number;
  created_at: string;
}

export interface Project {
  id: string;
  space_id: string;
  user_id: string;
  name: string;
  description?: string;
  learning_goal?: string;
  material_count: number;
  concept_count: number;
  created_at: string;
}

export interface Material {
  id: string;
  project_id: string;
  title: string;
  filename: string;
  storage_key: string;
  file_size_bytes: number;
  page_count: number;
  status: 'QUEUED' | 'PROCESSING' | 'READY' | 'FAILED';
  error_message?: string;
  created_at: string;
}

export interface MaterialStatus {
  id: string;
  status: 'QUEUED' | 'PROCESSING' | 'READY' | 'FAILED';
  error_message?: string;
  page_count: number;
}

export interface Citation {
  source: string;
  page: number;
  snippet: string;
}

export interface MessageHistoryItem {
  id: string;
  sender: 'user' | 'assistant';
  content: string;
  citations?: Citation[];
  is_unsupported: boolean;
  created_at: string;
}

export interface TutorResponse {
  message_id: string;
  reply: string;
  citations: Citation[];
  is_unsupported: boolean;
  evidence_score?: number;
}

export interface QuizQuestion {
  id: string;
  concept_id?: string;
  type: 'mcq' | 'open_ended';
  question: string;
  options?: string[];
  difficulty: string;
}

export interface Quiz {
  id: string;
  project_id: string;
  title: string;
  difficulty: string;
  questions: QuizQuestion[];
  created_at: string;
}

export interface OpenEndedEvaluation {
  score: number;
  what_you_understood: string[];
  concepts_covered: string[];
  missing_concepts: string[];
  feedback: string;
  suggested_action: string;
  reasoning_quality: string;
  confidence: number;
}

export interface QuestionResultItem {
  question_id: string;
  question: string;
  type: string;
  user_answer: string;
  correct_answer?: string;
  is_correct?: boolean;
  explanation?: string;
  evaluation?: OpenEndedEvaluation;
}

export interface QuizAttemptResponse {
  id: string;
  quiz_id: string;
  score: number;
  question_results: QuestionResultItem[];
  overall_feedback: string;
  created_at: string;
}

export interface ConceptMasteryItem {
  concept_id: string;
  concept_name: string;
  score: number;
  status: 'improving' | 'stable' | 'attention';
  assessment_count: number;
  mistake_count: number;
  last_practiced_at?: string;
}

export interface GrowthItem {
  concept_id: string;
  concept_name: string;
  previous_score: number;
  current_score: number;
  trend: 'improving' | 'stable' | 'attention';
  change: number;
}

export interface MasterySummaryResponse {
  overall_mastery: number;
  concepts: ConceptMasteryItem[];
  growth: GrowthItem[];
}

export interface Recommendation {
  id: string;
  project_id: string;
  concept_id?: string;
  action: string;
  reason: string;
  priority: 'high' | 'medium' | 'low';
  is_completed: boolean;
  created_at: string;
}

export interface ProjectAnalytics {
  project_id: string;
  learning_goal?: string;
  total_materials: number;
  total_chunks: number;
  overall_mastery: number;
  quizzes_taken: number;
  average_quiz_score: number;
  tutor_messages_count: number;
  concept_scores: { name: string; score: number; status: string }[];
  recent_events: { type: string; timestamp: string; payload: any }[];
}

export interface GlobalAnalytics {
  total_spaces: number;
  total_projects: number;
  total_materials: number;
  total_quizzes_completed: number;
  average_platform_score: number;
  active_streak_days: number;
  recent_activity: { type: string; timestamp: string; payload: any }[];
}

export interface AdminOverview {
  total_users: number;
  total_spaces: number;
  total_projects: number;
  total_materials: number;
  total_quizzes: number;
  total_ai_requests: number;
  total_ai_cost_usd: number;
  failed_ai_requests: number;
  active_background_jobs: number;
  failed_background_jobs: number;
}

export interface AIUsageItem {
  id: string;
  feature: string;
  model: string;
  latency_ms: number;
  input_tokens: number;
  output_tokens: number;
  estimated_cost_usd: number;
  success: boolean;
  error_message?: string;
  created_at: string;
}

export interface BackgroundJobItem {
  id: string;
  job_type: string;
  status: 'QUEUED' | 'PROCESSING' | 'READY' | 'FAILED';
  attempts: number;
  max_attempts: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
}
