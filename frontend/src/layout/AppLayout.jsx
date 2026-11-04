import { useCallback, useEffect, useReducer, useState } from 'react';
import {
  AppShell,
  Avatar,
  Badge,
  Burger,
  Divider,
  Group,
  Menu,
  NavLink,
  ActionIcon,
  Box,
  Text,
  Tooltip,
  UnstyledButton,
  em,
} from '@mantine/core';
import { useDisclosure, useMediaQuery } from '@mantine/hooks';
import { Outlet, useLocation, useNavigate } from 'react-router';
import {
  IconHome,
  IconClipboardList,
  IconTruck,
  IconReceipt2,
  IconCalendar,
  IconChartBar,
  IconSettings,
  IconChevronDown,
  IconChevronLeft,
  IconChevronRight,
  IconLogout,
  IconUser,
  IconUserCheck,
  IconUserShield,
  IconUsersGroup,
  IconBrandWhatsapp,
  IconMessageChatbot,
} from '@tabler/icons-react';
import logo from '../assets/logo-infrabot.jpeg';
import { Footer } from '../components/Footer';
import { NotificationBell } from './NotificationBell';
import { SimuladorTiempoControl } from '../components/SimuladorTiempoControl';
import { listarUsuariosPendientes } from '../api/usuarios';
import {
  ConversacionesProvider,
  useConversaciones,
} from '../pages/conversaciones/ConversacionesContext';
import { esAdministrador } from '../utils/auth';
import classes from './AppLayout.module.css';

// `contador` dice qué número de pendientes mostrar al lado (ver `contadores` abajo).
const secciones = [
  { titulo: null, links: [{ label: 'Dashboard', path: '/dashboard', icon: IconHome }] },
  {
    titulo: 'Operación',
    links: [
      { label: 'Reclamos', path: '/reclamos', icon: IconClipboardList },
      {
        label: 'Presupuestos',
        path: '/presupuestos',
        icon: IconReceipt2,
        contador: 'evaluacion',
        ayudaContador: 'reclamos con ofertas para comparar',
      },
      { label: 'Calendario', path: '/calendario', icon: IconCalendar },
      {
        label: 'Conversaciones',
        path: '/conversaciones',
        icon: IconMessageChatbot,
        contador: 'chats',
      },
    ],
  },
  {
    titulo: 'Contratistas',
    links: [
      { label: 'Contratistas', path: '/contratistas', icon: IconTruck, exact: true },
      {
        label: 'Listas de contratistas',
        path: '/contratistas/listas',
        icon: IconUsersGroup,
        soloAdmin: true,
      },
    ],
  },
  {
    titulo: 'Administración',
    links: [
      { label: 'Reportes', path: '/reportes', icon: IconChartBar },
      { label: 'Solicitudes', path: '/solicitudes', icon: IconUserCheck, contador: 'pendientes' },
      {
        label: 'Administradores',
        path: '/administradores',
        icon: IconUserShield,
        soloAdmin: true,
      },
      { label: 'Configuración', path: '/configuracion', icon: IconSettings },
    ],
  },
  {
    titulo: 'Demo',
    links: [{ label: 'WhatsApp (sim)', path: '/whatsapp', icon: IconBrandWhatsapp }],
  },
];

