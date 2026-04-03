import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import api from '../api/client';

export default function Navbar() {
  const { user, isAdmin, logout } = useAuth();
  const { data: appName = 'Team Scheduler' } = useQuery({
    queryKey: ['app-name'],
    queryFn: () => api.get<{ app_name: string }>('/admin/settings/app-name').then((r) => r.data.app_name),
    staleTime: 30_000,
  });
//  const [appName, setAppName] = useState('Team Scheduler');

  useEffect(() => {
    document.title = appName;
  }, [appName]);

  const label = isAdmin
    ? 'Administrateur'
    : user?.role === 'manager'
      ? `Manager — ${user.name}`
      : user?.name ?? '';

  return (
    <nav className="bg-indigo-700 text-white px-6 py-3 flex items-center justify-between shadow-md">
      <span className="font-bold text-lg tracking-tight">{appName}</span>
      <div className="flex items-center gap-4 text-sm">
        <span className="opacity-75">{label}</span>
        {!isAdmin && user && (
          <Link
            to="/profile"
            className="px-3 py-1 bg-indigo-500 hover:bg-indigo-400 rounded-lg transition font-medium"
          >
            Profil
          </Link>
        )}
        <button
          onClick={logout}
          className="px-3 py-1 bg-indigo-500 hover:bg-indigo-400 rounded-lg transition font-medium"
        >
          Déconnexion
        </button>
      </div>
    </nav>
  );
}
