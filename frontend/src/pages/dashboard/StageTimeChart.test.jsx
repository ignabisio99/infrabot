import { screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { describe, expect, it } from 'vitest';

import { render } from '../../test/render';
import { StageTimeChart } from './StageTimeChart';

const DATOS = [
  { etapa: 'REVISION', dias_promedio: 1.5, reclamos: 3 },
  { etapa: 'PRESUPUESTO', dias_promedio: 11.2, reclamos: 2 },
  { etapa: 'EJECUCION', dias_promedio: null, reclamos: 0 },
];

function Ubicacion() {
  const { pathname, search } = useLocation();
  return <div data-testid="ubicacion">{`${pathname}${search}`}</div>;
}

function renderChart(datos = DATOS) {
  const linkReclamos = (estados) => `/reclamos?estado=${estados.join(',')}`;
  return render(
    <MemoryRouter initialEntries={['/dashboard']}>
      <Routes>
        <Route
          path="/dashboard"
          element={
            <StageTimeChart datos={datos} etiquetaPeriodo="30 días" linkReclamos={linkReclamos} />
          }
        />
        <Route path="*" element={<Ubicacion />} />
      </Routes>
    </MemoryRouter>,
  );
}

function fila(etapa) {
  return screen.getByText(etapa).closest('button');
}

describe('StageTimeChart', () => {
  it('muestra los días de cada etapa y un guion en la que no tiene datos', () => {
    renderChart();

    expect(fila('Revisión')).toHaveTextContent('1,5 días');
    expect(fila('Presupuesto')).toHaveTextContent('11,2 días');
    expect(fila('Ejecución')).toHaveTextContent('—');
  });

  it('marca como más lenta la etapa con más días', () => {
    renderChart();

    expect(fila('Presupuesto')).toHaveTextContent('Más lenta');
    expect(fila('Revisión')).not.toHaveTextContent('Más lenta');
  });

  it('con una sola etapa medida no marca ninguna como más lenta', () => {
    renderChart([
      { etapa: 'REVISION', dias_promedio: 2, reclamos: 1 },
      { etapa: 'PRESUPUESTO', dias_promedio: null, reclamos: 0 },
      { etapa: 'EJECUCION', dias_promedio: null, reclamos: 0 },
    ]);

    expect(screen.queryByText('Más lenta')).not.toBeInTheDocument();
  });

  it('sin ninguna etapa medida muestra un aviso en lugar de las barras', () => {
    renderChart(DATOS.map((d) => ({ ...d, dias_promedio: null, reclamos: 0 })));

    expect(screen.getByText('Ningún reclamo terminó una etapa en el período.')).toBeInTheDocument();
    expect(screen.queryByText('Revisión')).not.toBeInTheDocument();
  });

  it('cada etapa lleva al listado con sus estados', async () => {
    const { user } = renderChart();

    await user.click(fila('Presupuesto'));

    expect(screen.getByTestId('ubicacion')).toHaveTextContent(
      '/reclamos?estado=PENDIENTE_PRESUPUESTO,EN_EVALUACION,DESIERTO',
    );
  });
});
