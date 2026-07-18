import { Container, Text, Title } from '@mantine/core';

export function ClaimsListPage() {
  return (
    <Container size="md" py="xl">
      <Title order={2}>Reclamos</Title>
      <Text c="dimmed" mt="sm">
        El listado de reclamos todavía no está disponible.
      </Text>
    </Container>
  );
}
