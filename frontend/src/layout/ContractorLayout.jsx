import { useEffect, useState } from 'react';
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
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  IconChevronDown,
  IconChevronLeft,
  IconChevronRight,
  IconClipboardList,
  IconLogout,
  IconReceipt2,
} from '@tabler/icons-react';

import logo from '../assets/logo-infrabot.jpeg';
import classes from './AppLayout.module.css';

const links = [
  { label: 'Mis solicitudes', path: '/portal/solicitudes', icon: IconClipboardList },
  { label: 'Mis presupuestos', path: '/portal/presupuestos', icon: IconReceipt2 },
];

function getUsuario() {
  try {
    const data = JSON.parse(localStorage.getItem('infrabot_user') || '{}');
    const nombre = data.nombre || 'Contratista';
    const iniciales = nombre
      .split(' ')
      .map((p) => p[0])
      .join('')
      .toUpperCase()
      .slice(0, 2);
    return { nombre, iniciales };
  } catch {
    return { nombre: 'Contratista', iniciales: 'C' };
  }
}

const NAVBAR_WIDTH_EXPANDIDO = 260;
const NAVBAR_WIDTH_COLAPSADO = 80;

export function ContractorLayout() {
  const [mobileOpened, { toggle: toggleMobile }] = useDisclosure();
  const [colapsado, { toggle: toggleColapsado }] = useDisclosure(false);
  const location = useLocation();
  const navigate = useNavigate();
  const [usuario, setUsuario] = useState(getUsuario);

  useEffect(() => {
    setUsuario(getUsuario());
  }, [location]);

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
                <Group gap="xs">
                  <Avatar color="#1fa7b3" radius="xl">
                    {usuario.iniciales}
                  </Avatar>
                  <div style={{ lineHeight: 1.1 }}>
                    <Text size="sm" fw={500}>
                      {usuario.nombre}
                    </Text>
                    <Text size="xs" c="dimmed">
                      Contratista
                    </Text>
                  </div>
                  <IconChevronDown size={16} stroke={1.5} />
                </Group>
              </UnstyledButton>
            </Menu.Target>
            <Menu.Dropdown>
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
              onClick={() => navigate(link.path)}
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
