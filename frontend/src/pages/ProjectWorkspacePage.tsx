import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import { api } from '../api/client';
import { 
  Project, Material, MessageHistoryItem, Quiz, QuizAttemptResponse,
  MasterySummaryResponse, Recommendation, ProjectAnalytics, Citation
} from '../types';
import { 
  BookOpen, FileText, MessageSquare, Award, TrendingUp, BarChart2,
  UploadCloud, Send, Sparkles, CheckCircle2, XCircle, Clock, AlertTriangle,
  ArrowLeft, RefreshCw, Trash2, ArrowUpRight, HelpCircle, Check, Play,
  ChevronRight, Lightbulb, Loader2
} from 'lucide-react';

export const ProjectWorkspacePage: React.FC = () => {
  const { projectId } = useParams<{ projectId: string }>();
  const [project, setProject] = useState<Project | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'materials' | 'tutor' | 'quiz' | 'mastery' | 'analytics'>('overview');
  const [loading, setLoading] = useState(true);

  // Tab states
  const [materials, setMaterials] = useState<Material[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  // Tutor state
  const [messages, setMessages] = useState<MessageHistoryItem[]>([]);
  const [inputMsg, setInputMsg] = useState('');
  const [sendingMsg, setSendingMsg] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Quiz state
  const [activeQuiz, setActiveQuiz] = useState<Quiz | null>(null);
  const [generatingQuiz, setGeneratingQuiz] = useState(false);
  const [userAnswers, setUserAnswers] = useState<Record<string, string>>({});
  const [quizAttempt, setQuizAttempt] = useState<QuizAttemptResponse | null>(null);
  const [submittingQuiz, setSubmittingQuiz] = useState(false);

  // Mastery & Recommendations
  const [masteryData, setMasteryData] = useState<MasterySummaryResponse | null>(null);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [analytics, setAnalytics] = useState<ProjectAnalytics | null>(null);

  // Initial load
  const loadProjectData = async () => {
    if (!projectId) return;
    try {
      const [proj, mats, recs, mastery, analyticsData] = await Promise.all([
        api.getProject(projectId),
        api.listMaterials(projectId),
        api.getRecommendations(projectId),
        api.getMastery(projectId),
        api.getProjectAnalytics(projectId),
      ]);
      setProject(proj);
      setMaterials(mats);
      setRecommendations(recs);
      setMasteryData(mastery);
      setAnalytics(analyticsData);
    } catch (err) {
      console.error('Failed to load project workspace:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProjectData();
  }, [projectId]);

  // Polling for processing materials
  useEffect(() => {
    const hasPending = materials.some(m => m.status === 'QUEUED' || m.status === 'PROCESSING');
    if (!hasPending || !projectId) return;

    const interval = setInterval(async () => {
      try {
        const updated = await api.listMaterials(projectId);
        setMaterials(updated);
        // Refresh mastery & project stats if material turned READY
        const anyReadyNow = updated.some(m => m.status === 'READY');
        if (anyReadyNow) {
          const [m, a] = await Promise.all([api.getMastery(projectId), api.getProjectAnalytics(projectId)]);
          setMasteryData(m);
          setAnalytics(a);
        }
      } catch (err) {
        console.error('Material status poll error:', err);
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [materials, projectId]);

  // Load tutor messages when tutor tab is opened
  useEffect(() => {
    if (activeTab === 'tutor' && projectId) {
      api.getTutorHistory(projectId)
        .then(setMessages)
        .catch(err => console.error('Tutor history error:', err));
    }
  }, [activeTab, projectId]);

  useEffect(() => {
    if (activeTab === 'tutor') {
      chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, activeTab]);

  // --- MATERIAL UPLOAD HANDLER ---
  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !projectId) return;
    setUploading(true);
    setUploadError(null);
    try {
      const uploaded = await api.uploadMaterial(projectId, file);
      setMaterials([uploaded, ...materials]);
    } catch (err: any) {
      setUploadError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const handleDeleteMaterial = async (matId: string) => {
    if (!confirm('Are you sure you want to delete this study material?')) return;
    try {
      await api.deleteMaterial(matId);
      setMaterials(materials.filter(m => m.id !== matId));
    } catch (err) {
      alert('Failed to delete material');
    }
  };

  // --- TUTOR MESSAGE SENDER ---
  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMsg.trim() || !projectId || sendingMsg) return;

    const userText = inputMsg;
    setInputMsg('');
    setSendingMsg(true);

    // Optimistic user message
    const tempUserMsg: MessageHistoryItem = {
      id: 'temp-' + Date.now(),
      sender: 'user',
      content: userText,
      is_unsupported: false,
      created_at: new Date().toISOString(),
    };
    setMessages(prev => [...prev, tempUserMsg]);

    try {
      const res = await api.askTutor(projectId, userText);
      const assistantMsg: MessageHistoryItem = {
        id: res.message_id,
        sender: 'assistant',
        content: res.reply,
        citations: res.citations,
        is_unsupported: res.is_unsupported,
        created_at: new Date().toISOString(),
      };
      setMessages(prev => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: MessageHistoryItem = {
        id: 'err-' + Date.now(),
        sender: 'assistant',
        content: 'Error interacting with AI Tutor: ' + (err.response?.data?.detail || err.message),
        is_unsupported: true,
        created_at: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setSendingMsg(false);
    }
  };

  const handleClearChat = async () => {
    if (!projectId || !confirm('Clear tutor conversation history?')) return;
    try {
      await api.clearTutorHistory(projectId);
      setMessages([]);
    } catch (err) {
      alert('Failed to clear history');
    }
  };

  // --- QUIZ HANDLERS ---
  const handleGenerateQuiz = async () => {
    if (!projectId) return;
    setGeneratingQuiz(true);
    setQuizAttempt(null);
    setUserAnswers({});
    try {
      const q = await api.generateQuiz(projectId);
      setActiveQuiz(q);
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to generate quiz');
    } finally {
      setGeneratingQuiz(false);
    }
  };

  const handleSubmitQuiz = async () => {
    if (!activeQuiz) return;
    setSubmittingQuiz(true);
    try {
      const payload = Object.entries(userAnswers).map(([qid, ans]) => ({
        question_id: qid,
        answer: ans,
      }));
      const result = await api.submitQuiz(activeQuiz.id, payload);
      setQuizAttempt(result);

      // Refresh mastery and recommendations
      if (projectId) {
        const [m, recs, a] = await Promise.all([
          api.getMastery(projectId),
          api.getRecommendations(projectId),
          api.getProjectAnalytics(projectId),
        ]);
        setMasteryData(m);
        setRecommendations(recs);
        setAnalytics(a);
      }
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to submit assessment');
    } finally {
      setSubmittingQuiz(false);
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-400">Project workspace not found.</p>
        <Link to="/spaces" className="text-indigo-400 hover:underline mt-2 inline-block">Return to Spaces</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Header & Breadcrumb */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Link to="/spaces" className="hover:text-white">Spaces</Link>
          <span>/</span>
          <Link to={`/spaces/${project.space_id}`} className="hover:text-white">Space Projects</Link>
          <span>/</span>
          <span className="text-slate-200 font-semibold">{project.name}</span>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                <BookOpen className="h-5 w-5" />
              </div>
              <h1 className="text-xl sm:text-2xl font-bold text-white">{project.name}</h1>
            </div>
            {project.learning_goal && (
              <p className="text-xs text-indigo-300 bg-indigo-950/40 border border-indigo-500/20 rounded-md px-2.5 py-1 mt-1 inline-block">
                <strong>Goal:</strong> {project.learning_goal}
              </p>
            )}
          </div>

          <div className="flex items-center gap-4 text-xs">
            <div className="text-right">
              <span className="text-slate-400 block">Overall Mastery</span>
              <span className="text-lg font-bold text-emerald-400">
                {masteryData?.overall_mastery ? `${masteryData.overall_mastery}%` : '0%'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Tabs Navigation Bar */}
      <div className="flex border-b border-slate-800 overflow-x-auto gap-2">
        <button
          onClick={() => setActiveTab('overview')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
            activeTab === 'overview' ? 'border-indigo-500 text-white' : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          <Lightbulb className="h-4 w-4" />
          Overview
        </button>

        <button
          onClick={() => setActiveTab('materials')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
            activeTab === 'materials' ? 'border-indigo-500 text-white' : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          <FileText className="h-4 w-4" />
          Study Materials ({materials.length})
        </button>

        <button
          onClick={() => setActiveTab('tutor')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
            activeTab === 'tutor' ? 'border-indigo-500 text-white' : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          <MessageSquare className="h-4 w-4" />
          AI Tutor
        </button>

        <button
          onClick={() => setActiveTab('quiz')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
            activeTab === 'quiz' ? 'border-indigo-500 text-white' : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          <Award className="h-4 w-4" />
          Adaptive Quiz
        </button>

        <button
          onClick={() => setActiveTab('mastery')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
            activeTab === 'mastery' ? 'border-indigo-500 text-white' : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          <TrendingUp className="h-4 w-4" />
          Mastery & Growth
        </button>

        <button
          onClick={() => setActiveTab('analytics')}
          className={`flex items-center gap-2 px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
            activeTab === 'analytics' ? 'border-indigo-500 text-white' : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          <BarChart2 className="h-4 w-4" />
          Analytics
        </button>
      </div>

      {/* TAB 1: OVERVIEW */}
      {activeTab === 'overview' && (
        <div className="space-y-6">
          {/* Top Recommendation */}
          {recommendations.length > 0 && !recommendations[0].is_completed && (
            <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[10px] font-bold text-amber-300 uppercase tracking-wide border border-amber-500/30">
                      Recommended Next Step
                    </span>
                    <span className="text-xs text-slate-400">Priority: {recommendations[0].priority}</span>
                  </div>
                  <h3 className="text-sm sm:text-base font-semibold text-white">{recommendations[0].action}</h3>
                  <p className="text-xs text-slate-300">{recommendations[0].reason}</p>
                </div>
                <button
                  onClick={() => setActiveTab('quiz')}
                  className="shrink-0 inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-amber-400"
                >
                  <Play className="h-3.5 w-3.5 fill-current" />
                  Practice Now
                </button>
              </div>
            </div>
          )}

          {/* Quick Launch Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div
              onClick={() => setActiveTab('materials')}
              className="cursor-pointer rounded-xl border border-slate-800 bg-slate-900/60 p-4 hover:border-indigo-500/40 hover:bg-slate-900 transition-all space-y-2"
            >
              <div className="flex items-center justify-between">
                <FileText className="h-5 w-5 text-indigo-400" />
                <span className="text-xs text-slate-500">{materials.length} ready</span>
              </div>
              <h3 className="text-sm font-bold text-white">1. Study Materials</h3>
              <p className="text-xs text-slate-400">Upload PDF lecture notes or textbook chapters for extraction.</p>
            </div>

            <div
              onClick={() => setActiveTab('tutor')}
              className="cursor-pointer rounded-xl border border-slate-800 bg-slate-900/60 p-4 hover:border-indigo-500/40 hover:bg-slate-900 transition-all space-y-2"
            >
              <div className="flex items-center justify-between">
                <MessageSquare className="h-5 w-5 text-sky-400" />
                <span className="text-xs text-slate-500">Grounded</span>
              </div>
              <h3 className="text-sm font-bold text-white">2. Ask AI Tutor</h3>
              <p className="text-xs text-slate-400">Ask questions, get page-cited answers, test understanding.</p>
            </div>

            <div
              onClick={() => setActiveTab('quiz')}
              className="cursor-pointer rounded-xl border border-slate-800 bg-slate-900/60 p-4 hover:border-indigo-500/40 hover:bg-slate-900 transition-all space-y-2"
            >
              <div className="flex items-center justify-between">
                <Award className="h-5 w-5 text-emerald-400" />
                <span className="text-xs text-slate-500">Adaptive</span>
              </div>
              <h3 className="text-sm font-bold text-white">3. Take Assessment</h3>
              <p className="text-xs text-slate-400">Target weak concepts with MCQs and AI-evaluated free-text prompts.</p>
            </div>
          </div>

          {/* Concepts Mastery Snapshot */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <TrendingUp className="h-4 w-4 text-indigo-400" />
                Concept Mastery Progress
              </h2>
              <button onClick={() => setActiveTab('mastery')} className="text-xs font-semibold text-indigo-400 hover:underline">
                View Growth Breakdown &rarr;
              </button>
            </div>

            {(!masteryData || masteryData.concepts.length === 0) ? (
              <p className="text-xs text-slate-500 py-4 text-center">No concept mastery recorded yet. Upload materials and complete a quiz to begin tracking.</p>
            ) : (
              <div className="space-y-3">
                {masteryData.concepts.map(c => (
                  <div key={c.concept_id} className="space-y-1">
                    <div className="flex justify-between text-xs">
                      <span className="font-medium text-slate-200">{c.concept_name}</span>
                      <span className="font-semibold text-slate-400">{c.score.toFixed(0)}%</span>
                    </div>
                    <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          c.score >= 75 ? 'bg-emerald-500' : c.score >= 50 ? 'bg-indigo-500' : 'bg-amber-500'
                        }`}
                        style={{ width: `${Math.min(100, Math.max(0, c.score))}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: STUDY MATERIALS */}
      {activeTab === 'materials' && (
        <div className="space-y-6">
          {/* Uploader Box */}
          <div className="rounded-xl border border-dashed border-slate-700 bg-slate-900/40 p-8 text-center space-y-3">
            <UploadCloud className="mx-auto h-10 w-10 text-indigo-400" />
            <div className="space-y-1">
              <h3 className="text-sm font-bold text-white">Upload PDF Study Materials</h3>
              <p className="text-xs text-slate-400">PDFs are extracted, page-referenced, chunked, and embedded into pgvector for the AI Tutor.</p>
            </div>

            {uploadError && (
              <p className="text-xs text-rose-400 bg-rose-950/40 py-1 px-3 rounded inline-block">{uploadError}</p>
            )}

            <label className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 cursor-pointer transition-colors shadow-md">
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
              <span>{uploading ? 'Processing File...' : 'Select PDF Document'}</span>
              <input
                type="file"
                accept=".pdf"
                disabled={uploading}
                onChange={handleFileUpload}
                className="hidden"
              />
            </label>
          </div>

          {/* Materials Table */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
              <h2 className="text-sm font-bold text-white">Uploaded Project Documents</h2>
              <button onClick={loadProjectData} className="text-xs text-slate-400 hover:text-white flex items-center gap-1">
                <RefreshCw className="h-3.5 w-3.5" /> Refresh
              </button>
            </div>

            {materials.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">No documents uploaded yet.</div>
            ) : (
              <div className="divide-y divide-slate-800">
                {materials.map(m => (
                  <div key={m.id} className="px-5 py-3.5 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <FileText className="h-5 w-5 text-indigo-400 shrink-0" />
                      <div>
                        <h4 className="text-xs font-semibold text-white">{m.filename}</h4>
                        <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
                          <span>{m.page_count} Pages</span>
                          <span>•</span>
                          <span>{(m.file_size_bytes / 1024).toFixed(0)} KB</span>
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      {/* Status Badge */}
                      {m.status === 'READY' && (
                        <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-400 border border-emerald-500/20">
                          <CheckCircle2 className="h-3 w-3" /> Ready
                        </span>
                      )}
                      {m.status === 'PROCESSING' && (
                        <span className="inline-flex items-center gap-1 rounded bg-sky-500/10 px-2 py-0.5 text-[11px] font-semibold text-sky-400 border border-sky-500/20">
                          <Loader2 className="h-3 w-3 animate-spin" /> Processing
                        </span>
                      )}
                      {m.status === 'QUEUED' && (
                        <span className="inline-flex items-center gap-1 rounded bg-amber-500/10 px-2 py-0.5 text-[11px] font-semibold text-amber-400 border border-amber-500/20">
                          <Clock className="h-3 w-3" /> Queued
                        </span>
                      )}
                      {m.status === 'FAILED' && (
                        <span className="inline-flex items-center gap-1 rounded bg-rose-500/10 px-2 py-0.5 text-[11px] font-semibold text-rose-400 border border-rose-500/20" title={m.error_message || 'Processing failed'}>
                          <XCircle className="h-3 w-3" /> Failed
                        </span>
                      )}

                      <button
                        onClick={() => handleDeleteMaterial(m.id)}
                        className="text-slate-500 hover:text-rose-400 p-1"
                        title="Delete Material"
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 3: AI TUTOR */}
      {activeTab === 'tutor' && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 flex flex-col h-[650px]">
          {/* Tutor Header */}
          <div className="px-5 py-3 border-b border-slate-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-indigo-400" />
              <span className="text-xs font-bold text-white">Grounded AI Tutor</span>
              <span className="text-[10px] text-slate-500 border border-slate-800 px-1.5 py-0.5 rounded">
                Grounded strictly in project PDFs
              </span>
            </div>
            <button
              onClick={handleClearChat}
              className="text-xs text-slate-500 hover:text-rose-400 flex items-center gap-1 transition-colors"
            >
              <Trash2 className="h-3.5 w-3.5" /> Clear Chat
            </button>
          </div>

          {/* Messages Thread */}
          <div className="flex-1 p-4 overflow-y-auto space-y-4">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-center p-6 space-y-3">
                <MessageSquare className="h-10 w-10 text-slate-700" />
                <h4 className="text-sm font-semibold text-slate-300">How can I help you learn today?</h4>
                <p className="text-xs text-slate-500 max-w-sm">
                  Ask conceptual questions, request explanations, or test ideas. Responses cite exact pages from your uploaded materials.
                </p>
                <div className="flex flex-wrap gap-2 justify-center pt-2">
                  <button
                    onClick={() => setInputMsg("What is 3NF in database normalization?")}
                    className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300 hover:bg-slate-700"
                  >
                    "What is 3NF normalization?"
                  </button>
                  <button
                    onClick={() => setInputMsg("What are the ACID properties in transactions?")}
                    className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300 hover:bg-slate-700"
                  >
                    "Explain ACID properties"
                  </button>
                  <button
                    onClick={() => setInputMsg("What is the capital of France?")}
                    className="rounded-full bg-slate-800 px-3 py-1 text-xs text-amber-300/80 hover:bg-slate-700"
                    title="Demonstrates safe unsupported-question handling"
                  >
                    "What is the capital of France?" (Unsupported Test)
                  </button>
                </div>
              </div>
            ) : (
              messages.map(m => (
                <div
                  key={m.id}
                  className={`flex flex-col ${m.sender === 'user' ? 'items-end' : 'items-start'}`}
                >
                  <div
                    className={`max-w-2xl rounded-2xl px-4 py-3 text-xs sm:text-sm leading-relaxed ${
                      m.sender === 'user'
                        ? 'bg-indigo-600 text-white rounded-br-none'
                        : m.is_unsupported
                        ? 'bg-amber-950/40 border border-amber-500/30 text-amber-200 rounded-bl-none'
                        : 'bg-slate-800 text-slate-200 rounded-bl-none border border-slate-700/50'
                    }`}
                  >
                    {m.is_unsupported && (
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-400 mb-1.5">
                        <AlertTriangle className="h-3.5 w-3.5" />
                        <span>Insufficient Evidence Guardrail</span>
                      </div>
                    )}
                    <p className="whitespace-pre-wrap">{m.content?.replace(/svgSource:/g, "Source:")}</p>

                    {/* Grounded Citation Chips */}
                    {m.citations && m.citations.length > 0 && (
                      <div className="mt-3 pt-2.5 border-t border-slate-700/60 flex flex-wrap gap-2">
                        {m.citations.map((c, i) => {
                          const cleanSource = (c.source || "").replace(/^svgSource:\s*/i, "").replace(/^Source:\s*/i, "").trim();
                          return (
                            <div
                              key={i}
                              className="inline-flex items-center gap-1.5 rounded bg-slate-900/80 border border-indigo-500/30 px-2 py-1 text-[11px] text-indigo-300"
                              title={c.snippet}
                            >
                              <BookOpen className="h-3 w-3 text-indigo-400 shrink-0" aria-hidden="true" focusable="false" />
                              <span>Source: {cleanSource} — Page {c.page}</span>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            {sendingMsg && (
              <div className="flex items-start">
                <div className="rounded-2xl bg-slate-800 px-4 py-3 text-xs text-slate-400 rounded-bl-none flex items-center gap-2">
                  <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-400" />
                  <span>AI Tutor is reasoning and checking project evidence...</span>
                </div>
              </div>
            )}
            <div ref={chatBottomRef} />
          </div>

          {/* Tutor Input Form */}
          <form onSubmit={handleSendMessage} className="p-3 border-t border-slate-800 flex gap-2">
            <input
              type="text"
              value={inputMsg}
              onChange={(e) => setInputMsg(e.target.value)}
              placeholder="Ask a question about your project materials..."
              className="flex-1 rounded-xl border border-slate-700 bg-slate-800 px-4 py-2.5 text-xs sm:text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
            />
            <button
              type="submit"
              disabled={!inputMsg.trim() || sendingMsg}
              className="rounded-xl bg-indigo-600 px-4 py-2.5 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors flex items-center gap-1.5"
            >
              <Send className="h-3.5 w-3.5" />
              <span>Send</span>
            </button>
          </form>
        </div>
      )}

      {/* TAB 4: ADAPTIVE QUIZ & ASSESSMENT */}
      {activeTab === 'quiz' && (
        <div className="space-y-6">
          {!activeQuiz && !quizAttempt && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-8 text-center space-y-4">
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                <Award className="h-6 w-6" />
              </div>
              <div className="space-y-1">
                <h3 className="text-lg font-bold text-white">Adaptive Learning Assessment</h3>
                <p className="text-xs text-slate-400 max-w-md mx-auto">
                  The system analyzes your weak concepts and recent mistakes to generate targeted questions (3 MCQs + 1 Open-Ended question).
                </p>
              </div>
              <button
                onClick={handleGenerateQuiz}
                disabled={generatingQuiz}
                className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-2.5 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 transition-colors shadow-lg shadow-indigo-600/20"
              >
                {generatingQuiz ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                <span>{generatingQuiz ? 'Generating Adaptive Assessment...' : 'Start Adaptive Quiz'}</span>
              </button>
            </div>
          )}

          {/* Active Quiz Form */}
          {activeQuiz && !quizAttempt && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 space-y-6">
              <div className="flex items-center justify-between border-b border-slate-800 pb-4">
                <div>
                  <span className="text-[10px] font-bold text-indigo-400 uppercase tracking-wide">Adaptive Assessment</span>
                  <h2 className="text-base font-bold text-white">{activeQuiz.title}</h2>
                </div>
                <span className="rounded bg-slate-800 px-2.5 py-1 text-xs text-slate-300 font-semibold capitalize">
                  Level: {activeQuiz.difficulty}
                </span>
              </div>

              <div className="space-y-6">
                {activeQuiz.questions.map((q, idx) => (
                  <div key={q.id} className="rounded-lg border border-slate-800 bg-slate-900/90 p-4 space-y-3">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-xs font-bold text-indigo-400">Question {idx + 1} of {activeQuiz.questions.length}</span>
                      <span className="text-[10px] rounded bg-slate-800 px-1.5 py-0.5 text-slate-400 uppercase">{q.type}</span>
                    </div>
                    <p className="text-sm font-semibold text-slate-100">{q.question}</p>

                    {/* MCQ Options */}
                    {q.type === 'mcq' && q.options && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                        {q.options.map((opt, optIdx) => (
                          <button
                            key={optIdx}
                            type="button"
                            onClick={() => setUserAnswers({ ...userAnswers, [q.id]: opt })}
                            className={`p-3 rounded-lg text-left text-xs font-medium border transition-all ${
                              userAnswers[q.id] === opt
                                ? 'border-indigo-500 bg-indigo-950/40 text-white'
                                : 'border-slate-800 bg-slate-800/60 text-slate-300 hover:bg-slate-800'
                            }`}
                          >
                            <span className="mr-2 font-bold text-slate-500">{String.fromCharCode(65 + optIdx)}.</span>
                            {opt}
                          </button>
                        ))}
                      </div>
                    )}

                    {/* Open Ended Textarea */}
                    {q.type === 'open_ended' && (
                      <div className="pt-1">
                        <textarea
                          rows={4}
                          value={userAnswers[q.id] || ''}
                          onChange={(e) => setUserAnswers({ ...userAnswers, [q.id]: e.target.value })}
                          placeholder="Write your explanation in your own words. The AI will evaluate your conceptual understanding and reasoning..."
                          className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => setActiveQuiz(null)}
                  className="rounded-lg px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSubmitQuiz}
                  disabled={submittingQuiz}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-5 py-2.5 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50"
                >
                  {submittingQuiz && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  <span>{submittingQuiz ? 'Evaluating Understanding...' : 'Submit Assessment'}</span>
                </button>
              </div>
            </div>
          )}

          {/* Assessment Evaluation Breakdown View */}
          {quizAttempt && (
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 space-y-6">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
                <div>
                  <span className="text-[10px] font-bold text-emerald-400 uppercase tracking-wide">Assessment Results</span>
                  <h2 className="text-base font-bold text-white">Performance & Understanding Breakdown</h2>
                  <p className="text-xs text-slate-400 mt-0.5">{quizAttempt.overall_feedback}</p>
                </div>
                <div className="text-right">
                  <span className="text-xs text-slate-400 block">Overall Score</span>
                  <span className="text-3xl font-black text-emerald-400">{quizAttempt.score}%</span>
                </div>
              </div>

              {/* Question Feedback Items */}
              <div className="space-y-4">
                {quizAttempt.question_results.map((res, i) => (
                  <div key={i} className="rounded-lg border border-slate-800 bg-slate-900/90 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-400">Question {i + 1} ({res.type.toUpperCase()})</span>
                      {res.is_correct ? (
                        <span className="inline-flex items-center gap-1 text-emerald-400 text-xs font-semibold">
                          <CheckCircle2 className="h-3.5 w-3.5" /> Correct
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 text-rose-400 text-xs font-semibold">
                          <XCircle className="h-3.5 w-3.5" /> Needs Attention
                        </span>
                      )}
                    </div>
                    <p className="text-xs font-semibold text-white">{res.question}</p>

                    <div className="text-xs space-y-1 bg-slate-800/40 p-2.5 rounded border border-slate-800">
                      <p><strong className="text-slate-400">Your Answer:</strong> <span className="text-slate-200">{res.user_answer || 'No answer submitted'}</span></p>
                      {res.correct_answer && <p><strong className="text-emerald-400">Target Concept:</strong> <span className="text-slate-300">{res.correct_answer}</span></p>}
                      {res.explanation && <p><strong className="text-indigo-400">Feedback:</strong> <span className="text-slate-300">{res.explanation}</span></p>}
                    </div>

                    {/* Open-ended detailed evaluation */}
                    {res.evaluation && (
                      <div className="mt-3 p-3 rounded bg-indigo-950/20 border border-indigo-500/20 text-xs space-y-2">
                        <div className="flex justify-between items-center text-indigo-300 font-bold">
                          <span>AI Rubric Evaluation</span>
                          <span>Score: {res.evaluation.score}% (Confidence: {(res.evaluation.confidence * 100).toFixed(0)}%)</span>
                        </div>

                        {res.evaluation.what_you_understood?.length > 0 && (
                          <div>
                            <span className="text-emerald-400 font-semibold block mb-0.5">What you understood:</span>
                            <ul className="list-disc list-inside text-slate-300 pl-1 space-y-0.5">
                              {res.evaluation.what_you_understood.map((item, idx) => (
                                <li key={idx}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {res.evaluation.missing_concepts?.length > 0 && (
                          <div>
                            <span className="text-amber-400 font-semibold block mb-0.5">Missing or incomplete concepts:</span>
                            <ul className="list-disc list-inside text-slate-300 pl-1 space-y-0.5">
                              {res.evaluation.missing_concepts.map((item, idx) => (
                                <li key={idx}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {res.evaluation.suggested_action && (
                          <div className="pt-1 text-slate-300">
                            <strong className="text-indigo-400">Suggested Action:</strong> {res.evaluation.suggested_action}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>

              <div className="flex justify-end gap-3 pt-4 border-t border-slate-800">
                <button
                  onClick={() => { setQuizAttempt(null); setActiveQuiz(null); }}
                  className="rounded-lg bg-indigo-600 px-5 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
                >
                  Complete Assessment & Return
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 5: MASTERY & GROWTH */}
      {activeTab === 'mastery' && (
        <div className="space-y-6">
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
            <h2 className="text-base font-bold text-white flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-indigo-400" />
              Concept Mastery & Growth Analysis
            </h2>
            <p className="text-xs text-slate-400">
              Mastery scores evolve continuously as you complete assessments and practice with the AI Tutor.
            </p>

            {(!masteryData || masteryData.concepts.length === 0) ? (
              <p className="text-xs text-slate-500 py-6 text-center">No concept data available yet. Please complete a quiz.</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                {masteryData.concepts.map(c => {
                  const growthItem = masteryData.growth.find(g => g.concept_id === c.concept_id);
                  return (
                    <div key={c.concept_id} className="rounded-xl border border-slate-800 bg-slate-900/80 p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <h4 className="text-sm font-bold text-white">{c.concept_name}</h4>
                        {/* Status Badge */}
                        {c.status === 'improving' && (
                          <span className="rounded bg-emerald-500/10 px-2 py-0.5 text-[11px] font-bold text-emerald-400 border border-emerald-500/20">
                            Improving ↑
                          </span>
                        )}
                        {c.status === 'stable' && (
                          <span className="rounded bg-sky-500/10 px-2 py-0.5 text-[11px] font-bold text-sky-400 border border-sky-500/20">
                            Stable →
                          </span>
                        )}
                        {c.status === 'attention' && (
                          <span className="rounded bg-amber-500/10 px-2 py-0.5 text-[11px] font-bold text-amber-400 border border-amber-500/20">
                            Needs Attention ⚠️
                          </span>
                        )}
                      </div>

                      <div className="space-y-1">
                        <div className="flex justify-between text-xs text-slate-400">
                          <span>Mastery: {c.score.toFixed(0)}%</span>
                          {growthItem && growthItem.change !== 0 && (
                            <span className={growthItem.change > 0 ? 'text-emerald-400' : 'text-rose-400'}>
                              {growthItem.change > 0 ? `+${growthItem.change}%` : `${growthItem.change}%`} from previous
                            </span>
                          )}
                        </div>
                        <div className="h-2 w-full bg-slate-800 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-500 ${
                              c.score >= 75 ? 'bg-emerald-500' : c.score >= 50 ? 'bg-indigo-500' : 'bg-amber-500'
                            }`}
                            style={{ width: `${Math.min(100, Math.max(0, c.score))}%` }}
                          />
                        </div>
                      </div>

                      <div className="flex justify-between text-[11px] text-slate-500 pt-1 border-t border-slate-800/60">
                        <span>Assessments: {c.assessment_count}</span>
                        <span>Mistakes: {c.mistake_count}</span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 6: ANALYTICS */}
      {activeTab === 'analytics' && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <span className="text-xs text-slate-400">Total Materials</span>
              <p className="mt-1 text-2xl font-bold text-white">{analytics?.total_materials ?? 0}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <span className="text-xs text-slate-400">Vector Chunks</span>
              <p className="mt-1 text-2xl font-bold text-indigo-400">{analytics?.total_chunks ?? 0}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <span className="text-xs text-slate-400">Quizzes Taken</span>
              <p className="mt-1 text-2xl font-bold text-emerald-400">{analytics?.quizzes_taken ?? 0}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
              <span className="text-xs text-slate-400">Tutor Messages</span>
              <p className="mt-1 text-2xl font-bold text-violet-400">{analytics?.tutor_messages_count ?? 0}</p>
            </div>
          </div>

          {/* Recent Events Feed */}
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <Clock className="h-4 w-4 text-indigo-400" />
              Recent Project Activity Feed
            </h2>
            {(!analytics?.recent_events || analytics.recent_events.length === 0) ? (
              <p className="text-xs text-slate-500 py-4 text-center">No learning events recorded yet.</p>
            ) : (
              <div className="divide-y divide-slate-800 text-xs">
                {analytics.recent_events.map((e, idx) => (
                  <div key={idx} className="py-2.5 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className="rounded bg-indigo-500/10 px-2 py-0.5 text-[10px] font-semibold text-indigo-400 border border-indigo-500/20">
                        {e.type}
                      </span>
                      <span className="text-slate-300">{JSON.stringify(e.payload)}</span>
                    </div>
                    <span className="text-[11px] text-slate-500">{new Date(e.timestamp).toLocaleTimeString()}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
