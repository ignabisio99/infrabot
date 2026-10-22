import { LineChart } from '@mantine/charts';
import { Card, Text, Title } from '@mantine/core';

import { mesCorto } from '../../utils/meses';

/**
 * Reclamos ingresados contra reclamos finalizados, por mes.
 *
 * Las dos series comparten eje porque las dos son cantidades de reclamos: la distancia
 * entre las líneas es justamente lo que se quiere leer (si el backlog crece o se drena).
 */
export function MonthlyFlowChart({ datos }) {
  const data = datos.map((punto) => ({
    mes: mesCorto(punto.mes),
    Ingresados: punto.ingresados,
    Finalizados: punto.finalizados,
  }));

  return (
    <Card withBorder radius="md" padding="lg" h="100%">
      <Title order={4}>Ingresados vs. finalizados</Title>
      <Text size="xs" c="dimmed" mb="md">
        Últimos {datos.length} meses.
      </Text>

      <LineChart
        h={260}
        data={data}
        dataKey="mes"
        series={[
          { name: 'Ingresados', color: 'blue.6' },
          { name: 'Finalizados', color: 'green.7' },
        ]}
        curveType="linear"
        strokeWidth={2}
        dotProps={{ r: 4, strokeWidth: 2 }}
        activeDotProps={{ r: 6 }}
        gridAxis="y"
        tickLine="none"
        withLegend
        legendProps={{ verticalAlign: 'bottom', height: 32 }}
        yAxisProps={{ allowDecimals: false, width: 30 }}
      />
    </Card>
  );
}
