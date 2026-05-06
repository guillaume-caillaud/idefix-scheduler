import { useCallback, useEffect, useRef, useState } from 'react';
import api from '../api/client';
import { useAuth } from '../contexts/AuthContext';

type ChallengeState = {
  code: string;
  deepLink: string;
  appLink: string;
  expiresAt: number; // unix ms
};

export default function LoginPage() {
  const { loginTelegramByChallenge } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [challenge, setChallenge] = useState<ChallengeState | null>(null);
  const [challengeLoading, setChallengeLoading] = useState(false);
  const [timeLeft, setTimeLeft] = useState(0);
  const pollingRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const rawBotName = import.meta.env.VITE_BOT_USERNAME as string | undefined;
  const botName = rawBotName?.trim().replace(/^@/, '');

  // Countdown timer
  useEffect(() => {
    if (!challenge) return;
    const interval = setInterval(() => {
      const remaining = Math.max(0, Math.round((challenge.expiresAt - Date.now()) / 1000));
      setTimeLeft(remaining);
      if (remaining === 0) {
        clearInterval(interval);
        setChallenge(null);
        setError('Le code a expiré. Génère un nouveau code pour te connecter.');
      }
    }, 1000);
    return () => clearInterval(interval);
  }, [challenge]);

  // Polling for challenge approval
  const startPolling = useCallback((code: string, deadline: number) => {
    const tick = async () => {
      if (Date.now() >= deadline) return;
      try {
        await loginTelegramByChallenge(code);
        setChallenge(null);
      } catch (err: unknown) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 409) {
          pollingRef.current = setTimeout(tick, 2000);
        }
        // other errors (404 expired, network) stop polling silently
      }
    };
    pollingRef.current = setTimeout(tick, 2000);
  }, [loginTelegramByChallenge]);

  // Cleanup polling on unmount
  useEffect(() => {
    return () => { if (pollingRef.current) clearTimeout(pollingRef.current); };
  }, []);

  const handleStartChallenge = async () => {
    if (!botName) {
      setError('VITE_BOT_USERNAME non configuré.');
      return;
    }
    setError(null);
    setChallengeLoading(true);
    if (pollingRef.current) clearTimeout(pollingRef.current);
    try {
      const { data } = await api.post<{ challenge_id: string; expires_in: number; deep_link?: string }>(
        '/auth/telegram/challenge'
      );
      const code = data.challenge_id;
      const ttlMs = data.expires_in * 1000;
      const expiresAt = Date.now() + ttlMs;
      const deepLink = data.deep_link ?? `https://t.me/${botName}`;
      const appLink = `tg://resolve?domain=${botName}`;
      setChallenge({ code, deepLink, appLink, expiresAt });
      startPolling(code, expiresAt);
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? 'Impossible de générer un code. Vérifie que l\'API est accessible.');
    } finally {
      setChallengeLoading(false);
    }
  };

  const handleCancelChallenge = () => {
    if (pollingRef.current) clearTimeout(pollingRef.current);
    setChallenge(null);
    setError(null);
  };

  const copyCommand = async () => {
    if (!challenge) return;
    try {
      await navigator.clipboard.writeText(challenge.code);
    } catch {
      /* silently fail */
    }
  };

  const formatTime = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;

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

        {/* ── Connexion Telegram via bot ── */}
        <div className="mb-6">
          <p className="text-sm font-medium text-gray-700 mb-3">Connexion bénévole / responsable</p>

          {!botName ? (
            <div className="p-3 bg-yellow-50 border border-yellow-200 text-yellow-700 rounded-lg text-sm">
              <strong>VITE_BOT_USERNAME</strong> non configuré dans <code>.env</code>.
            </div>
          ) : !challenge ? (
            <button
              type="button"
              onClick={handleStartChallenge}
              disabled={challengeLoading}
              className="w-full py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium text-sm transition disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {challengeLoading ? 'Génération du code…' : '🤖 Se connecter via Telegram'}
            </button>
          ) : (
            <div className="rounded-xl border border-indigo-100 bg-indigo-50/50 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-indigo-700 uppercase tracking-wide">Code de connexion</p>
                <span className={`text-xs font-mono px-2 py-0.5 rounded-full ${timeLeft <= 60 ? 'bg-red-100 text-red-600' : 'bg-indigo-100 text-indigo-600'}`}>
                  ⏱ {formatTime(timeLeft)}
                </span>
              </div>

              {/* Code 8 chiffres */}
              <div className="flex items-center gap-2">
                <div className="flex-1 rounded-lg bg-white border-2 border-indigo-200 py-3 text-center font-mono text-3xl font-bold tracking-[0.25em] text-indigo-800 select-all">
                  {challenge.code}
                </div>
                <button
                  type="button"
                  onClick={copyCommand}
                  title="Copier le code"
                  className="p-3 rounded-lg border border-indigo-200 bg-white text-indigo-600 hover:bg-indigo-50 transition text-lg"
                >
                  📋
                </button>
              </div>

              <div className="text-xs text-gray-500 space-y-1">
                <p className="font-medium text-gray-700">1) Ouvrez le bot Telegram :</p>
                <div className="flex gap-2">
                  <a
                    href={challenge.appLink}
                    className="flex-1 text-center py-1.5 rounded-md border border-indigo-200 bg-white text-indigo-700 hover:bg-indigo-50 transition text-xs"
                  >
                    Ouvrir l'app
                  </a>
                  <a
                    href={challenge.deepLink}
                    target="_blank"
                    rel="noreferrer"
                    className="flex-1 text-center py-1.5 rounded-md border border-indigo-200 bg-white text-indigo-700 hover:bg-indigo-50 transition text-xs"
                  >
                    Ouvrir le web
                  </a>
                </div>
                <p className="font-medium text-gray-700 pt-1">2) Envoyez la commande <span className="font-mono">/login</span> au bot.</p>
                <div className="rounded bg-white border border-indigo-100 px-3 py-1.5 font-mono text-xs text-gray-700 select-all">
                  /login
                </div>
                <p className="font-medium text-gray-700 pt-1">3) Quand le bot le demande, envoyez ce code à 8 chiffres :</p>
                <div className="rounded bg-white border border-indigo-100 px-3 py-1.5 font-mono text-xs text-gray-700 select-all">
                  {challenge.code}
                </div>
              </div>

              <div className="flex items-center gap-2 pt-1">
                <span className="text-xs text-gray-400 flex-1 italic">En attente de validation…</span>
                <button
                  type="button"
                  onClick={handleCancelChallenge}
                  className="text-xs text-gray-400 hover:text-gray-600 underline"
                >
                  Annuler
                </button>
              </div>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}


