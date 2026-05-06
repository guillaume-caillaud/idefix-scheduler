import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import LoginPage from './pages/LoginPage';
import AdminLoginPage from './pages/AdminLoginPage';
import AdminPage from './pages/AdminPage';
import ManagerPage from './pages/ManagerPage';
import EmployeePage from './pages/EmployeePage';
import ProfilePage from './pages/ProfilePage';
import TelegramAuthPage from './pages/TelegramAuthPage';
import Navbar from './components/Navbar';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});

function AppRoutes() {
  const { user, isAdmin, logout, pendingBlocked } = useAuth();
  const location = useLocation();

  // Non authentifié
  if (!user && !isAdmin) {
    return (
      <Routes>
        <Route path="/" element={<LoginPage />} />
        <Route path="/admin-login" element={<AdminLoginPage />} />
        <Route path="/telegram-auth" element={<TelegramAuthPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    );
  }

  if (location.pathname === '/telegram-auth') {
    return <TelegramAuthPage />;
  }

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
            Votre compte a bien été créé, mais il doit être validé par un administrateur. Lorsque cela
            aura été fait, veuillez raffraîchir cette page.
          </p>
          <div className="flex gap-2 justify-center">
            <button
              onClick={() => window.location.reload()}
              className="text-sm px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition"
            >
              Raffraîchir
            </button>
            <button
              onClick={logout}
              className="text-sm px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition"
            >
              Se déconnecter
            </button>
          </div>
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
