import { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';

import { getMe, logout } from './api/auth';
import { AppLayout } from './layout/AppLayout';
import { ContractorLayout } from './layout/ContractorLayout';
import { CompletarPerfilPage } from './pages/auth/CompletarPerfilPage';
import { ConfirmarEmailPage } from './pages/auth/ConfirmarEmailPage';
import { LoginPage } from './pages/auth/LoginPage';
import { PendienteAprobacionPage } from './pages/auth/PendienteAprobacionPage';
import { BudgetsListPage } from './pages/budgets/BudgetsListPage';
import { EditBudgetPage } from './pages/budgets/EditBudgetPage';
import { NewBudgetPage } from './pages/budgets/NewBudgetPage';
import { CalendarPage } from './pages/calendar/CalendarPage';
import { ClaimsListPage } from './pages/claims/ClaimsListPage';
import { EditClaimPage } from './pages/claims/EditClaimPage';
import { NewClaimPage } from './pages/claims/NewClaimPage';
import { PresupuestarReclamoPage } from './pages/claims/PresupuestarReclamoPage';
import { ContractorListsPage } from './pages/contractors/ContractorListsPage';
import { ContractorsListPage } from './pages/contractors/ContractorsListPage';
import { EditContractorPage } from './pages/contractors/EditContractorPage';
import { NewContractorPage } from './pages/contractors/NewContractorPage';
import { DashboardPage } from './pages/dashboard/DashboardPage';
import { MyPresupuestosPage } from './pages/portal/MyPresupuestosPage';
import { MySolicitudesPage } from './pages/portal/MySolicitudesPage';
import { ReportsPage } from './pages/reports/ReportsPage';
import { SettingsPage } from './pages/settings/SettingsPage';
import { UsersApprovalPage } from './pages/users/UsersApprovalPage';

function getUsuarioGuardado() {
  try {
    return JSON.parse(localStorage.getItem('infrabot_user') || 'null');
  } catch {
    return null;
  }
}

function App() {
  const [usuario, setUsuario] = useState(getUsuarioGuardado);
  const [verificando, setVerificando] = useState(true);

  // Al montar la app, verificar la sesión real contra el backend
  useEffect(() => {
    verificarSesion();
  }, []);

  // Verificar sesión cuando el usuario navega con "atrás/adelante" o vuelve a la pestaña
  useEffect(() => {
    const handlePopState = () => verificarSesion();
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') verificarSesion();
    };
    const handlePageShow = (e) => {
      if (e.persisted) verificarSesion();
    };

    window.addEventListener('popstate', handlePopState);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('pageshow', handlePageShow);
    return () => {
      window.removeEventListener('popstate', handlePopState);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
      window.removeEventListener('pageshow', handlePageShow);
    };
  }, []);

  async function verificarSesion() {
    setVerificando(true);
    try {
      const usuarioReal = await getMe();
      if (usuarioReal) {
        localStorage.setItem('infrabot_user', JSON.stringify(usuarioReal));
        setUsuario(usuarioReal);
      } else {
        localStorage.removeItem('infrabot_user');
        setUsuario(null);
      }
    } catch {
      // Si no puede conectar al backend, limpiar sesión por seguridad
      localStorage.removeItem('infrabot_user');
      setUsuario(null);
    } finally {
      setVerificando(false);
    }
  }

  const handleLogin = () => {
    setUsuario(getUsuarioGuardado());
    window.history.replaceState(null, '', '/');
  };

  const handleLogout = async () => {
    try {
      await logout();
    } catch {
      // Si falla, igual cerramos la sesión local
    }
    localStorage.removeItem('infrabot_user');
    setUsuario(null);
  };

  // Mientras verifica la sesión, no renderizar nada (evita flash)
  if (verificando) return null;

  // No autenticado → login
  if (!usuario) {
    return (
      <Routes>
        <Route path="/confirmar" element={<ConfirmarEmailPage />} />
        <Route path="*" element={<LoginPage onLogin={handleLogin} />} />
      </Routes>
    );
  }

  // Autenticado pero necesita completar perfil
  if (usuario.estado === 'PENDIENTE_PERFIL') {
    return (
      <CompletarPerfilPage
        usuario={usuario}
        onComplete={() => verificarSesion()}
      />
    );
  }

  // Autenticado pero pendiente de aprobación o rechazado
  if (usuario.estado === 'PENDIENTE_APROBACION' || usuario.estado === 'RECHAZADO') {
    return <PendienteAprobacionPage onLogout={handleLogout} />;
  }

  // Contratista aprobado → portal del contratista (experiencia acotada)
  if (usuario.tipo === 'CONTRATISTA') {
    return (
      <Routes>
        <Route element={<ContractorLayout />}>
          <Route index element={<Navigate to="/portal/solicitudes" replace />} />
          <Route path="/portal/solicitudes" element={<MySolicitudesPage />} />
          <Route path="/portal/presupuestos" element={<MyPresupuestosPage />} />
          <Route
            path="/portal/reclamos/:id/presupuestar"
            element={<PresupuestarReclamoPage />}
          />
          {/* Cualquier otra ruta redirige al portal, así un contratista no accede a vistas de admin */}
          <Route path="*" element={<Navigate to="/portal/solicitudes" replace />} />
        </Route>
      </Routes>
    );
  }

  // Administrador aprobado → app completa
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/reclamos" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/reclamos/nuevo" element={<NewClaimPage />} />
        <Route path="/reclamos" element={<ClaimsListPage />} />
        <Route path="/reclamos/:id/editar" element={<EditClaimPage />} />
        <Route path="/reclamos/:id/presupuestar" element={<PresupuestarReclamoPage />} />
        <Route path="/contratistas/nuevo" element={<NewContractorPage />} />
        <Route path="/contratistas" element={<ContractorsListPage />} />
        <Route path="/contratistas/listas" element={<ContractorListsPage />} />
        <Route path="/contratistas/:id/editar" element={<EditContractorPage />} />
        <Route path="/presupuestos/nuevo" element={<NewBudgetPage />} />
        <Route path="/presupuestos" element={<BudgetsListPage />} />
        <Route path="/presupuestos/:id/editar" element={<EditBudgetPage />} />
        <Route path="/calendario" element={<CalendarPage />} />
        <Route path="/reportes" element={<ReportsPage />} />
        <Route path="/solicitudes" element={<UsersApprovalPage />} />
        <Route path="/configuracion" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/reclamos" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
