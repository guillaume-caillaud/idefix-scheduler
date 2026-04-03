import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { addDays, format } from 'date-fns';
import { fr } from 'date-fns/locale';
import api from '../api/client';
import type {
  ConflictResponse,
  DayScheduleResponse,
  Task,
  Team,
  UnfilledTasksResponse,
} from '../types';
import { useAuth } from '../contexts/AuthContext';
import TaskCard from '../components/TaskCard';
import { printSchedule } from '../utils/printSchedule';

type Scope = 'global' | 'team';

export default function EmployeePage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [date, setDate] = useState<string>('');
  const [scope, setScope] = useState<Scope>('global');
  const [selectedTeamId, setSelectedTeamId] = useState<number | ''>('');
  const [assigningId, setAssigningId] = useState<number | null>(null);
  const [unassigningId, setUnassigningId] = useState<number | null>(null);

  // Récupérer le jour par défaut au chargement
  useEffect(() => {
    const fetchDefaultDay = async () => {
      const today = format(new Date(), 'yyyy-MM-dd');
      try {
        const response = await api.get('/admin/settings/default-day');
        const defaultDay = response.data.day || today;
        // Si la date par défaut est avant aujourd'hui, utiliser aujourd'hui
        const dateToUse = defaultDay < today ? today : defaultDay;
        setDate(dateToUse);
      } catch {
        // Si l'endpoint n'existe pas ou erreur, utiliser aujourd'hui
        setDate(today);
      }
    };
    fetchDefaultDay();
  }, []);

  const { data: myTeams = [] } = useQuery({
    queryKey: ['teams', 'me'],
    queryFn: () => api.get<Team[]>('/teams/me').then((r) => r.data),
  });

  const teamParams = scope === 'team' && selectedTeamId ? { team_id: selectedTeamId } : {};

  const { data: schedule } = useQuery({
    queryKey: ['schedule', date],
    queryFn: () =>
      api
        .get<DayScheduleResponse>('/assignments/me/schedule', { params: { date_value: date } })
        .then((r) => r.data),
    enabled: !!date,
  });

  const { data: conflictsData } = useQuery({
    queryKey: ['conflicts', date],
    queryFn: () =>
      api
        .get<ConflictResponse>('/assignments/me/conflicts', { params: { date_value: date } })
        .then((r) => r.data),
    enabled: !!date,
  });

  const { data: unfilledData } = useQuery({
    queryKey: ['unfilled', date, scope, selectedTeamId],
    queryFn: () =>
      api
        .get<UnfilledTasksResponse>('/tasks/unfilled', { params: { date_value: date, ...teamParams } })
        .then((r) => r.data),
    enabled: !!date,
  });

  const { data: planningTasks = [] } = useQuery({
    queryKey: ['planning', date, scope, selectedTeamId],
    queryFn: () =>
      api
        .get<Task[]>('/tasks', { params: { date_value: date, ...teamParams } })
        .then((r) => r.data),
    enabled: !!date && (scope === 'global' || !!selectedTeamId),
  });

  const selfAssign = useMutation({
    mutationFn: (task_id: number) =>
      api.post('/assignments', { task_id, assignee_id: user!.id }),
    onMutate: (task_id) => setAssigningId(task_id),
    onSettled: () => setAssigningId(null),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schedule', date] });
      qc.invalidateQueries({ queryKey: ['unfilled', date] });
      qc.invalidateQueries({ queryKey: ['conflicts', date] });
    },
  });

  const unassign = useMutation({
    mutationFn: (assignmentId: number) => api.delete(`/assignments/${assignmentId}`),
    onMutate: (assignmentId) => setUnassigningId(assignmentId),
    onSettled: () => setUnassigningId(null),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['schedule', date] });
      qc.invalidateQueries({ queryKey: ['unfilled', date] });
      qc.invalidateQueries({ queryKey: ['conflicts', date] });
    },
  });

  const conflictIds = new Set(conflictsData?.conflicts.map((c) => c.task_id) ?? []);
  const myTaskIds = new Set(schedule?.tasks.map((t) => t.id) ?? []);

  const formattedDate = date ? format(new Date(date + 'T00:00:00'), 'd MMMM yyyy', { locale: fr }) : '';

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-8">
      {/* ── En-tête ── */}
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Mon planning</h1>
        <p className="text-sm text-gray-400 capitalize">{formattedDate}</p>
      </div>

      {/* ── Sélection de date + export ── */}
      <div className="flex gap-2 items-center flex-wrap">
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
        />
        <button
          onClick={() => setDate(format(new Date(), 'yyyy-MM-dd'))}
          className="px-3 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-200 transition"
        >
          Aujourd'hui
        </button>
        <button
          onClick={() => setDate(format(addDays(new Date(), 1), 'yyyy-MM-dd'))}
          className="px-3 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-200 transition"
        >
          Demain
        </button>
        {(schedule?.tasks ?? []).length > 0 && (
          <button
            onClick={() =>
              printSchedule({
                title: 'Mon planning',
                date,
                formattedDate,
                tasks: schedule!.tasks,
                conflictIds,
                subtitle: user?.name,
              })
            }
            className="px-3 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition"
          >
            🖨 Imprimer
          </button>
        )}
      </div>

      <div className="flex gap-2 items-center flex-wrap">
        <button
          onClick={() => setScope('global')}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
            scope === 'global'
              ? 'bg-slate-700 text-white'
              : 'bg-white text-gray-600 border border-gray-200 hover:border-slate-300'
          }`}
        >
          Planning global
        </button>
        <button
          onClick={() => setScope('team')}
          className={`px-3 py-1.5 rounded-lg text-sm font-medium transition ${
            scope === 'team'
              ? 'bg-slate-700 text-white'
              : 'bg-white text-gray-600 border border-gray-200 hover:border-slate-300'
          }`}
        >
          Planning équipe
        </button>
        {scope === 'team' && (
          <select
            value={selectedTeamId}
            onChange={(e) => setSelectedTeamId(e.target.value ? Number(e.target.value) : '')}
            className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
          >
            <option value="">Sélectionner une équipe</option>
            {myTeams.map((team) => (
              <option key={team.id} value={team.id}>{team.name}</option>
            ))}
          </select>
        )}
      </div>

      <section>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Tâches visibles ({scope === 'global' ? 'global' : 'équipe'})
        </h2>

        {scope === 'team' && !selectedTeamId ? (
          <div className="text-center text-gray-400 py-8 bg-white rounded-xl border border-gray-100">
            Sélectionnez une équipe pour afficher les tâches de l'équipe.
          </div>
        ) : planningTasks.length === 0 ? (
          <div className="text-center text-gray-400 py-8 bg-white rounded-xl border border-gray-100">
            Aucune tâche visible
          </div>
        ) : (
          <div className="space-y-3">
            {planningTasks.map((task) => (
              <TaskCard key={task.id} task={task} isAssigned={myTaskIds.has(task.id)} />
            ))}
          </div>
        )}
      </section>

      {/* ── Mes tâches ── */}
      <section>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
          Mes tâches
          {conflictIds.size > 0 && (
            <span className="text-red-500 font-semibold normal-case text-xs">
              ⚠ {conflictIds.size} conflit{conflictIds.size > 1 ? 's' : ''} détecté{conflictIds.size > 1 ? 's' : ''}
            </span>
          )}
        </h2>

        {(schedule?.tasks ?? []).length === 0 ? (
          <div className="text-center text-gray-400 py-10 bg-white rounded-xl border border-gray-100">
            Aucune tâche assignée
          </div>
        ) : (
          <div className="space-y-3">
            {schedule!.tasks.map((task: Task) => (
              <TaskCard
                key={task.id}
                task={task}
                conflicting={conflictIds.has(task.id)}
                isAssigned
                onUnassign={() => unassign.mutate(task.id)}
                unassigning={unassigningId === task.id}
              />
            ))}
          </div>
        )}
      </section>

      {/* ── Tâches disponibles ── */}
      <section>
        <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Tâches disponibles (non remplies)
        </h2>

        {(() => {
          const available = (unfilledData?.tasks ?? []).filter((t) => !myTaskIds.has(t.id));
          return available.length === 0 ? (
            <div className="text-center text-gray-400 py-10 bg-white rounded-xl border border-gray-100">
              Aucune tâche disponible
            </div>
          ) : (
            <div className="space-y-3">
              {available.map((task) => (
                <TaskCard
                  key={task.id}
                  task={task}
                  onSelfAssign={() => selfAssign.mutate(task.id)}
                  selfAssigning={assigningId === task.id}
                  isAssigned={false}
                />
              ))}
            </div>
          );
        })()}
      </section>
    </div>
  );
}
