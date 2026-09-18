import axios from 'axios';
import {
  AuthResponse, User, Space, Project, Material, MaterialStatus,
  MessageHistoryItem, TutorResponse, Quiz, QuizAttemptResponse,
  MasterySummaryResponse, Recommendation, ProjectAnalytics,
  GlobalAnalytics, AdminOverview, AIUsageItem, BackgroundJobItem
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL 
  ? `${import.meta.env.VITE_API_BASE_URL}/api`
  : '/api';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach JWT token automatically
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('aiprof_token');
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle unauthorized responses
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('aiprof_token');
      localStorage.removeItem('aiprof_user');
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export const api = {
  // --- AUTH ---
  register: (data: { email: string; password: string; full_name: string }) =>
    apiClient.post<AuthResponse>('/auth/register', data).then((res) => res.data),
  login: (data: { email: string; password: string }) =>
    apiClient.post<AuthResponse>('/auth/login', data).then((res) => res.data),
  getMe: () => apiClient.get<User>('/auth/me').then((res) => res.data),

  // --- SPACES ---
  listSpaces: () => apiClient.get<Space[]>('/spaces').then((res) => res.data),
  createSpace: (data: { name: string; description?: string; icon?: string; color?: string }) =>
    apiClient.post<Space>('/spaces', data).then((res) => res.data),
  getSpace: (id: string) => apiClient.get<Space>(`/spaces/${id}`).then((res) => res.data),
  deleteSpace: (id: string) => apiClient.delete(`/spaces/${id}`),
  listSpaceProjects: (spaceId: string) =>
    apiClient.get<Project[]>(`/spaces/${spaceId}/projects`).then((res) => res.data),
  createProject: (spaceId: string, data: { name: string; description?: string; learning_goal?: string }) =>
    apiClient.post<Project>(`/spaces/${spaceId}/projects`, data).then((res) => res.data),

  // --- PROJECTS ---
  getProject: (projectId: string) => apiClient.get<Project>(`/projects/${projectId}`).then((res) => res.data),
  updateProject: (projectId: string, data: { name?: string; description?: string; learning_goal?: string }) =>
    apiClient.put<Project>(`/projects/${projectId}`, data).then((res) => res.data),
  deleteProject: (projectId: string) => apiClient.delete(`/projects/${projectId}`),

  // --- MATERIALS ---
  uploadMaterial: (projectId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post<Material>(`/projects/${projectId}/materials/upload`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((res) => res.data);
  },
  listMaterials: (projectId: string) =>
    apiClient.get<Material[]>(`/projects/${projectId}/materials`).then((res) => res.data),
  getMaterialStatus: (materialId: string) =>
    apiClient.get<MaterialStatus>(`/materials/${materialId}/status`).then((res) => res.data),
  deleteMaterial: (materialId: string) => apiClient.delete(`/materials/${materialId}`),

  // --- TUTOR ---
  askTutor: (projectId: string, message: string) =>
    apiClient.post<TutorResponse>(`/projects/${projectId}/tutor/chat`, { message }).then((res) => res.data),
  getTutorHistory: (projectId: string) =>
    apiClient.get<MessageHistoryItem[]>(`/projects/${projectId}/tutor/history`).then((res) => res.data),
  clearTutorHistory: (projectId: string) => apiClient.post(`/projects/${projectId}/tutor/clear`),

  // --- LEARNING & QUIZ ---
  generateQuiz: (projectId: string) =>
    apiClient.post<Quiz>(`/projects/${projectId}/quizzes/generate`).then((res) => res.data),
  listQuizzes: (projectId: string) =>
    apiClient.get<Quiz[]>(`/projects/${projectId}/quizzes`).then((res) => res.data),
  getQuiz: (quizId: string) => apiClient.get<Quiz>(`/quizzes/${quizId}`).then((res) => res.data),
  submitQuiz: (quizId: string, answers: { question_id: string; answer: string }[]) =>
    apiClient.post<QuizAttemptResponse>(`/quizzes/${quizId}/submit`, { answers }).then((res) => res.data),
  getMastery: (projectId: string) =>
    apiClient.get<MasterySummaryResponse>(`/projects/${projectId}/mastery`).then((res) => res.data),
  getRecommendations: (projectId: string) =>
    apiClient.get<Recommendation[]>(`/projects/${projectId}/recommendations`).then((res) => res.data),
  completeRecommendation: (recId: string) => apiClient.post(`/recommendations/${recId}/complete`),

  // --- ANALYTICS ---
  getProjectAnalytics: (projectId: string) =>
    apiClient.get<ProjectAnalytics>(`/projects/${projectId}/analytics`).then((res) => res.data),
  getGlobalAnalytics: () =>
    apiClient.get<GlobalAnalytics>('/analytics/global').then((res) => res.data),

  // --- ADMIN ---
  getAdminOverview: () => apiClient.get<AdminOverview>('/admin/overview').then((res) => res.data),
  listUsers: () => apiClient.get<User[]>('/admin/users').then((res) => res.data),
  inspectUser: (userId: string) => apiClient.get<any>(`/admin/users/${userId}`).then((res) => res.data),
  getAIUsage: () => apiClient.get<AIUsageItem[]>('/admin/ai-usage').then((res) => res.data),
  getJobs: () => apiClient.get<BackgroundJobItem[]>('/admin/jobs').then((res) => res.data),
  retryJob: (jobId: string) => apiClient.post(`/admin/jobs/${jobId}/retry`),

  // --- DEMO SEED ---
  seedDemo: () => apiClient.post<{ status: string; message: string; project_id: string }>('/demo/seed').then((res) => res.data),
};
