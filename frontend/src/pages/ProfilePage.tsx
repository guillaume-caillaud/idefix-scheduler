import { useState } from 'react';
import { useAuth } from '../contexts/AuthContext';

export default function ProfilePage() {
  const { user, updateMyName } = useAuth();
  const [name, setName] = useState(user?.name ?? '');
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);

  const onSave = async () => {
    const clean = name.trim();
    if (!clean) {
      setFeedback('Le nom ne peut pas être vide.');
      return;
    }

    setSaving(true);
    setFeedback(null);
    try {
      await updateMyName(clean);
      setFeedback('✅ Nom mis à jour.');
    } catch {
      setFeedback('❌ Impossible de mettre à jour le nom.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      <section className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
        <h1 className="text-2xl font-bold text-gray-800 mb-2">Mon profil</h1>
        <p className="text-sm text-gray-500 mb-6">
          Modifiez votre nom d'affichage utilisé dans l'application.
        </p>

        {feedback && (
          <div className="mb-4 p-2 bg-gray-50 border border-gray-200 text-sm rounded-lg text-gray-700">
            {feedback}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-700 block mb-1">Nom d'affichage</label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              placeholder="Votre nom"
            />
          </div>

          <div className="grid md:grid-cols-2 gap-3">
            <div>
              <p className="text-xs font-medium text-gray-700 mb-1">Rôle</p>
              <p className="text-sm text-gray-600 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                {user?.role ?? '-'}
              </p>
            </div>
            <div>
              <p className="text-xs font-medium text-gray-700 mb-1">Telegram</p>
              <p className="text-sm text-gray-600 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2">
                {user?.telegram_username ? `@${user.telegram_username}` : `#${user?.telegram_user_id ?? '-'}`}
              </p>
            </div>
          </div>

          <button
            onClick={onSave}
            disabled={saving}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition disabled:opacity-50"
          >
            {saving ? '...' : 'Enregistrer'}
          </button>
        </div>
      </section>
    </div>
  );
}
