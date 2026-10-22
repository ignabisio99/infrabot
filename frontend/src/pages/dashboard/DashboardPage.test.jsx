import { screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { obtenerResumenDashboard } from '../../api/dashboard';
import { render } from '../../test/render';
import { DashboardPage } from './DashboardPage';

vi.mock('../../api/dashboard', () => ({ obtenerResumenDashboard: vi.fn() }));
vi.mock('../../hooks/useEsMobile', () => ({ useEsMobile: vi.fn(() => false) }));
// jsdom no hace layout: Recharts mide el contenedor en 0x0, no dibuja y llena stderr de warnings.
vi.mock('@mantine/charts', () => ({ LineChart: () => null, Sparkline: () => null }));

function resumen({
  abiertos = 5,
  ingresados = { actual: 12, anterior: 10 },
  periodoDias = 30,
} = {}) {
  return {
    periodo_dias: periodoDias,
    kpis: {
      reclamos_abiertos: abiertos,
      pendientes_revision: 2,
      en_evaluacion: 1,
      visitas_proximos_7_dias: 3,
      ingresados,
      finalizados: { actual: 4, anterior: 8 },
      monto_aprobado: { actual: '150000.00', anterior: '0' },
      dias_promedio_resolucion: { actual: null, anterior: 6.5 },
    },
    por_estado: [{ estado: 'PENDIENTE_REVISION', cantidad: 2 }],
    serie_mensual: [
      { mes: '2026-09', ingresados: 3, finalizados: 1, monto_aprobado: '0' },
      { mes: '2026-10', ingresados: 9, finalizados: 3, monto_aprobado: '150000.00' },
    ],
    estados_abiertos: ['PENDIENTE_REVISION', 'EN_EVALUACION'],
    estancados: [],
    estancados_total: 0,
    dias_sin_movimiento_umbral: 7,
    categorias: ['Gas', 'Techos'],
  };
}

function Ubicacion() {
  const { pathname, search } = useLocation();
  return <div data-testid="ubicacion">{`${pathname}${search}`}</div>;
}

function renderDashboard(url = '/dashboard') {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <Routes>
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="*" element={<Ubicacion />} />
      </Routes>
    </MemoryRouter>,
  );
}

