import { useState } from 'react';
import type { Task } from '../types';

interface Props {
  task: Task;
  /** Surligne la carte en rouge si une collision horaire est détectée */
  conflicting?: boolean;
  /** Bouton ✏ Modifier (manager) */
  onEdit?: () => void;
  /** Bouton + Affecter (manager → ouvre le modal d'affectation) */
  onAssign?: () => void;
  /** Bouton Me proposer (employee → auto-affectation) */
  onSelfAssign?: () => void;
  selfAssigning?: boolean;
  /** L'utilisateur courant est déjà affecté à cette tâche */
  isAssigned?: boolean;
  /** Bouton - Retirer l'affectation (employee self-unassign) */
  onUnassign?: () => void;
  unassigning?: boolean;
}

function hhmm(iso: string) {
  return iso.substring(11, 16);
}

export default function TaskCard({
  task,
  conflicting,
  onEdit,
  onAssign,
  onSelfAssign,
  selfAssigning,
  isAssigned,
  onUnassign,
  unassigning,
}: Props) {
  const [showLongDescription, setShowLongDescription] = useState(false);
  const hasPrimaryActions =
    Boolean(onEdit) ||
    Boolean(onAssign) ||
    Boolean(onSelfAssign && !isAssigned) ||
    Boolean(isAssigned && onUnassign) ||
    Boolean(isAssigned && !onUnassign);
  const pct =
    task.required_people > 0 ? (task.assigned_people / task.required_people) * 100 : 0;

  const barColor = task.is_fully_staffed
    ? 'bg-green-400'
    : task.assigned_people > 0
      ? 'bg-yellow-400'
      : 'bg-red-300';

  const cardBorder = conflicting
    ? 'border-red-400 bg-red-50'
    : 'border-gray-100 hover:border-indigo-200 bg-white';

  return (
    <div className={`rounded-xl border p-4 shadow-sm transition ${cardBorder}`}>
      {/* En-tête */}
      <div className="flex justify-between items-start mb-1">
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            {conflicting && (
              <span className="text-xs font-semibold text-red-600 bg-red-100 px-2 py-0.5 rounded-full shrink-0">
                ⚠ Conflit
              </span>
            )}
            {!task.is_fully_staffed && !conflicting && (
              <span className="text-xs font-semibold text-orange-600 bg-orange-100 px-2 py-0.5 rounded-full shrink-0">
                Incomplet
              </span>
            )}
            <span className="font-semibold text-gray-800 truncate">{task.title}</span>
          </div>
          <div className="text-xs text-gray-400 mt-0.5">
            {hhmm(task.start_at)} – {hhmm(task.end_at)}
          </div>
        </div>
        <span
          className={`ml-3 shrink-0 text-xs font-medium px-2 py-0.5 rounded-full ${
            task.is_fully_staffed ? 'bg-green-100 text-green-700' : 'bg-orange-100 text-orange-700'
          }`}
        >
          {task.assigned_people}/{task.required_people} pers.
        </span>
      </div>

      <div className="mb-2">
        <p className="text-[11px] uppercase tracking-wide text-gray-400 mb-1">Affectés</p>
        {task.assigned_users.length === 0 ? (
          <p className="text-xs text-gray-400">Personne pour le moment</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {task.assigned_users.map((assignee) => (
              <span
                key={assignee.id}
                className="text-xs px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-700"
              >
                {assignee.name}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Barre de staffing */}
      <div className="w-full h-1.5 bg-gray-100 rounded-full mb-3 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${barColor}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>

      {task.description && showLongDescription && (
        <div className="mb-3 text-xs text-gray-600 bg-slate-50 border border-slate-200 rounded-lg p-2 whitespace-pre-wrap">
          {task.description}
        </div>
      )}

      {/* Actions */}
      <div className="flex gap-2 flex-wrap">
        {onEdit && (
          <button
            onClick={onEdit}
            className="text-xs px-2.5 py-1 bg-gray-100 text-gray-600 rounded-lg hover:bg-gray-200 transition"
          >
            ✏ Modifier
          </button>
        )}
        {onAssign && (
          <button
            onClick={onAssign}
            className="text-xs px-2.5 py-1 bg-indigo-50 text-indigo-600 rounded-lg hover:bg-indigo-100 transition"
          >
            + Affecter
          </button>
        )}
        {onSelfAssign && !isAssigned && (
          <button
            onClick={onSelfAssign}
            disabled={selfAssigning}
            className="text-xs px-2.5 py-1 bg-blue-50 text-blue-600 rounded-lg hover:bg-blue-100 transition disabled:opacity-50"
          >
            {selfAssigning ? '...' : '+ Me proposer'}
          </button>
        )}
        {isAssigned && onUnassign && (
          <button
            onClick={onUnassign}
            disabled={unassigning}
            className="text-xs px-2.5 py-1 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition disabled:opacity-50 flex items-center gap-1"
          >
            {unassigning ? '...' : '✕ Me retirer'}
          </button>
        )}
        {isAssigned && !onUnassign && (
          <span className="text-xs px-2.5 py-1 bg-green-50 text-green-600 rounded-lg font-medium">
            ✓ Affecté
          </span>
        )}
        {task.description && (
          <button
            onClick={() => setShowLongDescription((prev: boolean) => !prev)}
            className={`text-xs px-2.5 py-1 rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 transition ${
              hasPrimaryActions ? 'ml-auto' : ''
            }`}
          >
            {showLongDescription ? 'Masquer les informations' : 'Plus d\'information'}
          </button>
        )}
      </div>
    </div>
  );
}
