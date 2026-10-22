import { Card, Grid, SimpleGrid, Skeleton, Stack } from '@mantine/core';

const TARJETAS = 8;

function TarjetaSkeleton() {
  return (
    <Card withBorder radius="md" padding="lg">
      <Skeleton h={10} w="55%" radius="sm" />
      <Skeleton h={30} w="40%" mt="sm" radius="sm" />
      <Skeleton h={10} w="75%" mt="md" radius="sm" />
    </Card>
  );
}

function GraficoSkeleton({ filas }) {
  return (
    <Card withBorder radius="md" padding="lg" h="100%">
      <Skeleton h={16} w="45%" radius="sm" />
      <Skeleton h={10} w="70%" mt="xs" mb="lg" radius="sm" />
      {filas ? (
        <Stack gap="sm">
          {Array.from({ length: filas }, (_, i) => (
            <Skeleton key={i} h={14} radius="sm" />
          ))}
        </Stack>
      ) : (
        <Skeleton h={260} radius="sm" />
      )}
    </Card>
  );
}

/**
 * Lo que se ve mientras llega el primer resumen. Repite la grilla de la página para que
 * al cargar los bloques aparezcan donde ya estaban y la pantalla no salte.
 */
export function DashboardSkeleton() {
  return (
    <Stack gap="lg" data-testid="dashboard-skeleton">
      <SimpleGrid cols={{ base: 1, xs: 2, lg: 4 }}>
        {Array.from({ length: TARJETAS }, (_, i) => (
          <TarjetaSkeleton key={i} />
        ))}
      </SimpleGrid>
      <Grid>
        <Grid.Col span={{ base: 12, lg: 5 }}>
          <GraficoSkeleton filas={12} />
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 7 }}>
          <GraficoSkeleton />
        </Grid.Col>
      </Grid>
      <GraficoSkeleton filas={4} />
    </Stack>
  );
}
