import { Anchor, Box, Container, Divider, Group, Stack, Text } from '@mantine/core';

export function Footer() {
  return (
    <Box component="footer" py="md">
      <Container size="xl" px={{ base: 'md', sm: 'xl' }}>
        <Divider mb="md" />
        <Group justify="space-between" align="center" gap="xs" wrap="wrap">
          <Stack gap={2}>
            <Text size="sm" fw={600} c="dark">
              InfraBot UTN
            </Text>
            <Text size="xs" c="dimmed">
              Gestión inteligente de reclamos y presupuestos
            </Text>
          </Stack>
          <Stack gap={2}>
            <Text size="xs" c="dimmed">
              Desarrollado por Grupo 205 - Proyecto Final 2026
            </Text>
            <Anchor href="https://frba.utn.edu.ar/" target="_blank" rel="noreferrer" size="xs">
              UTN FRBA
            </Anchor>
          </Stack>
        </Group>
      </Container>
    </Box>
  );
}
