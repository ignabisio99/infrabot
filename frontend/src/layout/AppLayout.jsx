import { useEffect, useState } from 'react';
import {
  AppShell,
  Avatar,
  Badge,
  Burger,
  Group,
  Menu,
  NavLink,
  ActionIcon,
  Text,
  Tooltip,
  UnstyledButton,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
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
  IconUsersGroup,
  IconBrandWhatsapp,
} from '@tabler/icons-react';
import logo from '../assets/logo-infrabot.jpeg';
import { listarUsuariosPendientes } from '../api/usuarios';
import { esAdministrador } from '../utils/auth';
import classes from './AppLayout.module.css';

const links = [
  { label: 'Dashboard', path: '/dashboard', icon: IconHome },
  { label: 'Reclamos', path: '/reclamos', icon: IconClipboardList },
  { label: 'Contratistas', path: '/contratistas', icon: IconTruck, exact: true },
  { label: 'Listas de contratistas', path: '/contratistas/listas', icon: IconUsersGroup, soloAdmin: true },
  { label: 'Presupuestos', path: '/presupuestos', icon: IconReceipt2 },
  { label: 'Calendario', path: '/calendario', icon: IconCalendar },
  { label: 'Reportes', path: '/reportes', icon: IconChartBar },
  { label: 'Solicitudes', path: '/solicitudes', icon: IconUserCheck, mostrarPendientes: true },
  { label: 'Configuración', path: '/configuracion', icon: IconSettings },
  { label: 'WhatsApp (sim)', path: '/whatsapp', icon: IconBrandWhatsapp },
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
  const [mobileOpened, { toggle: toggleMobile }] = useDisclosure();
  const [colapsado, { toggle: toggleColapsado }] = useDisclosure(false);
  const location = useLocation();
  const navigate = useNavigate();
  const [usuario, setUsuario] = useState(getUsuario);
  const [pendientesCount, setPendientesCount] = useState(0);

  // Recalcular usuario al navegar o al restaurar del bfcache
  useEffect(() => {
    setUsuario(getUsuario());
  }, [location]);

  // Conteo de solicitudes pendientes (solo admins). Se refresca al navegar para que
  // el badge se actualice después de aprobar/rechazar en la página de solicitudes.
  useEffect(() => {
    if (!esAdministrador()) {
      setPendientesCount(0);
      return;
    }
    listarUsuariosPendientes()
      .then((pendientes) => setPendientesCount(pendientes.length))
      .catch(() => setPendientesCount(0));
  }, [location]);

  useEffect(() => {
    const handlePageShow = (e) => {
      if (e.persisted) setUsuario(getUsuario());
    };
    window.addEventListener('pageshow', handlePageShow);
    return () => window.removeEventListener('pageshow', handlePageShow);
  }, []);

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

          <Menu shadow="md" width={200}>
            <Menu.Target>
              <UnstyledButton>
                <Group gap="xs">
                  <Avatar color="#1fa7b3" radius="xl">
                    {usuario.iniciales}
                  </Avatar>
                  <div style={{ lineHeight: 1.1 }}>
                    <Text size="sm" fw={500}>
                      {usuario.nombre}
                    </Text>
                  </div>
                  <IconChevronDown size={16} stroke={1.5} />
                </Group>
              </UnstyledButton>
            </Menu.Target>
            <Menu.Dropdown>
              <Menu.Item leftSection={<IconUser size={16} />} onClick={() => navigate('/perfil')}>
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
      </AppShell.Header>

      <AppShell.Navbar p="md" style={{ backgroundColor: '#132a4d', border: 'none' }}>
        {links
          .filter((link) => !link.soloAdmin || esAdministrador())
          .map((link) => {
          const Icon = link.icon;
          const activo = link.exact
            ? location.pathname === link.path
            : location.pathname.startsWith(link.path);
          const tienePendientes = link.mostrarPendientes && pendientesCount > 0;
          const item = (
            <NavLink
              className={classes.navLink}
              label={colapsado ? undefined : link.label}
              leftSection={<Icon size={18} stroke={1.5} />}
              rightSection={
                tienePendientes && !colapsado ? (
                  <Badge
                    size="sm"
                    circle
                    color="red"
                    variant="filled"
                    style={{ boxShadow: '0 0 0 3px rgba(255,255,255,0.15)' }}
                  >
                    {pendientesCount}
                  </Badge>
                ) : undefined
              }
              active={activo}
              onClick={() => navigate(link.path)}
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
              label={tienePendientes ? `${link.label} (${pendientesCount})` : link.label}
              position="right"
              withArrow
            >
              {itemConIndicador}
            </Tooltip>
          ) : (
            <div key={link.path}>{itemConIndicador}</div>
          );
        })}
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
