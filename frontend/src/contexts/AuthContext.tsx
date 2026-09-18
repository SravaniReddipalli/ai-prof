import React, { createContext, useContext, useState, useEffect } from 'react';
import { User } from '../types';
import { api } from '../api/client';

interface AuthContextType {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
  demoLogin: (role: 'admin' | 'student') => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('aiprof_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const initAuth = async () => {
      const storedToken = localStorage.getItem('aiprof_token');
      if (storedToken) {
        try {
          const profile = await api.getMe();
          setUser(profile);
          setToken(storedToken);
        } catch (err) {
          localStorage.removeItem('aiprof_token');
          localStorage.removeItem('aiprof_user');
          setUser(null);
          setToken(null);
        }
      }
      setIsLoading(false);
    };
    initAuth();
  }, []);

  const login = async (email: string, password: string) => {
    const res = await api.login({ email, password });
    localStorage.setItem('aiprof_token', res.access_token);
    localStorage.setItem('aiprof_user', JSON.stringify(res.user));
    setToken(res.access_token);
    setUser(res.user);
  };

  const register = async (email: string, password: string, fullName: string) => {
    const res = await api.register({ email, password, full_name: fullName });
    localStorage.setItem('aiprof_token', res.access_token);
    localStorage.setItem('aiprof_user', JSON.stringify(res.user));
    setToken(res.access_token);
    setUser(res.user);
  };

  const logout = () => {
    localStorage.removeItem('aiprof_token');
    localStorage.removeItem('aiprof_user');
    setToken(null);
    setUser(null);
  };

  const demoLogin = async (role: 'admin' | 'student') => {
    const email = role === 'admin' ? 'admin@aiprof.io' : 'student@aiprof.io';
    const password = role === 'admin' ? 'admin123' : 'student123';
    try {
      await login(email, password);
    } catch (err) {
      // If user doesn't exist yet, seed demo data first then login
      try {
        await api.seedDemo();
        await login(email, password);
      } catch (seedErr) {
        // Fallback auto-registration
        await register(email, password, role === 'admin' ? 'Prof. Alan Turing' : 'Alex River');
      }
    }
  };

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, register, logout, demoLogin }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
