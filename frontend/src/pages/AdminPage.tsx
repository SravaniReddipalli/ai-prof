import React, { useState, useEffect } from 'react';
import { api } from '../api/client';
import { 
  AdminOverview, User, AIUsageItem, BackgroundJobItem 
} from '../types';
import { 
  Shield, Users, Cpu, Activity, AlertCircle, RefreshCw, 
  CheckCircle2, XCircle, Clock, Search, DollarSign, Layers, Loader2 
} from 'lucide-react';

export const AdminPage: React.FC = () => {
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'users' | 'ai' | 'jobs'>('overview');
  const [loading, setLoading] = useState(true);

  const [users, setUsers] = useState<User[]>([]);
  const [aiUsage, setAiUsage] = useState<AIUsageItem[]>([]);
  const [jobs, setJobs] = useState<BackgroundJobItem[]>([]);

  // User inspect modal
  const [inspectUser, setInspectUser] = useState<any | null>(null);
  const [inspectLoading, setInspectLoading] = useState(false);

  const loadData = async () => {
    setLoading(true);
    try {
      const [ov, uList, aiList, jobList] = await Promise.all([
        api.getAdminOverview(),
        api.listUsers(),
        api.getAIUsage(),
        api.getJobs(),
      ]);
      setOverview(ov);
      setUsers(uList);
      setAiUsage(aiList);
      setJobs(jobList);
    } catch (err) {
      console.error('Failed to load admin data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleInspect = async (userId: string) => {
    setInspectLoading(true);
    try {
      const detail = await api.inspectUser(userId);
      setInspectUser(detail);
    } catch (err) {
      alert('Failed to inspect user');
    } finally {
      setInspectLoading(false);
    }
  };

  const handleRetryJob = async (jobId: string) => {
    try {
      await api.retryJob(jobId);
      alert('Job successfully requeued');
      const updatedJobs = await api.getJobs();
      setJobs(updatedJobs);
    } catch (err) {
      alert('Failed to retry job');
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-white flex items-center gap-2">
            <Shield className="h-6 w-6 text-indigo-500" />
            Admin Operations & Observability
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Platform-wide visibility into user learning journeys, AI usage costs, and background jobs.
          </p>
        </div>

        <button
          onClick={loadData}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-800 px-3.5 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-700 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh Metrics
        </button>
      </div>

      {/* Overview Stat Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Total Users</span>
            <Users className="h-4 w-4 text-indigo-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-white">{overview?.total_users ?? 0}</p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Total AI Requests</span>
            <Cpu className="h-4 w-4 text-sky-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-white">{overview?.total_ai_requests ?? 0}</p>
          <span className="text-[10px] text-slate-500">{overview?.failed_ai_requests ?? 0} failures</span>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Estimated AI Cost</span>
            <DollarSign className="h-4 w-4 text-emerald-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-emerald-400">${(overview?.total_ai_cost_usd ?? 0).toFixed(4)}</p>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-4">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">Active / Failed Jobs</span>
            <Activity className="h-4 w-4 text-amber-400" />
          </div>
          <p className="mt-2 text-2xl font-bold text-white">
            {overview?.active_background_jobs ?? 0} / <span className="text-rose-400">{overview?.failed_background_jobs ?? 0}</span>
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-800 gap-2">
        <button
          onClick={() => setActiveTab('overview')}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === 'overview' ? 'border-indigo-500 text-white' : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          Platform Overview
        </button>
        <button
          onClick={() => setActiveTab('users')}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === 'users' ? 'border-indigo-500 text-white' : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          User Journey Inspector ({users.length})
        </button>
        <button
          onClick={() => setActiveTab('ai')}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === 'ai' ? 'border-indigo-500 text-white' : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          AI Observability ({aiUsage.length})
        </button>
        <button
          onClick={() => setActiveTab('jobs')}
          className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${
            activeTab === 'jobs' ? 'border-indigo-500 text-white' : 'border-transparent text-slate-400 hover:text-slate-300'
          }`}
        >
          Background Jobs ({jobs.length})
        </button>
      </div>

      {/* TAB: USERS */}
      {activeTab === 'users' && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-800 font-bold text-xs text-slate-300">Registered Users</div>
          <div className="divide-y divide-slate-800">
            {users.map(u => (
              <div key={u.id} className="p-4 flex items-center justify-between gap-4">
                <div>
                  <h4 className="text-xs font-bold text-white">{u.full_name} ({u.email})</h4>
                  <span className="text-[11px] text-slate-500 capitalize">Role: {u.role} • Registered: {new Date(u.created_at).toLocaleDateString()}</span>
                </div>
                <button
                  onClick={() => handleInspect(u.id)}
                  className="rounded bg-indigo-600/20 border border-indigo-500/30 px-3 py-1 text-xs font-semibold text-indigo-300 hover:bg-indigo-600/30"
                >
                  Inspect Journey &rarr;
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB: AI OBSERVABILITY */}
      {activeTab === 'ai' && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 bg-slate-950/60 text-slate-400 uppercase text-[10px]">
              <tr>
                <th className="p-3">Feature</th>
                <th className="p-3">Model</th>
                <th className="p-3">Latency</th>
                <th className="p-3">Tokens (In/Out)</th>
                <th className="p-3">Est. Cost</th>
                <th className="p-3">Status</th>
                <th className="p-3">Time</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {aiUsage.map(l => (
                <tr key={l.id} className="hover:bg-slate-800/30">
                  <td className="p-3 font-semibold text-white">{l.feature}</td>
                  <td className="p-3 text-slate-400">{l.model}</td>
                  <td className="p-3 text-slate-300">{l.latency_ms} ms</td>
                  <td className="p-3 text-slate-400">{l.input_tokens} / {l.output_tokens}</td>
                  <td className="p-3 text-emerald-400 font-mono">${l.estimated_cost_usd.toFixed(5)}</td>
                  <td className="p-3">
                    {l.success ? (
                      <span className="inline-flex items-center gap-1 text-emerald-400 text-[11px]">
                        <CheckCircle2 className="h-3 w-3" /> OK
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-rose-400 text-[11px]" title={l.error_message || 'Error'}>
                        <XCircle className="h-3 w-3" /> Failed
                      </span>
                    )}
                  </td>
                  <td className="p-3 text-slate-500">{new Date(l.created_at).toLocaleTimeString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* TAB: BACKGROUND JOBS */}
      {activeTab === 'jobs' && (
        <div className="rounded-xl border border-slate-800 bg-slate-900/60 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="border-b border-slate-800 bg-slate-950/60 text-slate-400 uppercase text-[10px]">
              <tr>
                <th className="p-3">Job ID / Type</th>
                <th className="p-3">Status</th>
                <th className="p-3">Attempts</th>
                <th className="p-3">Created</th>
                <th className="p-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {jobs.map(j => (
                <tr key={j.id} className="hover:bg-slate-800/30">
                  <td className="p-3">
                    <span className="font-semibold text-white block">{j.job_type}</span>
                    <span className="text-[10px] text-slate-500 font-mono">{j.id.slice(0, 8)}...</span>
                  </td>
                  <td className="p-3">
                    <span className={`inline-flex items-center gap-1 text-[11px] font-semibold ${
                      j.status === 'READY' ? 'text-emerald-400' : j.status === 'FAILED' ? 'text-rose-400' : 'text-amber-400'
                    }`}>
                      {j.status}
                    </span>
                    {j.error_message && <p className="text-[10px] text-rose-400 max-w-xs truncate">{j.error_message}</p>}
                  </td>
                  <td className="p-3 text-slate-400">{j.attempts} / {j.max_attempts}</td>
                  <td className="p-3 text-slate-500">{new Date(j.created_at).toLocaleTimeString()}</td>
                  <td className="p-3">
                    {j.status === 'FAILED' && (
                      <button
                        onClick={() => handleRetryJob(j.id)}
                        className="rounded bg-indigo-600 px-2.5 py-1 text-[11px] font-semibold text-white hover:bg-indigo-500"
                      >
                        Re-queue
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* User Inspect Modal */}
      {inspectUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <div>
                <h3 className="text-base font-bold text-white">{inspectUser.user.full_name}</h3>
                <span className="text-xs text-slate-400">{inspectUser.user.email}</span>
              </div>
              <button onClick={() => setInspectUser(null)} className="text-slate-400 hover:text-white">✕</button>
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs">
              <div className="p-3 rounded bg-slate-800/60">
                <span className="text-slate-400 block">Spaces Owned:</span>
                <span className="text-base font-bold text-white">{inspectUser.spaces_count}</span>
              </div>
              <div className="p-3 rounded bg-slate-800/60">
                <span className="text-slate-400 block">Projects:</span>
                <span className="text-base font-bold text-white">{inspectUser.projects_count}</span>
              </div>
              <div className="p-3 rounded bg-slate-800/60">
                <span className="text-slate-400 block">Quizzes Taken:</span>
                <span className="text-base font-bold text-emerald-400">{inspectUser.quizzes_count}</span>
              </div>
              <div className="p-3 rounded bg-slate-800/60">
                <span className="text-slate-400 block">Total AI Cost:</span>
                <span className="text-base font-bold text-sky-400">${inspectUser.estimated_ai_cost_usd.toFixed(4)}</span>
              </div>
            </div>

            <div className="space-y-2">
              <span className="text-xs font-bold text-slate-300 block">Recent Activity Log:</span>
              <div className="max-h-40 overflow-y-auto space-y-1.5 text-[11px] divide-y divide-slate-800">
                {inspectUser.recent_activity.map((a: any, i: number) => (
                  <div key={i} className="pt-1.5 flex justify-between text-slate-400">
                    <span className="text-indigo-300 font-semibold">{a.type}</span>
                    <span>{new Date(a.timestamp).toLocaleTimeString()}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
