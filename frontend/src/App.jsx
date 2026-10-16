import { useEffect, useState } from 'react';
import { Navigate, Route, Routes } from 'react-router';
import { Box, Center, Loader, Stack, Text } from '@mantine/core';
import { IconCalendar, IconClipboardList, IconReceipt2 } from '@tabler/icons-react';

import { getMe, logout } from './api/auth';
import { AppLayout } from './layout/AppLayout';
import { PortalLayout } from './layout/PortalLayout';
import { CompletarPerfilPage } from './pages/auth/CompletarPerfilPage';
import { ConfirmarEmailPage } from './pages/auth/ConfirmarEmailPage';
import { LoginPage } from './pages/auth/LoginPage';
import { PendienteAprobacionPage } from './pages/auth/PendienteAprobacionPage';
import { BudgetsListPage } from './pages/budgets/BudgetsListPage';
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
import { ProfilePage } from './pages/profile/ProfilePage';
import { UsersApprovalPage } from './pages/users/UsersApprovalPage';
import { ConversacionesPage } from './pages/conversaciones/ConversacionesPage';
import { WhatsAppSimPage } from './pages/whatsapp/WhatsAppSimPage';
import { Footer } from './components/Footer';

const LINKS_CONTRATISTA = [
  { label: 'Mis solicitudes', path: '/portal/solicitudes', icon: IconClipboardList },
  { label: 'Mis presupuestos', path: '/portal/presupuestos', icon: IconReceipt2 },
  { label: 'Calendario', path: '/calendario', icon: IconCalendar },
];

const LINKS_INSPECTOR = [{ label: 'Reclamos', path: '/reclamos', icon: IconClipboardList }];

function ConFooter({ children }) {
  return (
    <Box style={{ display: 'flex', flexDirection: 'column', minHeight: '100vh' }}>
      <Box style={{ flex: 1 }}>{children}</Box>
      <Footer />
    </Box>
  );
}

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
    verificarSesion({ bloqueante: true });
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

  // Sólo la verificación inicial muestra el loader: las posteriores corren en segundo
  // plano porque reemplazar el árbol por el loader desmonta la página actual.
  async function verificarSesion({ bloqueante = false } = {}) {
    if (bloqueante) setVerificando(true);
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
      // Error de red o del servidor: no dice nada sobre la sesión, se mantiene la actual
    } finally {
      clearTimeout(timer);
      if (bloqueante) setVerificando(false);
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
      <ConFooter>
        <Center h="100vh">
          <Stack align="center" gap="xs">
            <Loader color="teal" />
            <Text size="sm" c="dimmed">
              Verificando sesión…
            </Text>
          </Stack>
        </Center>
      </ConFooter>
    );
  }

  // No autenticado → login
  if (!usuario) {
    return (
      <ConFooter>
        <Routes>
          <Route path="/confirmar" element={<ConfirmarEmailPage />} />
          <Route path="*" element={<LoginPage onLogin={handleLogin} />} />
        </Routes>
      </ConFooter>
    );
  }

  // Autenticado pero necesita completar perfil
  if (usuario.estado === 'PENDIENTE_PERFIL') {
    return (
      <ConFooter>
        <CompletarPerfilPage usuario={usuario} onComplete={() => verificarSesion()} />
      </ConFooter>
    );
  }

  // Autenticado pero pendiente de aprobación o rechazado
  if (usuario.estado === 'PENDIENTE_APROBACION' || usuario.estado === 'RECHAZADO') {
    return (
      <ConFooter>
        <PendienteAprobacionPage onLogout={handleLogout} />
      </ConFooter>
    );
  }

  // Contratista aprobado → portal del contratista (experiencia acotada)
  if (usuario.tipo === 'CONTRATISTA') {
    return (
      <Routes>
        <Route element={<PortalLayout links={LINKS_CONTRATISTA} etiquetaRol="Contratista" />}>
          <Route index element={<Navigate to="/portal/solicitudes" replace />} />
          <Route path="/portal/solicitudes" element={<MySolicitudesPage />} />
          <Route path="/portal/presupuestos" element={<MyPresupuestosPage />} />
          <Route path="/calendario" element={<CalendarPage />} />
          <Route path="/perfil" element={<ProfilePage />} />
          <Route path="/portal/reclamos/:id/presupuestar" element={<PresupuestarReclamoPage />} />
          {/* Cualquier otra ruta redirige al portal, así un contratista no accede a vistas de admin */}
          <Route path="*" element={<Navigate to="/portal/solicitudes" replace />} />
        </Route>
      </Routes>
    );
  }

  // Inspector aprobado → sólo ve reclamos, los comenta y les agrega fotos
  if (usuario.tipo === 'INSPECTOR') {
    return (
      <Routes>
        <Route element={<PortalLayout links={LINKS_INSPECTOR} etiquetaRol="Inspector" />}>
          <Route path="/reclamos" element={<ClaimsListPage />} />
          <Route path="/perfil" element={<ProfilePage />} />
          <Route path="*" element={<Navigate to="/reclamos" replace />} />
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
        <Route path="/contratistas/nuevo" element={<NewContractorPage />} />
        <Route path="/contratistas" element={<ContractorsListPage />} />
        <Route path="/contratistas/listas" element={<ContractorListsPage />} />
        <Route path="/contratistas/:id/editar" element={<EditContractorPage />} />
        <Route path="/presupuestos" element={<BudgetsListPage />} />
        <Route path="/calendario" element={<CalendarPage />} />
        <Route path="/reportes" element={<ReportsPage />} />
        <Route path="/solicitudes" element={<UsersApprovalPage />} />
        <Route path="/configuracion" element={<SettingsPage />} />
        <Route path="/perfil" element={<ProfilePage />} />
        <Route path="/whatsapp" element={<WhatsAppSimPage />} />
        <Route path="/conversaciones" element={<ConversacionesPage />} />
        <Route path="*" element={<Navigate to="/reclamos" replace />} />
      </Route>
    </Routes>
  );
}

export default App;
