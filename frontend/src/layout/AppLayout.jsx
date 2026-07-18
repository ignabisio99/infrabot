import { AppShell, Burger, Group, NavLink, Title } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';

const links = [
  { label: 'Nuevo Reclamo', path: '/reclamos/nuevo' },
  { label: 'Reclamos', path: '/reclamos' },
];

export function AppLayout() {
  const [opened, { toggle }] = useDisclosure();
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 260, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md">
          <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
          <Title order={3}>InfraBot UTN</Title>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        {links.map((link) => (
          <NavLink
            key={link.path}
            label={link.label}
            active={location.pathname === link.path}
            onClick={() => navigate(link.path)}
          />
        ))}
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  );
}
