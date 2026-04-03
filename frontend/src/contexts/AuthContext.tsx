import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { User } from '../types';
import api from '../api/client';

interface AuthContextValue {
  token: string | null;
  user: User | null;
  isAdmin: boolean;
  pendingBlocked: boolean;
  loginAdmin: (username: string, password: string) => Promise<void>;
  loginTelegram: (payload: Record<string, string | number | undefined>) => Promise<void>;
  updateMyName: (name: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('token'));
  const [isAdmin, setIsAdmin] = useState(() => localStorage.getItem('isAdmin') === '1');
  const [user, setUser] = useState<User | null>(null);
  const [pendingBlocked, setPendingBlocked] = useState(() => localStorage.getItem('pendingBlocked') === '1');

  const logout = useCallback(() => {
    localStorage.removeItem('token');
    localStorage.removeItem('isAdmin');
    localStorage.removeItem('pendingBlocked');
    setToken(null);
    setUser(null);
    setIsAdmin(false);
    setPendingBlocked(false);
  }, []);

  useEffect(() => {
    if (token && !isAdmin) {
      api
        .get<User>('/auth/me')
        .then((r: { data: User }) => setUser(r.data))
        .catch((err: unknown) => {
          const status = (err as { response?: { status?: number } })?.response?.status;
          if (status === 403) {
            localStorage.removeItem('token');
            localStorage.removeItem('isAdmin');
            localStorage.setItem('pendingBlocked', '1');
            setToken(null);
            setUser(null);
            setIsAdmin(false);
            setPendingBlocked(true);
            return;
          }
          logout();
        });
    }
  }, [token, isAdmin, logout]);

  const loginAdmin = async (username: string, password: string) => {
    const { data } = await api.post<{ access_token: string }>('/auth/admin/login', {
      username,
      password,
    });
    localStorage.setItem('token', data.access_token);
    localStorage.setItem('isAdmin', '1');
    localStorage.removeItem('pendingBlocked');
    setToken(data.access_token);
    setIsAdmin(true);
    setPendingBlocked(false);
  };

  const loginTelegram = async (payload: Record<string, string | number | undefined>) => {
    const { data } = await api.post<{ access_token: string }>('/auth/telegram/login', payload);
    localStorage.setItem('token', data.access_token);
    localStorage.removeItem('isAdmin');
    localStorage.removeItem('pendingBlocked');
    setToken(data.access_token);
    setIsAdmin(false);
    setPendingBlocked(false);
    try {
      const me = await api.get<User>('/auth/me');
      setUser(me.data);
    } catch (err: unknown) {
      const status = (err as { response?: { status?: number } })?.response?.status;
      if (status === 403) {
        localStorage.removeItem('token');
        localStorage.setItem('pendingBlocked', '1');
        setToken(null);
        setUser(null);
        setPendingBlocked(true);
        return;
      }
      throw err;
    }
  };

  const updateMyName = async (name: string) => {
    const { data } = await api.patch<User>('/auth/me', { name });
    setUser(data);
  };

  return (
    <AuthContext.Provider
      value={{ token, user, isAdmin, pendingBlocked, loginAdmin, loginTelegram, updateMyName, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be inside AuthProvider');
  return ctx;
}
