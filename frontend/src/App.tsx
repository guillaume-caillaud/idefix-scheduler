import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import LoginPage from './pages/LoginPage';
import AdminPage from './pages/AdminPage';
import ManagerPage from './pages/ManagerPage';
import EmployeePage from './pages/EmployeePage';
import ProfilePage from './pages/ProfilePage';
import Navbar from './components/Navbar';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});

function AppRoutes() {
  const { user, isAdmin, logout, pendingBlocked } = useAuth();

  // Non authentifié
  if (!user && !isAdmin) return <LoginPage />;

  if (pendingBlocked) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
        <div className="bg-white rounded-2xl shadow-xl p-8 max-w-sm text-center">
          <div className="text-4xl mb-3">🔒</div>
          <h2 className="text-xl font-bold text-gray-800 mb-2">Accès en attente de validation</h2>
          <p className="text-gray-500 text-sm mb-6">
            Votre compte Telegram existe, mais il n'a pas encore été validé par un administrateur.
          </p>
          <button onClick={logout} className="text-sm text-indigo-600 hover:underline">
            Revenir à la connexion
          </button>
        </div>
      </div>
    );
  }

  // Compte créé mais rôle non encore attribué
  if (user?.role === 'pending') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
        <div className="bg-white rounded-2xl shadow-xl p-8 max-w-sm text-center">
          <div className="text-4xl mb-3">⏳</div>
          <h2 className="text-xl font-bold text-gray-800 mb-2">En attente d'activation</h2>
          <p className="text-gray-500 text-sm mb-6">
            Ton compte a bien été créé. Un administrateur doit t'attribuer un rôle avant que tu
            puisses accéder à l'application.
          </p>
          <button
            onClick={logout}
            className="text-sm text-indigo-600 hover:underline"
          >
            Se déconnecter
          </button>
        </div>
      </div>
    );
  }

  const defaultPath = isAdmin ? '/admin' : user?.role === 'manager' ? '/manager' : '/employee';

  return (
    <div className="min-h-screen bg-gray-50">
      <Navbar />
      <Routes>
        {isAdmin && <Route path="/admin" element={<AdminPage />} />}
        {user?.role === 'manager' && <Route path="/manager" element={<ManagerPage />} />}
        {user?.role === 'employee' && <Route path="/employee" element={<EmployeePage />} />}
        {!isAdmin && user && <Route path="/profile" element={<ProfilePage />} />}
        <Route path="*" element={<Navigate to={defaultPath} replace />} />
      </Routes>
    </div>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}
