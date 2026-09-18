import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../contexts/AuthContext';
import { api } from '../../api/client';
import { 
  BookOpen, Compass, Shield, LogOut, Sparkles, CheckCircle2, 
  Layers, ChevronRight, User as UserIcon, Loader2 
} from 'lucide-react';

export const Navbar: React.FC = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [seeding, setSeeding] = useState(false);
  const [seedMessage, setSeedMessage] = useState<string | null>(null);

  const handleSeedDemo = async () => {
    setSeeding(true);
    setSeedMessage(null);
    try {
      const res = await api.seedDemo();
      setSeedMessage('DBMS Demo Workspace Loaded!');
      setTimeout(() => setSeedMessage(null), 3500);
      if (res.project_id) {
        navigate(`/projects/${res.project_id}`);
      } else {
        navigate('/spaces');
      }
    } catch (err: any) {
      setSeedMessage('Failed to seed: ' + (err.response?.data?.detail || err.message));
      setTimeout(() => setSeedMessage(null), 3500);
    } finally {
      setSeeding(false);
    }
  };

  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800 bg-slate-900/90 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Brand */}
        <div className="flex items-center gap-8">
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-indigo-600 text-white shadow-md shadow-indigo-500/20 group-hover:bg-indigo-500 transition-colors">
              <BookOpen className="h-5 w-5" />
            </div>
            <div className="flex flex-col">
              <div className="flex items-center gap-1.5">
                <span className="font-bold text-lg tracking-tight text-white">AI.Prof</span>
                <span className="rounded bg-indigo-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-400 border border-indigo-500/20">
                  STUDY COMPANION
                </span>
              </div>
            </div>
          </Link>

          {/* Navigation Links */}
          <nav className="hidden md:flex items-center gap-1">
            <Link
              to="/"
              className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                location.pathname === '/' 
                  ? 'bg-slate-800 text-white' 
                  : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
              }`}
            >
              <Compass className="h-4 w-4" />
              Dashboard
            </Link>

            <Link
              to="/spaces"
              className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                location.pathname.startsWith('/spaces') 
                  ? 'bg-slate-800 text-white' 
                  : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
              }`}
            >
              <Layers className="h-4 w-4" />
              Spaces & Projects
            </Link>

            {user?.role === 'admin' && (
              <Link
                to="/admin"
                className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                  location.pathname.startsWith('/admin') 
                    ? 'bg-slate-800 text-indigo-400 border border-indigo-500/20' 
                    : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                }`}
              >
                <Shield className="h-4 w-4 text-indigo-400" />
                Admin Dashboard
              </Link>
            )}
          </nav>
        </div>

        {/* Right side actions */}
        <div className="flex items-center gap-3">
          {/* Seed Demo Button */}
          <button
            onClick={handleSeedDemo}
            disabled={seeding}
            className="hidden sm:inline-flex items-center gap-1.5 rounded-lg border border-indigo-500/30 bg-indigo-950/40 px-3 py-1.5 text-xs font-semibold text-indigo-300 hover:bg-indigo-900/50 hover:text-white transition-all disabled:opacity-50 shadow-sm"
            title="Populate complete Database Management Systems demo workspace"
          >
            {seeding ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-400" />
            ) : (
              <Sparkles className="h-3.5 w-3.5 text-indigo-400" />
            )}
            Seed DBMS Demo
          </button>

          {seedMessage && (
            <div className="fixed bottom-4 right-4 z-50 rounded-lg bg-emerald-950/90 border border-emerald-500/40 px-4 py-2.5 text-xs text-emerald-200 shadow-xl flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
              {seedMessage}
            </div>
          )}

          {/* User Profile & Logout */}
          {user ? (
            <div className="flex items-center gap-3 pl-2 border-l border-slate-800">
              <div className="hidden sm:flex flex-col text-right">
                <span className="text-xs font-semibold text-slate-200">{user.full_name}</span>
                <span className="text-[11px] text-slate-400 capitalize">{user.role}</span>
              </div>
              <button
                onClick={logout}
                className="rounded-lg p-2 text-slate-400 hover:bg-slate-800 hover:text-rose-400 transition-colors"
                title="Sign Out"
              >
                <LogOut className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <Link
              to="/login"
              className="rounded-lg bg-indigo-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-indigo-500 transition-colors"
            >
              Sign In
            </Link>
          )}
        </div>
      </div>
    </header>
  );
};
