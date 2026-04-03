import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { format, addDays } from 'date-fns';
import { fr } from 'date-fns/locale';
import api from '../api/client';
import type { Task, Team, TeamDetail, User } from '../types';
import TaskCard from '../components/TaskCard';
import TaskFormModal from '../components/TaskFormModal';
import { printSchedule } from '../utils/printSchedule';

type Tab = 'all' | 'unfilled';
type Scope = 'global' | 'team';

export default function ManagerPage() {
  const qc = useQueryClient();
  const [date, setDate] = useState(new Date().toISOString().substring(0, 10));
  const [tab, setTab] = useState<Tab>('all');
  const [scope, setScope] = useState<Scope>('global');
  const [selectedTeamId, setSelectedTeamId] = useState<number | ''>('');
  const [manageTeamId, setManageTeamId] = useState<number | ''>('');
  const [teamName, setTeamName] = useState('');
  const [selectedEmployeeForTeam, setSelectedEmployeeForTeam] = useState<number | ''>('');
  const [teamFeedback, setTeamFeedback] = useState<string | null>(null);
  const [editingTask, setEditingTask] = useState<Task | undefined>();
  const [showTaskModal, setShowTaskModal] = useState(false);
  const [assignTask, setAssignTask] = useState<Task | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<number | ''>('');
  const [assignError, setAssignError] = useState<string | null>(null);
  const [alertMsg, setAlertMsg] = useState('');
  const [alertSending, setAlertSending] = useState(false);
  const [alertFeedback, setAlertFeedback] = useState<string | null>(null);

  // Récupérer le jour par défaut au chargement
  useEffect(() => {
    const fetchDefaultDay = async () => {
      const today = format(new Date(), 'yyyy-MM-dd');
      try {
        const response = await api.get('/admin/settings/default-day');
        if (response.data.day) {
          // Si la date par défaut est avant aujourd'hui, utiliser aujourd'hui
          const dateToUse = response.data.day < today ? today : response.data.day;
          setDate(dateToUse);
        }
      } catch {
        // Si l'endpoint n'existe pas ou erreur, utiliser aujourd'hui
      }
    };
    fetchDefaultDay();
  }, []);

  const { data: teams = [] } = useQuery({
    queryKey: ['teams'],
    queryFn: () => api.get<Team[]>('/teams').then((r) => r.data),
  });

  const { data: managedTeamDetail } = useQuery({
    queryKey: ['team-detail', manageTeamId],
    queryFn: () => api.get<TeamDetail>(`/teams/${manageTeamId}`).then((r) => r.data),
    enabled: !!manageTeamId,
  });

  const teamParams = scope === 'team' && selectedTeamId ? { team_id: selectedTeamId } : {};

  // Toutes les tâches du jour
  const { data: allTasks = [] } = useQuery({
    queryKey: ['tasks', date, scope, selectedTeamId],
    queryFn: () =>
      api.get<Task[]>('/tasks', { params: { date_value: date, ...teamParams } }).then((r) => r.data),
    enabled: scope === 'global' || !!selectedTeamId,
  });

  // Tâches non remplies
  const { data: unfilledData } = useQuery({
    queryKey: ['tasks', 'unfilled', date, scope, selectedTeamId],
    queryFn: () =>
      api.get('/tasks/unfilled', { params: { date_value: date, ...teamParams } }).then((r) => r.data),
    enabled: tab === 'unfilled' && (scope === 'global' || !!selectedTeamId),
  });

  // Utilisateurs assignables (employés + managers)
  const { data: assignableUsers = [] } = useQuery({
    queryKey: ['users-assignable'],
    queryFn: () => api.get<User[]>('/users/assignable').then((r) => r.data),
    enabled: assignTask !== null,
  });

  const { data: teamAssignableUsers = [] } = useQuery({
    queryKey: ['users-assignable', 'teams'],
    queryFn: () => api.get<User[]>('/users/assignable').then((r) => r.data),
  });

  const employeeUsers = teamAssignableUsers.filter((u) => u.role === 'employee');

  const assignMutation = useMutation({
    mutationFn: ({ task_id, assignee_id }: { task_id: number; assignee_id: number }) =>
      api.post('/assignments', { task_id, assignee_id }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['tasks'] });
      setAssignTask(null);
      setSelectedUserId('');
      setAssignError(null);
    },
    onError: (err: unknown) => {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setAssignError(detail ?? "Erreur lors de l'affectation.");
    },
  });

  const createTeamMutation = useMutation({
    mutationFn: (name: string) => api.post('/teams', { name }),
    onSuccess: () => {
      setTeamFeedback('✅ Equipe créée.');
      setTeamName('');
      qc.invalidateQueries({ queryKey: ['teams'] });
    },
    onError: () => setTeamFeedback('❌ Impossible de créer l\'équipe.'),
  });

  const addTeamMemberMutation = useMutation({
    mutationFn: ({ teamId, userId }: { teamId: number; userId: number }) =>
      api.post(`/teams/${teamId}/members`, { user_ids: [userId] }),
    onSuccess: () => {
      setTeamFeedback('✅ Employé ajouté à l\'équipe.');
      setSelectedEmployeeForTeam('');
      qc.invalidateQueries({ queryKey: ['team-detail', manageTeamId] });
    },
    onError: () => setTeamFeedback('❌ Impossible d\'ajouter cet employé.'),
  });

  const removeTeamMemberMutation = useMutation({
    mutationFn: ({ teamId, userId }: { teamId: number; userId: number }) =>
      api.delete(`/teams/${teamId}/members/${userId}`),
    onSuccess: () => {
      setTeamFeedback('✅ Employé retiré de l\'équipe.');
      qc.invalidateQueries({ queryKey: ['team-detail', manageTeamId] });
    },
    onError: () => setTeamFeedback('❌ Impossible de retirer cet employé.'),
  });

  const sendAlert = async () => {
    if (!alertMsg.trim()) return;
    setAlertSending(true);
    setAlertFeedback(null);
    try {
      await api.post('/alerts', { message: alertMsg });
      setAlertFeedback('✅ Alerte envoyée.');
      setAlertMsg('');
    } catch {
      setAlertFeedback("❌ Erreur lors de l'envoi.");
    } finally {
      setAlertSending(false);
    }
  };

  const tasks = tab === 'all' ? allTasks : (unfilledData?.tasks ?? []);
  const formattedDate = format(new Date(date + 'T00:00:00'), 'd MMMM yyyy', { locale: fr });

  return (
    <div className="p-6 max-w-3xl mx-auto space-y-6">
      {/* ── En-tête ── */}
      <div className="flex flex-wrap items-end gap-3">
        <div>
          <h1 className="text-2xl font-bold text-gray-800">Planification</h1>
          <p className="text-sm text-gray-400 capitalize">{formattedDate}</p>
        </div>
        <div className="flex-1" />
        <div className="flex gap-2 items-center">
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
            Auj.
          </button>
          <button
            onClick={() => setDate(format(addDays(new Date(), 1), 'yyyy-MM-dd'))}
            className="px-3 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm font-medium hover:bg-gray-200 transition"
          >
            Dem.
          </button>
        </div>
        <button
          onClick={() =>
            printSchedule({
              title: 'Planning',
              date,
              formattedDate,
              tasks,
            })
          }
          className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-sm font-medium hover:bg-gray-200 transition flex items-center gap-1.5"
        >
          🖨 Imprimer
        </button>
        <button
          onClick={() => {
            setEditingTask(undefined);
            setShowTaskModal(true);
          }}
          disabled={teams.length === 0}
          className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition disabled:opacity-50"
        >
          + Nouvelle tâche
        </button>
      </div>

      {teams.length === 0 && (
        <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          Créez d'abord une équipe pour pouvoir créer des tâches d'équipe.
        </div>
      )}

      {/* ── Onglets ── */}
      <div className="flex gap-2 items-center">
        <button
          onClick={() => setScope('global')}
          className={`px-4 py-1.5 rounded-lg text-sm font-medium transition ${
            scope === 'global'
              ? 'bg-slate-700 text-white'
              : 'bg-white text-gray-600 border border-gray-200 hover:border-slate-300'
          }`}
        >
          Planning global
        </button>
        <button
          onClick={() => setScope('team')}
          className={`px-4 py-1.5 rounded-lg text-sm font-medium transition ${
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
            {teams.map((team) => (
              <option key={team.id} value={team.id}>{team.name}</option>
            ))}
          </select>
        )}
        {(['all', 'unfilled'] as Tab[]).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-1.5 rounded-lg text-sm font-medium transition ${
              tab === t
                ? 'bg-indigo-600 text-white'
                : 'bg-white text-gray-600 border border-gray-200 hover:border-indigo-300'
            }`}
          >
            {t === 'all' ? 'Toutes les tâches' : '⚠ Non remplies'}
          </button>
        ))}
        <span className="ml-auto text-sm text-gray-400">
          {tasks.length} tâche{tasks.length !== 1 ? 's' : ''}
        </span>
      </div>

      {scope === 'team' && !selectedTeamId && (
        <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
          Sélectionnez une équipe pour afficher son planning.
        </div>
      )}

      {/* ── Liste des tâches ── */}
      {(scope === 'team' && !selectedTeamId) ? null : tasks.length === 0 ? (
        <div className="text-center text-gray-400 py-16 bg-white rounded-xl border border-gray-100">
          {tab === 'unfilled' ? '✓ Toutes les tâches sont remplies' : 'Aucune tâche ce jour'}
        </div>
      ) : (
        <div className="space-y-3">
          {tasks.map((task:Task) => (
            <TaskCard
              key={task.id}
              task={task}
              onEdit={() => {
                setEditingTask(task);
                setShowTaskModal(true);
              }}
              onAssign={() => {
                setAssignTask(task);
                setSelectedUserId('');
                setAssignError(null);
              }}
            />
          ))}
        </div>
      )}

      {/* ── Envoi d'alerte ── */}
      <section className="bg-white rounded-xl border border-gray-100 shadow-sm p-5">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">📢 Envoyer une alerte Telegram</h2>
        {alertFeedback && (
          <p className="mb-2 text-sm text-gray-600">{alertFeedback}</p>
        )}
        <div className="flex gap-3">
          <input
            type="text"
            placeholder="Message…"
            value={alertMsg}
            onChange={(e) => setAlertMsg(e.target.value)}
            className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
          />
          <button
            onClick={sendAlert}
            disabled={alertSending || !alertMsg.trim()}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition"
          >
            {alertSending ? '...' : 'Envoyer'}
          </button>
        </div>
      </section>

      {/* ── Gestion des équipes (manager) ── */}
      <section className="bg-white rounded-xl border border-gray-100 shadow-sm p-5 space-y-4">
        <h2 className="text-sm font-semibold text-gray-700">👥 Gérer les équipes</h2>
        {teamFeedback && <p className="text-sm text-gray-600">{teamFeedback}</p>}

        <div className="flex gap-2 flex-wrap">
          <input
            type="text"
            value={teamName}
            onChange={(e) => setTeamName(e.target.value)}
            placeholder="Nom de la nouvelle équipe"
            className="flex-1 min-w-52 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
          />
          <button
            onClick={() => teamName.trim() && createTeamMutation.mutate(teamName.trim())}
            disabled={!teamName.trim() || createTeamMutation.isPending}
            className="px-3 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition disabled:opacity-50"
          >
            {createTeamMutation.isPending ? '...' : '+ Créer'}
          </button>
        </div>

        <div className="grid md:grid-cols-2 gap-3">
          <div className="space-y-2">
            <label className="text-xs text-gray-500">Equipe à gérer</label>
            <select
              value={manageTeamId}
              onChange={(e) => setManageTeamId(e.target.value ? Number(e.target.value) : '')}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
            >
              <option value="">Sélectionner</option>
              {teams.map((team) => (
                <option key={team.id} value={team.id}>{team.name}</option>
              ))}
            </select>

            <div className="flex gap-2">
              <select
                value={selectedEmployeeForTeam}
                onChange={(e) => setSelectedEmployeeForTeam(e.target.value ? Number(e.target.value) : '')}
                disabled={!manageTeamId}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
              >
                <option value="">Ajouter un employé</option>
                {employeeUsers.map((employee) => (
                  <option key={employee.id} value={employee.id}>{employee.name}</option>
                ))}
              </select>
              <button
                onClick={() =>
                  manageTeamId &&
                  selectedEmployeeForTeam &&
                  addTeamMemberMutation.mutate({
                    teamId: Number(manageTeamId),
                    userId: Number(selectedEmployeeForTeam),
                  })
                }
                disabled={!manageTeamId || !selectedEmployeeForTeam || addTeamMemberMutation.isPending}
                className="px-3 py-2 bg-indigo-50 text-indigo-700 rounded-lg text-sm hover:bg-indigo-100 disabled:opacity-50"
              >
                Ajouter
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-xs text-gray-500">Membres</p>
            {!manageTeamId ? (
              <p className="text-sm text-gray-400">Sélectionnez une équipe.</p>
            ) : (managedTeamDetail?.members ?? []).length === 0 ? (
              <p className="text-sm text-gray-400">Aucun employé dans cette équipe.</p>
            ) : (
              <div className="space-y-2">
                {managedTeamDetail!.members.map((member) => (
                  <div key={member.id} className="flex items-center justify-between bg-gray-50 border border-gray-100 rounded-lg px-3 py-2">
                    <span className="text-sm text-gray-700">{member.name}</span>
                    <button
                      onClick={() =>
                        manageTeamId &&
                        removeTeamMemberMutation.mutate({
                          teamId: Number(manageTeamId),
                          userId: member.id,
                        })
                      }
                      disabled={removeTeamMemberMutation.isPending}
                      className="text-xs px-2 py-1 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 disabled:opacity-50"
                    >
                      Retirer
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ── Modal création / édition de tâche ── */}
      {showTaskModal && (
        <TaskFormModal
          task={editingTask}
          teams={teams}
          defaultTeamId={selectedTeamId ? Number(selectedTeamId) : undefined}
          onClose={() => {
            setShowTaskModal(false);
            setEditingTask(undefined);
          }}
          onSuccess={() => qc.invalidateQueries({ queryKey: ['tasks'] })}
        />
      )}

      {/* ── Modal affectation ── */}
      {assignTask && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 px-4">
          <div className="bg-white rounded-2xl shadow-xl p-6 w-full max-w-sm">
            <div className="flex justify-between items-center mb-3">
              <h2 className="text-lg font-bold text-gray-800">Affecter un utilisateur</h2>
              <button onClick={() => setAssignTask(null)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">
                ×
              </button>
            </div>

            <p className="text-sm text-gray-500 mb-4">
              <span className="font-medium text-gray-700">{assignTask.title}</span>
              {' '}— {assignTask.assigned_people}/{assignTask.required_people} pers.
            </p>

            {assignError && (
              <div className="mb-3 p-2 bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg">
                {assignError}
              </div>
            )}

            <select
              value={selectedUserId}
              onChange={(e) =>
                setSelectedUserId(e.target.value ? Number(e.target.value) : '')
              }
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300 mb-4"
            >
              <option value="">— Sélectionner un utilisateur —</option>
              {assignableUsers.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.name} ({u.role === 'manager' ? 'Manager' : 'Employé'})
                </option>
              ))}
            </select>

            <div className="flex gap-3">
              <button
                onClick={() => setAssignTask(null)}
                className="flex-1 py-2 border border-gray-200 text-gray-600 rounded-lg text-sm hover:bg-gray-50 transition"
              >
                Annuler
              </button>
              <button
                onClick={() =>
                  selectedUserId &&
                  assignMutation.mutate({
                    task_id: assignTask.id,
                    assignee_id: Number(selectedUserId),
                  })
                }
                disabled={!selectedUserId || assignMutation.isPending}
                className="flex-1 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 disabled:opacity-50 transition"
              >
                {assignMutation.isPending ? '...' : 'Affecter'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