function tarjeta(titulo) {
  return screen.getByText(titulo).closest('.mantine-Card-root');
}

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('muestra el skeleton hasta que llega el resumen', async () => {
    let resolver;
    obtenerResumenDashboard.mockReturnValue(new Promise((r) => (resolver = r)));
    renderDashboard();

    expect(screen.getByTestId('dashboard-skeleton')).toBeInTheDocument();

    resolver(resumen());

    expect(await screen.findByText('Reclamos abiertos')).toBeInTheDocument();
    expect(screen.queryByTestId('dashboard-skeleton')).not.toBeInTheDocument();
  });

  it('muestra la variación contra el período anterior con el color según convenga', async () => {
    obtenerResumenDashboard.mockResolvedValue(resumen());
    renderDashboard();

    await screen.findByText('Reclamos abiertos');

    expect(within(tarjeta('Ingresados')).getByText('↑ 20%')).toBeInTheDocument();
    expect(within(tarjeta('Finalizados')).getByText('↓ 50%')).toBeInTheDocument();
    expect(within(tarjeta('Monto aprobado')).getByText('↑ desde 0')).toBeInTheDocument();
    expect(
      within(tarjeta('Resolución promedio')).getByText('Sin datos para comparar'),
    ).toBeInTheDocument();
    expect(within(tarjeta('Finalizados')).getByText('vs. 30 días anteriores')).toBeInTheDocument();
  });

  it('pide el resumen con los filtros de la URL', async () => {
    obtenerResumenDashboard.mockResolvedValue(resumen({ periodoDias: 365 }));
    renderDashboard('/dashboard?periodo=365&prioridad=ALTA&categoria=Gas');

    await screen.findByText('Reclamos abiertos');

    expect(obtenerResumenDashboard).toHaveBeenCalledWith({
      periodo: '365',
      prioridad: 'ALTA',
      categoria: 'Gas',
    });
    expect(within(tarjeta('Ingresados')).getByText('vs. 12 meses anteriores')).toBeInTheDocument();
  });

  it('un período inválido en la URL cae en el de 30 días', async () => {
    obtenerResumenDashboard.mockResolvedValue(resumen());
    renderDashboard('/dashboard?periodo=7');

    await screen.findByText('Reclamos abiertos');

    expect(obtenerResumenDashboard).toHaveBeenCalledWith({
      periodo: '30',
      prioridad: '',
      categoria: '',
    });
  });

  it('al cambiar el período vuelve a pedir y mantiene los datos mientras tanto', async () => {
    obtenerResumenDashboard.mockResolvedValueOnce(resumen({ abiertos: 5 }));
    let resolver;
    obtenerResumenDashboard.mockReturnValueOnce(new Promise((r) => (resolver = r)));
    const { user } = renderDashboard();

    await screen.findByText('Reclamos abiertos');
    await user.click(screen.getByText('90 días'));

    expect(obtenerResumenDashboard).toHaveBeenLastCalledWith({
      periodo: '90',
      prioridad: '',
      categoria: '',
    });
    expect(screen.getByLabelText('Actualizando')).toBeInTheDocument();
    expect(within(tarjeta('Reclamos abiertos')).getByText('5')).toBeInTheDocument();
    // Los textos siguen describiendo los números que se ven, no el período recién elegido.
    expect(within(tarjeta('Finalizados')).getByText('vs. 30 días anteriores')).toBeInTheDocument();

    resolver(resumen({ abiertos: 9, periodoDias: 90 }));

    await waitFor(() =>
      expect(within(tarjeta('Reclamos abiertos')).getByText('9')).toBeInTheDocument(),
    );
    expect(within(tarjeta('Finalizados')).getByText('vs. 90 días anteriores')).toBeInTheDocument();
    expect(screen.queryByLabelText('Actualizando')).not.toBeInTheDocument();
  });

  it('la tarjeta de abiertos lleva al listado con los estados y la prioridad elegida', async () => {
    obtenerResumenDashboard.mockResolvedValue(resumen());
    const { user } = renderDashboard('/dashboard?prioridad=ALTA');

    await screen.findByText('Reclamos abiertos');
    await user.click(tarjeta('Reclamos abiertos'));

    expect(screen.getByTestId('ubicacion')).toHaveTextContent(
      '/reclamos?estado=PENDIENTE_REVISION%2CEN_EVALUACION&prioridad=ALTA',
    );
  });

  it('una prioridad inválida en la URL se ignora', async () => {
    obtenerResumenDashboard.mockResolvedValue(resumen());
    renderDashboard('/dashboard?prioridad=URGENTE');

    await screen.findByText('Reclamos abiertos');

    expect(obtenerResumenDashboard).toHaveBeenCalledWith({
      periodo: '30',
      prioridad: '',
      categoria: '',
    });
  });

  it('las barras por estado llevan al listado con prioridad y categoría', async () => {
    obtenerResumenDashboard.mockResolvedValue(resumen());
    const { user } = renderDashboard('/dashboard?prioridad=ALTA&categoria=Gas');

    await screen.findByText('Reclamos abiertos');
    await user.click(
      screen.getByText('Reclamos por estado').closest('.mantine-Card-root').querySelector('button'),
    );

    expect(screen.getByTestId('ubicacion')).toHaveTextContent(
      '/reclamos?estado=PENDIENTE_REVISION&prioridad=ALTA&categoria=Gas',
    );
  });

  it('si falla un cambio de filtro, los datos anteriores quedan atenuados', async () => {
    obtenerResumenDashboard.mockResolvedValueOnce(resumen());
    obtenerResumenDashboard.mockRejectedValueOnce(new Error('Sin conexión.'));
    const { user } = renderDashboard();

    await screen.findByText('Reclamos abiertos');
    await user.click(screen.getByText('90 días'));

    expect(await screen.findByText('Sin conexión.')).toBeInTheDocument();
    expect(screen.queryByLabelText('Actualizando')).not.toBeInTheDocument();
    expect(tarjeta('Reclamos abiertos').parentElement.parentElement).toHaveStyle({
      opacity: '0.55',
    });
  });

  it('si falla la carga muestra el error en lugar del skeleton', async () => {
    obtenerResumenDashboard.mockRejectedValue(new Error('No se pudo obtener el resumen.'));
    renderDashboard();

    expect(await screen.findByText('No se pudo obtener el resumen.')).toBeInTheDocument();
    expect(screen.queryByTestId('dashboard-skeleton')).not.toBeInTheDocument();
  });
});
