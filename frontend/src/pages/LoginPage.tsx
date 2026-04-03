import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  auth_date: number;
  hash: string;
}

declare global {
  interface Window {
    onTelegramAuth: (user: TelegramUser) => void;
  }
}

export default function LoginPage() {
  const { loginAdmin, loginTelegram } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const widgetRef = useRef<HTMLDivElement>(null);
  const botName = import.meta.env.VITE_BOT_USERNAME as string | undefined;

  useEffect(() => {
    if (!botName || !widgetRef.current) return;

    window.onTelegramAuth = async (tgUser: TelegramUser) => {
      setLoading(true);
      setError(null);
      try {
        await loginTelegram({
          id: tgUser.id,
          first_name: tgUser.first_name,
          last_name: tgUser.last_name,
          username: tgUser.username,
          auth_date: tgUser.auth_date,
          hash: tgUser.hash,
        });
      } catch {
        setError('Connexion Telegram échouée. Réessaie.');
        setLoading(false);
      }
    };

    const script = document.createElement('script');
    script.src = 'https://telegram.org/js/telegram-widget.js?22';
    script.setAttribute('data-telegram-login', botName);
    script.setAttribute('data-size', 'large');
    script.setAttribute('data-onauth', 'onTelegramAuth(user)');
    script.setAttribute('data-request-access', 'write');
    script.async = true;
    widgetRef.current.appendChild(script);

    const ref = widgetRef.current;
    return () => { ref.replaceChildren(); };
  }, [botName, loginTelegram]);

  const handleAdminLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await loginAdmin(username, password);
    } catch {
      setError('Identifiants incorrects.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50 to-indigo-100 p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 w-full max-w-md">
        <h1 className="text-2xl font-bold text-center text-indigo-700 mb-1">Team Scheduler</h1>
        <p className="text-center text-gray-400 text-sm mb-6">Gestionnaire de tâches d'équipe</p>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 text-red-700 rounded-lg text-sm">
            {error}
          </div>
        )}

        {/* Connexion Telegram */}
        <div className="mb-6">
          <p className="text-sm font-medium text-gray-700 mb-3">Connexion employé / manager</p>
          {botName ? (
            <div ref={widgetRef} className="flex justify-center min-h-[48px]" />
          ) : (
            <div className="p-3 bg-yellow-50 border border-yellow-200 text-yellow-700 rounded-lg text-sm">
              <strong>VITE_BOT_USERNAME</strong> non configuré dans <code>.env</code>.
            </div>
          )}
        </div>

        <div className="relative mb-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-200" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-white px-2 text-gray-400">ou</span>
          </div>
        </div>

        {/* Connexion admin */}
        <form onSubmit={handleAdminLogin} className="space-y-3">
          <p className="text-sm font-medium text-gray-700">Connexion administrateur</p>
          <input
            type="text"
            placeholder="Identifiant"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
          <input
            type="password"
            placeholder="Mot de passe"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full px-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-400"
          />
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium text-sm transition disabled:opacity-50"
          >
            {loading ? 'Connexion...' : 'Se connecter'}
          </button>
        </form>
      </div>
    </div>
  );
}
