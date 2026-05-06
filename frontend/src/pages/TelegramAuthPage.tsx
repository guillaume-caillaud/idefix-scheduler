import { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

export default function TelegramAuthPage() {
  const { loginTelegram } = useAuth();
  const [message, setMessage] = useState('Validation Telegram en cours...');

  useEffect(() => {
    const run = async () => {
      const params = new URLSearchParams(window.location.search);
      const id = params.get('id');
      const firstName = params.get('first_name');
      const authDate = params.get('auth_date');
      const hash = params.get('hash');

      if (!id || !firstName || !authDate || !hash) {
        setMessage('❌ Données Telegram incomplètes. Reviens à la connexion et réessaie.');
        return;
      }

      try {
        await loginTelegram({
          id: Number(id),
          first_name: firstName,
          last_name: params.get('last_name') ?? undefined,
          username: params.get('username') ?? undefined,
          auth_date: Number(authDate),
          hash,
        });
        setMessage('✅ Authentification réussie. Redirection...');
      } catch (err: unknown) {
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setMessage(`❌ Connexion Telegram échouée${detail ? `: ${detail}` : '.'}`);
      }
    };

    run();
  }, [loginTelegram]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl p-8 max-w-md w-full text-center">
        <h1 className="text-xl font-bold text-gray-800 mb-3">Connexion Telegram</h1>
        <p className="text-sm text-gray-600">{message}</p>
      </div>
    </div>
  );
}
