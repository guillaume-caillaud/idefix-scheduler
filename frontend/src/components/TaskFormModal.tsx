import { useState, type FormEvent, type ReactNode } from 'react';
import type { Task, Team } from '../types';
import api from '../api/client';

interface Props {
  /** Tâche à modifier (undefined = création) */
  task?: Task;
  teams?: Team[];
  defaultTeamId?: number;
  onClose: () => void;
  onSuccess: () => void;
}

export default function TaskFormModal({ task, teams = [], defaultTeamId, onClose, onSuccess }: Props) {
  const today = new Date().toISOString().substring(0, 10);

  const [title, setTitle] = useState(task?.title ?? '');
  const [description, setDescription] = useState(task?.description ?? '');
  const [date, setDate] = useState(task?.start_at.substring(0, 10) ?? today);
  const [startTime, setStartTime] = useState(task?.start_at.substring(11, 16) ?? '09:00');
  const [endTime, setEndTime] = useState(task?.end_at.substring(11, 16) ?? '11:00');
  const [required, setRequired] = useState(task?.required_people ?? 1);
  const [teamId, setTeamId] = useState<number | ''>(
    task?.team_id ?? defaultTeamId ?? (teams[0]?.id ?? ''),
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);

    if (endTime <= startTime) {
      setError("L'heure de fin doit être après l'heure de début.");
      return;
    }

    setLoading(true);
    try {
      const payload = {
        title,
        description: description || undefined,
        start_at: `${date}T${startTime}:00`,
        end_at: `${date}T${endTime}:00`,
        required_people: required,
        team_id: teamId ? Number(teamId) : undefined,
      };

      if (task) {
        await api.patch(`/tasks/${task.id}`, payload);
      } else {
        await api.post('/tasks', payload);
      }
      onSuccess();
      onClose();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? 'Une erreur est survenue.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 px-4">
      <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-md">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-lg font-bold text-gray-800">
            {task ? 'Modifier la tâche' : 'Nouvelle tâche'}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">
            ×
          </button>
        </div>

        {error && (
          <div className="mb-3 p-3 bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <Field label="Titre *">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
              className={input}
            />
          </Field>

          <Field label="Description">
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={2}
              className={`${input} resize-none`}
            />
          </Field>

          <Field label="Date *">
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              required
              className={input}
            />
          </Field>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Heure début *">
              <input
                type="time"
                value={startTime}
                onChange={(e) => setStartTime(e.target.value)}
                required
                className={input}
              />
            </Field>
            <Field label="Heure fin *">
              <input
                type="time"
                value={endTime}
                onChange={(e) => setEndTime(e.target.value)}
                required
                className={input}
              />
            </Field>
          </div>

          <Field label="Personnes requises *">
            <input
              type="number"
              min={1}
              value={required}
              onChange={(e) => setRequired(Number(e.target.value))}
              required
              className={input}
            />
          </Field>

          <Field label="Equipe *">
            <select
              value={teamId}
              onChange={(e) => setTeamId(e.target.value ? Number(e.target.value) : '')}
              required
              className={input}
            >
              <option value="">— Sélectionner une équipe —</option>
              {teams.map((team) => (
                <option key={team.id} value={team.id}>{team.name}</option>
              ))}
            </select>
          </Field>

          <div className="flex gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 border border-gray-200 text-gray-600 rounded-lg text-sm hover:bg-gray-50 transition"
            >
              Annuler
            </button>
            <button
              type="submit"
              disabled={loading}
              className="flex-1 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition disabled:opacity-50"
            >
              {loading ? '...' : task ? 'Mettre à jour' : 'Créer'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const input =
  'w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300';

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      {children}
    </div>
  );
}
