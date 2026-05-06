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

type Tab = 'global' | 'team' | 'mine' | 'available';

export default function EmployeePage() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [date, setDate] = useState<string>('');
  const [tab, setTab] = useState<Tab>('global');
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

  // Toujours chargés : planning personnel + conflits
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

  // Onglet "Planning global"
  const { data: globalTasks = [] } = useQuery({
    queryKey: ['planning', date, 'global'],
    queryFn: () =>
      api.get<Task[]>('/tasks', { params: { date_value: date } }).then((r) => r.data),
    enabled: !!date && tab === 'global',
  });

  // Onglet "Planning équipe"
  const { data: teamTasks = [] } = useQuery({
    queryKey: ['planning', date, 'team', selectedTeamId],
    queryFn: () =>
      api
        .get<Task[]>('/tasks', { params: { date_value: date, team_id: selectedTeamId } })
        .then((r) => r.data),
    enabled: !!date && tab === 'team' && !!selectedTeamId,
  });

  // Onglet "Tâches disponibles"
  const { data: unfilledData } = useQuery({
    queryKey: ['unfilled', date],
    queryFn: () =>
      api
        .get<UnfilledTasksResponse>('/tasks/unfilled', { params: { date_value: date } })
        .then((r) => r.data),
    enabled: !!date && tab === 'available',
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
      qc.invalidateQueries({ queryKey: ['planning', date] });
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
      qc.invalidateQueries({ queryKey: ['planning', date] });
    },
  });

  // Données dérivées
  const conflictIds = new Set(conflictsData?.conflicts.map((c) => c.task_id) ?? []);
  const myTaskIds = new Set((schedule?.tasks ?? []).map((t) => t.id));
  // task_id → my_assignment_id pour le retrait
  const myAssignmentByTaskId = new Map(
    (schedule?.tasks ?? []).map((t) => [t.id, t.my_assignment_id])
  );
  const myTeamIds = new Set(myTeams.map((t) => t.id));
  const selectedTeam = myTeams.find((t) => t.id === selectedTeamId);
  const formattedDate = date
    ? format(new Date(date + 'T00:00:00'), 'd MMMM yyyy', { locale: fr })
    : '';

  // Tâches dispo : non-remplies dans les équipes du bénévole, non déjà assignées
  const availableTasks = (unfilledData?.tasks ?? []).filter(
    (t) => !myTaskIds.has(t.id) && (t.team_id == null || myTeamIds.has(t.team_id))
  );

  // Rendu générique : conflits + auto-affectation + retrait sur chaque tâche
  function renderTaskList(tasks: Task[], emptyMessage = 'Aucune tâche') {
    if (tasks.length === 0) {
      return (
        <div className="text-center text-gray-400 py-10 bg-white rounded-xl border border-gray-100">
          {emptyMessage}
        </div>
      );
    }
    return (
      <div className="space-y-3">
        {tasks.map((task) => {
          const isAssigned = myTaskIds.has(task.id);
          const assignmentId = myAssignmentByTaskId.get(task.id);
          return (
            <TaskCard
              key={task.id}
              task={task}
              conflicting={conflictIds.has(task.id)}
              isAssigned={isAssigned}
              onSelfAssign={!isAssigned ? () => selfAssign.mutate(task.id) : undefined}
              selfAssigning={assigningId === task.id}
              onUnassign={isAssigned && assignmentId ? () => unassign.mutate(assignmentId) : undefined}
              unassigning={unassigningId === assignmentId}
            />
          );
        })}
      </div>
    );
  }

  const tabStyle = (active: boolean) =>
    `px-3 py-1.5 rounded-lg text-sm font-medium transition ${
      active
        ? 'bg-slate-700 text-white'
        : 'bg-white text-gray-600 border border-gray-200 hover:border-slate-300'
    }`;

  return (
    <div className="p-6 max-w-2xl mx-auto space-y-6">
      {/* En-tête */}
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Mon planning</h1>
        <p className="text-sm text-gray-400 capitalize">{formattedDate}</p>
      </div>

      {/* Sélection de date + export */}
      <div className="flex gap-2 items-center flex-wrap">
        <button
          onClick={() =>
            setDate(format(addDays(new Date(date + 'T00:00:00'), -1), 'yyyy-MM-dd'))
          }
          className="px-2 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-200 transition"
          title="Jour précédent"
        >
          ←
        </button>
        <input
          type="date"
          value={date}
          onChange={(e) => setDate(e.target.value)}
          className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
        />
        <button
          onClick={() =>
            setDate(format(addDays(new Date(date + 'T00:00:00'), 1), 'yyyy-MM-dd'))
          }
          className="px-2 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-200 transition"
          title="Jour suivant"
        >
          →
        </button>
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

      {/* Onglets de navigation */}
      <div className="flex gap-2 items-center flex-wrap">
        <button onClick={() => setTab('global')} className={tabStyle(tab === 'global')}>
          Planning global
        </button>
        <button onClick={() => setTab('team')} className={tabStyle(tab === 'team')}>
          Planning équipe
        </button>
        <button onClick={() => setTab('mine')} className={tabStyle(tab === 'mine')}>
          Mes tâches
          {conflictIds.size > 0 && <span className="ml-1.5 text-red-300">⚠</span>}
        </button>
        <button onClick={() => setTab('available')} className={tabStyle(tab === 'available')}>
          Tâches disponibles
        </button>
      </div>

      {/* Sélecteur d'équipe (onglet équipe uniquement) */}
      {tab === 'team' && (
        <div>
          <select
            value={selectedTeamId}
            onChange={(e) => setSelectedTeamId(e.target.value ? Number(e.target.value) : '')}
            className="px-3 py-1.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
          >
            <option value="">Sélectionner une équipe</option>
            {myTeams.map((team) => (
              <option key={team.id} value={team.id}>
                {team.name}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* Contenu de l'onglet actif */}
      <section>
        {tab === 'global' && (
          <>
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
              Toutes les tâches
            </h2>
            {renderTaskList(globalTasks, 'Aucune tâche pour cette journée')}
          </>
        )}

        {tab === 'team' && (
          <>
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
              {selectedTeam
                ? `Tâches de l'équipe ${selectedTeam.name}`
                : "Tâches de l'équipe"}
            </h2>
            {!selectedTeamId ? (
              <div className="text-center text-gray-400 py-10 bg-white rounded-xl border border-gray-100">
                Sélectionnez une équipe pour afficher ses tâches.
              </div>
            ) : (
              renderTaskList(teamTasks, 'Aucune tâche pour cette équipe')
            )}
          </>
        )}

        {tab === 'mine' && (
          <>
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3 flex items-center gap-2">
              Mes tâches
              {conflictIds.size > 0 && (
                <span className="text-red-500 font-semibold normal-case text-xs">
                  ⚠ {conflictIds.size} conflit{conflictIds.size > 1 ? 's' : ''} détecté
                  {conflictIds.size > 1 ? 's' : ''}
                </span>
              )}
            </h2>
            {renderTaskList(schedule?.tasks ?? [], 'Aucune tâche assignée')}
          </>
        )}

        {tab === 'available' && (
          <>
            <h2 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-3">
              Tâches disponibles
            </h2>
            {availableTasks.length === 0 ? (
              <div className="text-center text-gray-400 py-10 bg-white rounded-xl border border-gray-100">
                Aucune tâche disponible
              </div>
            ) : (
              <div className="space-y-3">
                {availableTasks.map((task) => (
                  <TaskCard
                    key={task.id}
                    task={task}
                    conflicting={conflictIds.has(task.id)}
                    isAssigned={false}
                    onSelfAssign={() => selfAssign.mutate(task.id)}
                    selfAssigning={assigningId === task.id}
                  />
                ))}
              </div>
            )}
          </>
        )}
      </section>
    </div>
  );
}
