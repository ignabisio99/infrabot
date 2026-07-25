import {
  AppShell,
  Avatar,
  Burger,
  Group,
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
} from '@tabler/icons-react';
import logo from '../assets/logo-infrabot.jpeg';
import classes from './AppLayout.module.css';

const links = [
  { label: 'Dashboard', path: '/dashboard', icon: IconHome },
  { label: 'Reclamos', path: '/reclamos', icon: IconClipboardList },
  { label: 'Contratistas', path: '/contratistas', icon: IconTruck },
  { label: 'Presupuestos', path: '/presupuestos', icon: IconReceipt2 },
  { label: 'Calendario', path: '/calendario', icon: IconCalendar },
  { label: 'Reportes', path: '/reportes', icon: IconChartBar },
  { label: 'Configuración', path: '/configuracion', icon: IconSettings },
];

// TODO: reemplazar por el usuario autenticado real cuando exista login
const usuarioMock = {
  iniciales: 'RP',
  nombre: 'R. Pérez',
  rol: 'Responsable',
};

const NAVBAR_WIDTH_EXPANDIDO = 260;
const NAVBAR_WIDTH_COLAPSADO = 80;

export function AppLayout() {
  const [mobileOpened, { toggle: toggleMobile }] = useDisclosure();
  const [colapsado, { toggle: toggleColapsado }] = useDisclosure(false);
  const location = useLocation();
  const navigate = useNavigate();

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

          <UnstyledButton>
            <Group gap="xs">
              <Avatar color="#1fa7b3" radius="xl">
                {usuarioMock.iniciales}
              </Avatar>
              <div style={{ lineHeight: 1.1 }}>
                <Text size="sm" fw={500}>
                  {usuarioMock.nombre}
                </Text>
                <Text size="xs" c="dimmed">
                  {usuarioMock.rol}
                </Text>
              </div>
              <IconChevronDown size={16} stroke={1.5} />
            </Group>
          </UnstyledButton>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md" style={{ backgroundColor: '#132a4d', border: 'none' }}>
        {links.map((link) => {
          const Icon = link.icon;
          const item = (
            <NavLink
              className={classes.navLink}
              label={colapsado ? undefined : link.label}
              leftSection={<Icon size={18} stroke={1.5} />}
              active={location.pathname.startsWith(link.path)}
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
