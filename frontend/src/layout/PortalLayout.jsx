import {
  AppShell,
  Avatar,
  Burger,
  Group,
  Menu,
  NavLink,
  ActionIcon,
  Text,
  Tooltip,
  UnstyledButton,
  em,
} from '@mantine/core';
import { useDisclosure, useMediaQuery } from '@mantine/hooks';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  IconChevronDown,
  IconChevronLeft,
  IconChevronRight,
  IconLogout,
  IconUser,
} from '@tabler/icons-react';

import logo from '../assets/logo-infrabot.jpeg';
import classes from './AppLayout.module.css';

function getUsuario(etiquetaRol) {
  try {
    const data = JSON.parse(localStorage.getItem('infrabot_user') || '{}');
    const nombre = data.nombre || etiquetaRol;
    const iniciales = nombre
      .split(' ')
      .map((p) => p[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
    return { nombre, iniciales };
  } catch {
    return { nombre: etiquetaRol, iniciales: etiquetaRol[0] };
  }
}

const NAVBAR_WIDTH_EXPANDIDO = 260;
const NAVBAR_WIDTH_COLAPSADO = 80;

/** Layout acotado para los usuarios que no son admin: un menú corto y el perfil. */
export function PortalLayout({ links, etiquetaRol }) {
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
  // useLocation re-renderiza en cada navegación, así que se relee localStorage
  // (por ejemplo, después de editar el perfil).
  const usuario = getUsuario(etiquetaRol);

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
            <img src={logo} alt="InfraBot UTN" height={56} />
          </Group>

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
                    <Text size="xs" c="dimmed">
                      {etiquetaRol}
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
              <Menu.Item color="red" leftSection={<IconLogout size={16} />} onClick={handleLogout}>
                Cerrar sesión
              </Menu.Item>
            </Menu.Dropdown>
          </Menu>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md" style={{ backgroundColor: '#132a4d', border: 'none' }}>
        {links.map((link) => {
          const Icon = link.icon;
          const activo = location.pathname.startsWith(link.path);
          const item = (
            <NavLink
              className={classes.navLink}
              label={colapsado ? undefined : link.label}
              leftSection={<Icon size={18} stroke={1.5} />}
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

          return colapsado ? (
            <Tooltip key={link.path} label={link.label} position="right" withArrow>
              {item}
            </Tooltip>
          ) : (
            <div key={link.path}>{item}</div>
          );
        })}
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
