import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { api } from '../api/client';
import { GlobalAnalytics, Space, Project, Recommendation } from '../types';
import { 
  Sparkles, Layers, BookOpen, ArrowRight, CheckCircle2, 
  TrendingUp, Award, Clock, ArrowUpRight, Loader2, Play
} from 'lucide-react';

export const HomePage: React.FC = () => {
  const { user } = useAuth();
  const [analytics, setAnalytics] = useState<GlobalAnalytics | null>(null);
  const [spaces, setSpaces] = useState<Space[]>([]);
  const [recentProjects, setRecentProjects] = useState<Project[]>([]);
  const [topRecommendation, setTopRecommendation] = useState<Recommendation | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [stats, spaceList] = await Promise.all([
          api.getGlobalAnalytics(),
          api.listSpaces(),
        ]);
        setAnalytics(stats);
        setSpaces(spaceList);

        // Fetch projects from first space if available
        if (spaceList.length > 0) {
          const projs = await api.listSpaceProjects(spaceList[0].id);
          setRecentProjects(projs);
          if (projs.length > 0) {
            const recs = await api.getRecommendations(projs[0].id);
            if (recs.length > 0) {
              setTopRecommendation(recs[0]);
            }
          }
        }
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Welcome & Primary Action Banner */}
      <div className="rounded-2xl border border-slate-800 bg-gradient-to-r from-slate-900 via-indigo-950/30 to-slate-900 p-6 sm:p-8">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-flex items-center gap-2 rounded-full bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-400 border border-indigo-500/20">
              <Sparkles className="h-3.5 w-3.5" />
              <span>Welcome back, {user?.full_name}</span>
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
              Continue Your Learning Journey
            </h1>
            <p className="text-sm text-slate-400 max-w-xl">
              AI.Prof tracks your concept mastery, pinpoints knowledge gaps, and provides grounded tutoring directly from your study materials.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <Link
              to="/spaces"
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-600/30 hover:bg-indigo-500 transition-all"
            >
              <Layers className="h-4 w-4" />
              Explore Spaces
            </Link>
          </div>
        </div>
      </div>

      {/* "What Should I Do Next?" Recommendation Box */}
      {topRecommendation && !topRecommendation.is_completed && (
        <div className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="rounded bg-amber-500/20 px-2 py-0.5 text-[11px] font-bold text-amber-300 uppercase tracking-wide border border-amber-500/30">
                  Recommended Next Action
                </span>
                <span className="text-xs text-slate-400">Priority: {topRecommendation.priority}</span>
              </div>
              <h3 className="text-base font-semibold text-white">{topRecommendation.action}</h3>
              <p className="text-xs text-slate-300">{topRecommendation.reason}</p>
            </div>

            {recentProjects.length > 0 && (
              <Link
                to={`/projects/${topRecommendation.project_id}`}
                className="shrink-0 inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-xs font-semibold text-slate-950 hover:bg-amber-400 transition-colors"
              >
                <Play className="h-3.5 w-3.5 fill-current" />
                Take Action
              </Link>
            )}
          </div>
        </div>
      )}

      {/* Metrics Row: "How am I doing?" */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Active Spaces</span>
            <Layers className="h-4 w-4 text-indigo-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-white">{analytics?.total_spaces ?? spaces.length}</p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Total Projects</span>
            <BookOpen className="h-4 w-4 text-sky-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-white">{analytics?.total_projects ?? recentProjects.length}</p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Quizzes Completed</span>
            <Award className="h-4 w-4 text-emerald-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-white">{analytics?.total_quizzes_completed ?? 0}</p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Avg Platform Score</span>
            <TrendingUp className="h-4 w-4 text-violet-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-white">
            {analytics?.average_platform_score ? `${analytics.average_platform_score}%` : '—'}
          </p>
        </div>
      </div>

      {/* Recent Projects Section: "Where was I?" */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Clock className="h-4 w-4 text-indigo-400" />
            Recent Projects
          </h2>
          <Link to="/spaces" className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1">
            View All Spaces <ArrowRight className="h-3 w-3" />
          </Link>
        </div>

        {recentProjects.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/30 p-8 text-center space-y-3">
            <BookOpen className="mx-auto h-8 w-8 text-slate-600" />
            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-slate-300">No Projects Found</h3>
              <p className="text-xs text-slate-500">Create a space or click "Seed DBMS Demo" in the top bar to jump in immediately.</p>
            </div>
            <Link
              to="/spaces"
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500"
            >
              Go to Spaces
            </Link>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {recentProjects.map((p) => (
              <Link
                key={p.id}
                to={`/projects/${p.id}`}
                className="group rounded-xl border border-slate-800 bg-slate-900/50 p-5 hover:border-indigo-500/50 hover:bg-slate-900/80 transition-all flex flex-col justify-between"
              >
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-[10px] font-semibold text-slate-400">
                      {p.material_count} Materials
                    </span>
                    <ArrowUpRight className="h-4 w-4 text-slate-600 group-hover:text-indigo-400 transition-colors" />
                  </div>
                  <h3 className="font-semibold text-white group-hover:text-indigo-300 transition-colors">{p.name}</h3>
                  <p className="text-xs text-slate-400 line-clamp-2">
                    {p.learning_goal || p.description || 'No learning goal specified.'}
                  </p>
                </div>
                <div className="mt-4 pt-3 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-500">
                  <span>{p.concept_count} Concepts</span>
                  <span className="text-indigo-400 group-hover:underline">Open Workspace &rarr;</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
