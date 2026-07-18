import { AppShell, Burger, Group, NavLink, Title, ActionIcon, Tooltip } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  IconClipboardList,
  IconTruck,
  IconChevronLeft,
  IconChevronRight,
} from '@tabler/icons-react';

const links = [
  { label: 'Reclamos', path: '/reclamos', icon: IconClipboardList },
  { label: 'Contratistas', path: '/contratistas', icon: IconTruck },
];

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
        <Group h="100%" px="md">
          <Burger opened={mobileOpened} onClick={toggleMobile} hiddenFrom="sm" size="sm" />
          <ActionIcon variant="subtle" color="gray" onClick={toggleColapsado} visibleFrom="sm">
            {colapsado ? <IconChevronRight size={18} /> : <IconChevronLeft size={18} />}
          </ActionIcon>
          {!colapsado && <Title order={3}>InfraBot UTN</Title>}
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        {links.map((link) => {
          const Icon = link.icon;
          const item = (
            <NavLink
              label={colapsado ? undefined : link.label}
              leftSection={<Icon size={18} stroke={1.5} />}
              active={location.pathname.startsWith(link.path)}
              onClick={() => navigate(link.path)}
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
