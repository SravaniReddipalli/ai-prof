import React, { useState, useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { Space, Project } from '../types';
import { 
  Folder, BookOpen, Plus, ArrowLeft, ArrowRight, Loader2, 
  X, AlertCircle, Trash2, Target 
} from 'lucide-react';

export const SpaceDetailPage: React.FC = () => {
  const { spaceId } = useParams<{ spaceId: string }>();
  const navigate = useNavigate();
  const [space, setSpace] = useState<Space | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  
  const [showModal, setShowModal] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [learningGoal, setLearningGoal] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    if (!spaceId) return;
    try {
      const [spaceData, projs] = await Promise.all([
        api.getSpace(spaceId),
        api.listSpaceProjects(spaceId),
      ]);
      setSpace(spaceData);
      setProjects(projs);
    } catch (err) {
      console.error('Failed to load space projects:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [spaceId]);

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!spaceId) return;
    setError(null);
    setCreating(true);
    try {
      const newProj = await api.createProject(spaceId, {
        name,
        description,
        learning_goal: learningGoal,
      });
      setName('');
      setDescription('');
      setLearningGoal('');
      setShowModal(false);
      navigate(`/projects/${newProj.id}`);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to create Project');
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteSpace = async () => {
    if (!spaceId || !window.confirm('Are you sure you want to delete this Space and all associated projects?')) return;
    try {
      await api.deleteSpace(spaceId);
      navigate('/spaces');
    } catch (err) {
      alert('Failed to delete space');
    }
  };

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  if (!space) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-400">Space not found.</p>
        <Link to="/spaces" className="text-indigo-400 hover:underline mt-2 inline-block">Return to Spaces</Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb & Navigation */}
      <div className="flex items-center gap-2 text-xs text-slate-400">
        <Link to="/spaces" className="hover:text-white flex items-center gap-1">
          <ArrowLeft className="h-3.5 w-3.5" />
          Spaces
        </Link>
        <span>/</span>
        <span className="text-slate-200 font-semibold">{space.name}</span>
      </div>

      {/* Header Info */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
              <Folder className="h-4 w-4" />
            </div>
            <h1 className="text-2xl font-bold text-white">{space.name}</h1>
          </div>
          <p className="text-xs text-slate-400 max-w-2xl">{space.description || 'No description provided.'}</p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleDeleteSpace}
            className="rounded-lg p-2 text-slate-500 hover:text-rose-400 hover:bg-rose-950/30 transition-colors"
            title="Delete Space"
          >
            <Trash2 className="h-4 w-4" />
          </button>
          <button
            onClick={() => setShowModal(true)}
            className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-500 transition-colors shadow-md shadow-indigo-600/20"
          >
            <Plus className="h-4 w-4" />
            Create Project
          </button>
        </div>
      </div>

      {/* Projects Grid */}
      <div className="space-y-4">
        <h2 className="text-base font-bold text-white flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-indigo-400" />
          Learning Projects in this Space
        </h2>

        {projects.length === 0 ? (
          <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/30 p-10 text-center space-y-3">
            <BookOpen className="mx-auto h-8 w-8 text-slate-600" />
            <h3 className="text-sm font-semibold text-slate-300">No Projects in this Space Yet</h3>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              Create a focused learning project (e.g. "Relational Databases", "Neural Networks") to begin uploading materials and learning.
            </p>
            <button
              onClick={() => setShowModal(true)}
              className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500"
            >
              <Plus className="h-3.5 w-3.5" />
              New Project
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {projects.map((p) => (
              <Link
                key={p.id}
                to={`/projects/${p.id}`}
                className="group rounded-xl border border-slate-800 bg-slate-900/60 p-5 hover:border-indigo-500/50 hover:bg-slate-900 transition-all flex flex-col justify-between"
              >
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="rounded bg-slate-800 px-2 py-0.5 text-[11px] font-semibold text-slate-300">
                      {p.material_count} Materials
                    </span>
                    <span className="text-[11px] text-slate-500">{p.concept_count} Concepts</span>
                  </div>

                  <div>
                    <h3 className="text-base font-bold text-white group-hover:text-indigo-300 transition-colors">{p.name}</h3>
                    <p className="text-xs text-slate-400 mt-1 line-clamp-2">{p.description || 'No description'}</p>
                  </div>

                  {p.learning_goal && (
                    <div className="rounded-lg bg-slate-800/60 p-2.5 text-[11px] text-slate-300 border border-slate-800">
                      <div className="flex items-center gap-1 text-indigo-400 font-semibold mb-0.5">
                        <Target className="h-3 w-3" />
                        <span>Goal:</span>
                      </div>
                      <p className="line-clamp-2">{p.learning_goal}</p>
                    </div>
                  )}
                </div>

                <div className="mt-4 pt-3 border-t border-slate-800 flex items-center justify-between text-xs text-indigo-400 font-semibold group-hover:underline">
                  <span>Enter Learning Workspace</span>
                  <ArrowRight className="h-3.5 w-3.5 group-hover:translate-x-1 transition-transform" />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>

      {/* Create Project Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">Create New Project</h2>
              <button onClick={() => setShowModal(false)} className="text-slate-400 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>

            {error && (
              <div className="flex items-center gap-2 rounded-lg bg-rose-950/50 border border-rose-500/30 p-2.5 text-xs text-rose-300">
                <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleCreateProject} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Project Name</label>
                <input
                  type="text"
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="e.g. Relational Normalization & Transactions"
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Description (Optional)</label>
                <textarea
                  rows={2}
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Brief overview of topic..."
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-300 mb-1">Learning Goal (Important for Tutor)</label>
                <textarea
                  rows={2}
                  value={learningGoal}
                  onChange={(e) => setLearningGoal(e.target.value)}
                  placeholder="e.g. Master 1NF-3NF decomposition and transaction ACID properties for exam preparation"
                  className="w-full rounded-lg border border-slate-700 bg-slate-800 px-3 py-2 text-sm text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="rounded-lg px-4 py-2 text-xs font-semibold text-slate-400 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500 disabled:opacity-50"
                >
                  {creating && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Create & Launch Workspace
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
