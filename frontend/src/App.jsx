import { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import { Center, Loader, Stack, Text } from '@mantine/core';

import { getMe, logout } from './api/auth';
import { AppLayout } from './layout/AppLayout';
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
import { ContractorsListPage } from './pages/contractors/ContractorsListPage';
import { EditContractorPage } from './pages/contractors/EditContractorPage';
import { NewContractorPage } from './pages/contractors/NewContractorPage';
import { DashboardPage } from './pages/dashboard/DashboardPage';
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
    const controlador = new AbortController();
    const timer = setTimeout(() => controlador.abort(), 8000);
    try {
      const usuarioReal = await getMe(controlador.signal);
      if (usuarioReal) {
        localStorage.setItem('infrabot_user', JSON.stringify(usuarioReal));
        setUsuario(usuarioReal);
      } else {
        localStorage.removeItem('infrabot_user');
        setUsuario(null);
      }
    } catch {
      localStorage.removeItem('infrabot_user');
      setUsuario(null);
    } finally {
      clearTimeout(timer);
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

  if (verificando) {
    return (
      <Center h="100vh">
        <Stack align="center" gap="xs">
          <Loader color="teal" />
          <Text size="sm" c="dimmed">
            Verificando sesión…
          </Text>
        </Stack>
      </Center>
    );
  }

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

  // Aprobado → app normal
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route index element={<Navigate to="/reclamos" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/reclamos/nuevo" element={<NewClaimPage />} />
        <Route path="/reclamos" element={<ClaimsListPage />} />
        <Route path="/reclamos/:id/editar" element={<EditClaimPage />} />
        <Route path="/contratistas/nuevo" element={<NewContractorPage />} />
        <Route path="/contratistas" element={<ContractorsListPage />} />
        <Route path="/contratistas/:id/editar" element={<EditContractorPage />} />
        <Route path="/presupuestos/nuevo" element={<NewBudgetPage />} />
        <Route path="/presupuestos" element={<BudgetsListPage />} />
        <Route path="/presupuestos/:id/editar" element={<EditBudgetPage />} />
        <Route path="/calendario" element={<CalendarPage />} />
        <Route path="/reportes" element={<ReportsPage />} />
        <Route path="/solicitudes" element={<UsersApprovalPage />} />
        <Route path="/configuracion" element={<SettingsPage />} />
      </Route>
    </Routes>
  );
}

export default App;