// Obtiene datos del usuario logueado desde localStorage
function getUsuario() {
  try {
    const data = JSON.parse(localStorage.getItem('infrabot_user') || '{}');
    const nombre = data.nombre || 'Usuario';
    const iniciales = nombre
      .split(' ')
      .map((p) => p[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
    return { nombre, iniciales };
  } catch {
    return { nombre: 'Usuario', iniciales: 'U' };
  }
}

const NAVBAR_WIDTH_EXPANDIDO = 260;
const NAVBAR_WIDTH_COLAPSADO = 80;

export function AppLayout() {
  return (
    <ConversacionesProvider>
      <AppLayoutInner />
    </ConversacionesProvider>
  );
}

function AppLayoutInner() {
  const [mobileOpened, { toggle: toggleMobile, close: closeMobile }] = useDisclosure();
  const [colapsadoDesktop, { toggle: toggleColapsado }] = useDisclosure(false);
  const esMobile = useMediaQuery(`(max-width: ${em(767)})`);
  // En mobile el navbar ocupa todo el ancho: mostrarlo siempre con labels.
  const colapsado = colapsadoDesktop && !esMobile;
  const location = useLocation();
  const navigate = useNavigate();

  const irA = (path) => {
    navigate(path);
    closeMobile();
  };

  const [, forzarRender] = useReducer((n) => n + 1, 0);
  // useLocation re-renderiza en cada navegación, así que se relee localStorage
  // (por ejemplo, después de editar el perfil).
  const usuario = getUsuario();
  const [pendientesCount, setPendientesCount] = useState(0);
  const { esperaCount, miasNuevosCount } = useConversaciones();
  const [enEvaluacion, setEnEvaluacion] = useState(0);
  const alRecibirConteo = useCallback(
    (conteo) => setEnEvaluacion(conteo.reclamos_en_evaluacion ?? 0),
    [],
  );
  const contadores = {
    pendientes: pendientesCount,
    chats: esperaCount + miasNuevosCount,
    evaluacion: enEvaluacion,
  };

  // Conteo de solicitudes pendientes (solo admins). Se refresca al navegar para que
  // el badge se actualice después de aprobar/rechazar en la página de solicitudes.
  useEffect(() => {
    if (!esAdministrador()) return;
    listarUsuariosPendientes()
      .then((pendientes) => setPendientesCount(pendientes.length))
      .catch(() => setPendientesCount(0));
  }, [location]);

  useEffect(() => {
    const handlePageShow = (e) => {
      if (e.persisted) forzarRender();
    };
    window.addEventListener('pageshow', handlePageShow);
    return () => window.removeEventListener('pageshow', handlePageShow);
  }, []);

  const renderLink = (link) => {
    const Icon = link.icon;
    const activo = link.exact
      ? location.pathname === link.path
      : location.pathname.startsWith(link.path);
    const badgeCount = link.contador ? contadores[link.contador] : 0;
    const tienePendientes = badgeCount > 0;
    const item = (
      <NavLink
        className={classes.navLink}
        label={colapsado ? undefined : link.label}
        leftSection={<Icon size={18} stroke={1.5} />}
        rightSection={
          tienePendientes && !colapsado ? (
            <Tooltip
              label={link.ayudaContador ? `${badgeCount} ${link.ayudaContador}` : badgeCount}
              disabled={!link.ayudaContador}
              withArrow
            >
              <Badge
                size="sm"
                circle
                color="red"
                variant="filled"
                style={{ boxShadow: '0 0 0 3px rgba(255,255,255,0.15)' }}
              >
                {badgeCount}
              </Badge>
            </Tooltip>
          ) : undefined
        }
        active={activo}
        onClick={() => irA(link.path)}
        variant="filled"
        color="#1fa7b3"
        styles={{
          root: { color: '#c7cee0' },
          label: { color: 'inherit' },
        }}
      />
    );

    // Cuando el nav está colapsado, el badge numérico no entra: mostramos un
    // punto rojo sobre el ícono y el conteo en el tooltip.
    const itemConIndicador =
      tienePendientes && colapsado ? (
        <div style={{ position: 'relative' }}>
          {item}
          <div
            style={{
              position: 'absolute',
              top: 6,
              right: 10,
              width: 10,
              height: 10,
              borderRadius: '50%',
              backgroundColor: 'var(--mantine-color-red-6)',
              border: '2px solid #132a4d',
            }}
          />
        </div>
      ) : (
        item
      );

    return colapsado ? (
      <Tooltip
        key={link.path}
        label={tienePendientes ? `${link.label} (${badgeCount})` : link.label}
        position="right"
        withArrow
      >
        {itemConIndicador}
      </Tooltip>
    ) : (
      <div key={link.path}>{itemConIndicador}</div>
    );
  };

  const handleLogout = async () => {
    try {
      const { logout } = await import('../api/auth');
      await logout();
    } catch {
      // Si falla la llamada al backend, igual cerramos la sesión local
    }
    localStorage.removeItem('infrabot_user');
    window.location.href = '/';
  };

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{
        width: colapsado ? NAVBAR_WIDTH_COLAPSADO : NAVBAR_WIDTH_EXPANDIDO,
        breakpoint: 'sm',
        collapsed: { mobile: !mobileOpened },
      }}
      padding="md"
      transitionDuration={200}
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group h="100%">
            <Burger opened={mobileOpened} onClick={toggleMobile} hiddenFrom="sm" size="sm" />
            <ActionIcon variant="subtle" color="gray" onClick={toggleColapsado} visibleFrom="sm">
              {colapsado ? <IconChevronRight size={18} /> : <IconChevronLeft size={18} />}
            </ActionIcon>
            {<img src={logo} alt="InfraBot UTN" height={56} />}
          </Group>

          <Group gap="sm">
            {esAdministrador() && <SimuladorTiempoControl />}
            {esAdministrador() && <NotificationBell onConteo={alRecibirConteo} />}
            <Menu shadow="md" width={200}>
              <Menu.Target>
                <UnstyledButton>
                  <Group gap="xs" wrap="nowrap">
                    <Avatar color="#1fa7b3" radius="xl">
                      {usuario.iniciales}
                    </Avatar>
                    <div style={{ lineHeight: 1.1, maxWidth: 160 }} className="header-user-info">
                      <Text size="sm" fw={500} truncate>
                        {usuario.nombre}
                      </Text>
                    </div>
                    <IconChevronDown size={16} stroke={1.5} />
                  </Group>
                </UnstyledButton>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item leftSection={<IconUser size={16} />} onClick={() => irA('/perfil')}>
                  Mi perfil
                </Menu.Item>
                <Menu.Item
                  color="red"
                  leftSection={<IconLogout size={16} />}
                  onClick={handleLogout}
                >
                  Cerrar sesión
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar
        p="md"
        style={{ backgroundColor: '#132a4d', border: 'none', overflowY: 'auto' }}
      >
        {secciones.map((seccion) => {
          const visibles = seccion.links.filter((link) => !link.soloAdmin || esAdministrador());
          if (visibles.length === 0) return null;
          return (
            <div key={seccion.titulo ?? 'inicio'}>
              {seccion.titulo &&
                (colapsado ? (
                  <Divider my="xs" color="rgba(255, 255, 255, 0.12)" />
                ) : (
                  <Text
                    size="xs"
                    fw={700}
                    tt="uppercase"
                    c="rgba(199, 206, 224, 0.55)"
                    px="sm"
                    mt="md"
                    mb={4}
                    style={{ letterSpacing: 0.6 }}
                  >
                    {seccion.titulo}
                  </Text>
                ))}
              {visibles.map((link) => renderLink(link))}
            </div>
          );
        })}
      </AppShell.Navbar>

      <AppShell.Main>
        <Box style={{ display: 'flex', flexDirection: 'column', minHeight: 'calc(100vh - 60px)' }}>
          <Box style={{ flex: 1 }}>
            <Outlet />
          </Box>
          <Footer />
        </Box>
      </AppShell.Main>
    </AppShell>
  );
}
