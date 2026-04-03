import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { format } from 'date-fns';
import api from '../api/client';
import type { Team, TeamDetail, User, UserRole } from '../types';

const ROLE_LABELS: Record<UserRole, string> = {
  pending: 'En attente',
  employee: 'Employé',
  manager: 'Manager',
};

const ROLE_STYLES: Record<UserRole, string> = {
  pending: 'bg-yellow-100 text-yellow-700',
  employee: 'bg-blue-100 text-blue-700',
  manager: 'bg-purple-100 text-purple-700',
};

type FilterRole = UserRole | '';

export default function AdminPage() {
  const qc = useQueryClient();
  const [filterRole, setFilterRole] = useState<FilterRole>('');
  const [alertMsg, setAlertMsg] = useState('');
  const [alertSending, setAlertSending] = useState(false);
  const [alertFeedback, setAlertFeedback] = useState<string | null>(null);
  const [defaultDay, setDefaultDay] = useState<string>('');
  const [defaultDayFeedback, setDefaultDayFeedback] = useState<string | null>(null);
  const [appName, setAppName] = useState<string>('');
  const [appNameFeedback, setAppNameFeedback] = useState<string | null>(null);
  const [teamName, setTeamName] = useState('');
  const [selectedTeamId, setSelectedTeamId] = useState<number | ''>('');
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<number | ''>('');
  const [selectedManagerId, setSelectedManagerId] = useState<number | ''>('');
  const [teamFeedback, setTeamFeedback] = useState<string | null>(null);

  // Récupérer le jour par défaut et le nom de l'application au démarrage
  useEffect(() => {
    const fetchSettings = async () => {
      try {
        const defaultDayRes = await api.get('/admin/settings/default-day');
        if (defaultDayRes.data.day) {
          setDefaultDay(defaultDayRes.data.day);
        } else {
          setDefaultDay(format(new Date(), 'yyyy-MM-dd'));
        }
      } catch {
        setDefaultDay(format(new Date(), 'yyyy-MM-dd'));
      }
      
      try {
        const appNameRes = await api.get<{ app_name: string }>('/admin/settings/app-name');
        if (appNameRes.data.app_name) {
          setAppName(appNameRes.data.app_name);
        }
      } catch {
        setAppName('Team Scheduler');
      }
    };
    fetchSettings();
  }, []);

  const { data: users = [], isLoading } = useQuery({
    queryKey: ['users', filterRole],
    queryFn: () =>
      api
        .get<User[]>('/users', { params: filterRole ? { role: filterRole } : {} })
        .then((r) => r.data),
  });

  const { data: teams = [] } = useQuery({
    queryKey: ['teams'],
    queryFn: () => api.get<Team[]>('/teams').then((r) => r.data),
  });

  const { data: selectedTeam } = useQuery({
    queryKey: ['team-detail', selectedTeamId],
    queryFn: () => api.get<TeamDetail>(`/teams/${selectedTeamId}`).then((r) => r.data),
    enabled: !!selectedTeamId,
  });

  const assignRole = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: UserRole }) =>
      api.patch<User>(`/auth/admin/users/${userId}/role`, { role }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['users'] }),
  });

  const setDefaultDayMutation = useMutation({
    mutationFn: (day: string) =>
      api.post('/admin/settings/default-day', { value: day }),
    onSuccess: () => {
      setDefaultDayFeedback('✅ Jour par défaut défini.');
      setTimeout(() => setDefaultDayFeedback(null), 3000);
    },
    onError: () => {
      setDefaultDayFeedback('❌ Erreur lors de la sauvegarde.');
    },
  });

  const setAppNameMutation = useMutation({
    mutationFn: (name: string) =>
      api.post('/admin/settings/app-name', { value: name }),
    onSuccess: () => {
      setAppNameFeedback('✅ Nom de l\'application défini.');
      qc.invalidateQueries({ queryKey: ['app-name'] });
      setTimeout(() => setAppNameFeedback(null), 3000);
    },
    onError: () => {
      setAppNameFeedback('❌ Erreur lors de la sauvegarde.');
    },
  });

  const createTeamMutation = useMutation({
    mutationFn: (name: string) => api.post<Team>('/teams', { name }),
    onSuccess: () => {
      setTeamFeedback('✅ Equipe créée.');
      setTeamName('');
      qc.invalidateQueries({ queryKey: ['teams'] });
    },
    onError: () => setTeamFeedback('❌ Impossible de créer l\'équipe.'),
  });

  const addMemberMutation = useMutation({
    mutationFn: ({ teamId, userId }: { teamId: number; userId: number }) =>
      api.post(`/teams/${teamId}/members`, { user_ids: [userId] }),
    onSuccess: () => {
      setTeamFeedback('✅ Employé ajouté à l\'équipe.');
      setSelectedEmployeeId('');
      qc.invalidateQueries({ queryKey: ['team-detail', selectedTeamId] });
      qc.invalidateQueries({ queryKey: ['teams'] });
    },
    onError: () => setTeamFeedback('❌ Impossible d\'ajouter cet employé.'),
  });

  const removeMemberMutation = useMutation({
    mutationFn: ({ teamId, userId }: { teamId: number; userId: number }) =>
      api.delete(`/teams/${teamId}/members/${userId}`),
    onSuccess: () => {
      setTeamFeedback('✅ Employé retiré de l\'équipe.');
      qc.invalidateQueries({ queryKey: ['team-detail', selectedTeamId] });
      qc.invalidateQueries({ queryKey: ['teams'] });
    },
    onError: () => setTeamFeedback('❌ Impossible de retirer cet employé.'),
  });

  const setTeamManagerMutation = useMutation({
    mutationFn: ({ teamId, managerId }: { teamId: number; managerId: number | null }) =>
      api.patch(`/teams/${teamId}/manager`, { manager_id: managerId }),
    onSuccess: () => {
      setTeamFeedback('✅ Manager de l\'équipe défini.');
      qc.invalidateQueries({ queryKey: ['team-detail', selectedTeamId] });
      qc.invalidateQueries({ queryKey: ['teams'] });
    },
    onError: () => setTeamFeedback('❌ Impossible de définir le manager.'),
  });

  const sendBroadcast = async () => {
    if (!alertMsg.trim()) return;
    setAlertSending(true);
    setAlertFeedback(null);
    try {
      await api.post('/alerts', { message: alertMsg });
      setAlertFeedback('✅ Alerte envoyée à tous les employés.');
      setAlertMsg('');
    } catch {
      setAlertFeedback("❌ Erreur lors de l'envoi.");
    } finally {
      setAlertSending(false);
    }
  };

  const filters: FilterRole[] = ['', 'pending', 'employee', 'manager'];
  const employees = users.filter((u) => u.role === 'employee');
  const managers = users.filter((u) => u.role === 'manager');

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-8">
      {/* ── Gestion utilisateurs ── */}
      <section>
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <h1 className="text-2xl font-bold text-gray-800">Gestion des utilisateurs</h1>
          <div className="flex-1" />
          <div className="flex gap-2 flex-wrap">
            {filters.map((r) => (
              <button
                key={r}
                onClick={() => setFilterRole(r)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition ${
                  filterRole === r
                    ? 'bg-indigo-600 text-white'
                    : 'bg-white text-gray-600 border border-gray-200 hover:border-indigo-300'
                }`}
              >
                {r === '' ? 'Tous' : ROLE_LABELS[r]}
              </button>
            ))}
          </div>
        </div>

        {isLoading ? (
          <div className="text-center text-gray-400 py-12">Chargement…</div>
        ) : users.length === 0 ? (
          <div className="text-center text-gray-400 py-12">Aucun utilisateur</div>
        ) : (
          <div className="bg-white rounded-xl shadow-sm border border-gray-100 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-gray-500 text-xs uppercase">
                  <th className="text-left px-4 py-3">Nom</th>
                  <th className="text-left px-4 py-3">Telegram</th>
                  <th className="text-left px-4 py-3">Rôle actuel</th>
                  <th className="text-right px-4 py-3">Changer le rôle</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {users.map((user) => (
                  <tr key={user.id} className="hover:bg-gray-50 transition">
                    <td className="px-4 py-3 font-medium text-gray-800">{user.name}</td>
                    <td className="px-4 py-3 text-gray-500">
                      {user.telegram_username
                        ? `@${user.telegram_username}`
                        : `#${user.telegram_user_id}`}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-xs font-medium ${ROLE_STYLES[user.role]}`}
                      >
                        {ROLE_LABELS[user.role]}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex justify-end gap-2">
                        {(['employee', 'manager'] as UserRole[])
                          .filter((r) => r !== user.role)
                          .map((r) => (
                            <button
                              key={r}
                              onClick={() => assignRole.mutate({ userId: user.id, role: r })}
                              disabled={assignRole.isPending}
                              className="px-2.5 py-1 bg-indigo-50 text-indigo-600 rounded text-xs font-medium hover:bg-indigo-100 transition disabled:opacity-50"
                            >
                              → {ROLE_LABELS[r]}
                            </button>
                          ))}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── Jour par défaut ── */}
      <section className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-800 mb-3">📅 Jour par défaut pour la planification</h2>
        <p className="text-xs text-gray-400 mb-4">
          Définissez le jour qui s'affichera par défaut pour tous les employés et managers au chargement de leur planning.
        </p>
        {defaultDayFeedback && (
          <div className="mb-3 p-2 bg-gray-50 border border-gray-200 text-sm rounded-lg text-gray-700">
            {defaultDayFeedback}
          </div>
        )}
        <div className="flex gap-3 items-end">
          <div>
            <label className="text-xs font-medium text-gray-700 block mb-1">Date</label>
            <input
              type="date"
              value={defaultDay}
              onChange={(e) => setDefaultDay(e.target.value)}
              className="px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
          </div>
          <button
            onClick={() => setDefaultDayMutation.mutate(defaultDay)}
            disabled={setDefaultDayMutation.isPending}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition disabled:opacity-50"
          >
            {setDefaultDayMutation.isPending ? '...' : 'Enregistrer'}
          </button>
        </div>
      </section>

      {/* ── Nom de l'application ── */}
      <section className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-800 mb-3">🏷️ Nom de l'application</h2>
        <p className="text-xs text-gray-400 mb-4">
          Configurez le nom de l'application affiché dans la barre de navigation et le titre de la page.
        </p>
        {appNameFeedback && (
          <div className="mb-3 p-2 bg-gray-50 border border-gray-200 text-sm rounded-lg text-gray-700">
            {appNameFeedback}
          </div>
        )}
        <div className="flex gap-3 items-end">
          <div className="flex-1">
            <label className="text-xs font-medium text-gray-700 block mb-1">Nom</label>
            <input
              type="text"
              value={appName}
              onChange={(e) => setAppName(e.target.value)}
              placeholder="Team Scheduler"
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
          </div>
          <button
            onClick={() => appName.trim() && setAppNameMutation.mutate(appName.trim())}
            disabled={!appName.trim() || setAppNameMutation.isPending}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition disabled:opacity-50"
          >
            {setAppNameMutation.isPending ? '...' : 'Enregistrer'}
          </button>
        </div>
      </section>

      {/* ── Gestion des équipes ── */}
      <section className="bg-white rounded-xl border border-gray-100 shadow-sm p-6 space-y-4">
        <h2 className="text-lg font-bold text-gray-800">👥 Gestion des équipes</h2>
        {teamFeedback && (
          <div className="p-2 bg-gray-50 border border-gray-200 text-sm rounded-lg text-gray-700">
            {teamFeedback}
          </div>
        )}

        <div className="flex gap-3 flex-wrap">
          <input
            type="text"
            value={teamName}
            onChange={(e) => setTeamName(e.target.value)}
            placeholder="Nom de la nouvelle équipe"
            className="flex-1 min-w-60 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
          />
          <button
            onClick={() => teamName.trim() && createTeamMutation.mutate(teamName.trim())}
            disabled={!teamName.trim() || createTeamMutation.isPending}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition disabled:opacity-50"
          >
            {createTeamMutation.isPending ? '...' : '+ Créer une équipe'}
          </button>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div className="space-y-3">
            <label className="text-xs font-medium text-gray-700 block">Equipe</label>
            <select
              value={selectedTeamId}
              onChange={(e) => {
                setSelectedTeamId(e.target.value ? Number(e.target.value) : '');
                setSelectedManagerId('');
              }}
              className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
            >
              <option value="">— Sélectionner une équipe —</option>
              {teams.map((team) => (
                <option key={team.id} value={team.id}>{team.name}</option>
              ))}
            </select>

            <label className="text-xs font-medium text-gray-700 block">Manager 🎯</label>
            <div className="flex gap-2">
              <select
                value={selectedManagerId}
                onChange={(e) => setSelectedManagerId(e.target.value ? Number(e.target.value) : '')}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                disabled={!selectedTeamId}
              >
                <option value="">— Aucun —</option>
                {managers.map((manager) => (
                  <option key={manager.id} value={manager.id}>{manager.name}</option>
                ))}
              </select>
              <button
                onClick={() =>
                  selectedTeamId &&
                  selectedManagerId &&
                  setTeamManagerMutation.mutate({ teamId: Number(selectedTeamId), managerId: Number(selectedManagerId) })
                }
                disabled={!selectedTeamId || !selectedManagerId || setTeamManagerMutation.isPending}
                className="px-3 py-2 bg-purple-100 text-purple-700 rounded-lg text-sm font-medium hover:bg-purple-200 transition disabled:opacity-50"
              >
                {setTeamManagerMutation.isPending ? '...' : 'Affecter'}
              </button>
            </div>

            <label className="text-xs font-medium text-gray-700 block">Ajouter un employé</label>
            <div className="flex gap-2">
              <select
                value={selectedEmployeeId}
                onChange={(e) => setSelectedEmployeeId(e.target.value ? Number(e.target.value) : '')}
                className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
                disabled={!selectedTeamId}
              >
                <option value="">— Sélectionner —</option>
                {employees.map((employee) => (
                  <option key={employee.id} value={employee.id}>{employee.name}</option>
                ))}
              </select>
              <button
                onClick={() =>
                  selectedTeamId &&
                  selectedEmployeeId &&
                  addMemberMutation.mutate({ teamId: Number(selectedTeamId), userId: Number(selectedEmployeeId) })
                }
                disabled={!selectedTeamId || !selectedEmployeeId || addMemberMutation.isPending}
                className="px-3 py-2 bg-indigo-50 text-indigo-700 rounded-lg text-sm font-medium hover:bg-indigo-100 transition disabled:opacity-50"
              >
                Ajouter
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <p className="text-xs font-medium text-gray-700">Détails de l'équipe</p>
            {!selectedTeamId ? (
              <div className="text-sm text-gray-400">Sélectionnez une équipe pour voir ses détails.</div>
            ) : (
              <div className="space-y-3">
                {selectedTeam?.manager && (
                  <div className="p-3 bg-purple-50 border border-purple-200 rounded-lg">
                    <p className="text-xs font-medium text-purple-600 mb-1">Manager 🎯</p>
                    <p className="text-sm text-purple-900 font-semibold">{selectedTeam.manager.name}</p>
                  </div>
                )}
                <div>
                  <p className="text-xs font-medium text-gray-700 mb-2">Membres</p>
                  {(selectedTeam?.members ?? []).length === 0 ? (
                    <div className="text-sm text-gray-400">Aucun employé dans cette équipe.</div>
                  ) : (
                    <div className="space-y-2">
                      {selectedTeam!.members.map((member) => (
                        <div key={member.id} className="flex items-center justify-between px-3 py-2 bg-gray-50 rounded-lg border border-gray-100">
                          <span className="text-sm text-gray-700">{member.name}</span>
                          <button
                            onClick={() =>
                              selectedTeamId &&
                              removeMemberMutation.mutate({ teamId: Number(selectedTeamId), userId: member.id })
                            }
                            disabled={removeMemberMutation.isPending}
                            className="text-xs px-2.5 py-1 bg-red-50 text-red-600 rounded-lg hover:bg-red-100 transition disabled:opacity-50"
                          >
                            Retirer
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      </section>

      {/* ── Diffusion d'alertes ── */}
      <section className="bg-white rounded-xl border border-gray-100 shadow-sm p-6">
        <h2 className="text-lg font-bold text-gray-800 mb-3">📢 Diffuser une alerte Telegram</h2>
        <p className="text-xs text-gray-400 mb-3">
          Envoie un message à tous les employés via le bot Telegram.
        </p>
        {alertFeedback && (
          <div className="mb-3 p-2 bg-gray-50 border border-gray-200 text-sm rounded-lg text-gray-700">
            {alertFeedback}
          </div>
        )}
        <div className="flex gap-3">
          <input
            type="text"
            placeholder="Message de l'alerte…"
            value={alertMsg}
            onChange={(e) => setAlertMsg(e.target.value)}
            className="flex-1 px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
          />
          <button
            onClick={sendBroadcast}
            disabled={alertSending || !alertMsg.trim()}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg text-sm font-medium hover:bg-indigo-700 transition disabled:opacity-50"
          >
            {alertSending ? '...' : 'Envoyer'}
          </button>
        </div>
      </section>
    </div>
  );
}
