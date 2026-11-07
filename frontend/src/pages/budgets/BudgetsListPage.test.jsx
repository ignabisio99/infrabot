import { screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listarPresupuestos } from '../../api/presupuestos';
import { render } from '../../test/render';
import { BudgetsListPage } from './BudgetsListPage';

vi.mock('../../api/presupuestos');
vi.mock('./BudgetAuditModal', () => ({ BudgetAuditModal: () => null }));
vi.mock('./BudgetItemsModal', () => ({ BudgetItemsModal: () => null }));
vi.mock('./DecideBudgetModal', () => ({ DecideBudgetModal: () => null }));

const ESCUELA_2 = 'ESCUELA DE EDUCACIÓN PRIMARIA Nº5 INGENIERO JORGE NEWBERY';

function presupuesto(id, reclamoId, empresa, estado, monto, datos = {}) {
  return {
    id,
    estado,
    monto,
    version: 1,
    fecha: '2026-11-03T10:00:00Z',
    observaciones: null,
    estados_posibles: ['RECIBIDO', 'AJUSTES_SOLICITADOS'].includes(estado) ? ['APROBADO'] : [],
    reclamo: {
      id: reclamoId,
      nombre_escuela: reclamoId === 2 ? ESCUELA_2 : 'Escuela Uno',
      estado: 'EN_EVALUACION',
    },
    contratista: { id, nombre_empresa: empresa, fecha_baja: null },
    ...datos,
  };
}

async function renderListado(presupuestos, primerReclamo = 'REC-00000002') {
  listarPresupuestos.mockResolvedValue(presupuestos);
  const resultado = render(
    <MemoryRouter>
      <BudgetsListPage />
    </MemoryRouter>,
  );
  await screen.findByText(primerReclamo);
  return resultado;
}

const fila = (empresa) => screen.getByText(empresa).closest('tr');

describe('BudgetsListPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('agrupa las ofertas por reclamo y marca la más barata de las que siguen en carrera', async () => {
    await renderListado([
      presupuesto(1, 2, 'Cara SA', 'RECIBIDO', '3600'),
      presupuesto(2, 1, 'Única SA', 'RECIBIDO', '1000'),
      presupuesto(3, 2, 'Barata SA', 'RECIBIDO', '3000'),
      presupuesto(4, 2, 'Descartada SA', 'RECHAZADO', '100'),
    ]);

    expect(screen.getAllByText('REC-00000002')).toHaveLength(1);
    expect(screen.getByText('EP Nº5 Ingeniero Jorge Newbery')).toBeInTheDocument();
    expect(screen.getByText('3 ofertas')).toBeInTheDocument();
    expect(within(fila('Barata SA')).getByText('Más barata')).toBeInTheDocument();
    expect(within(fila('Cara SA')).getByText('+20% que la más barata')).toBeInTheDocument();
    // Con una sola oferta no hay con qué comparar.
    expect(within(fila('Única SA')).queryByText('Más barata')).not.toBeInTheDocument();

    const empresas = screen.getAllByText(/^(Cara|Barata|Descartada) SA$/).map((e) => e.textContent);
    expect(empresas).toEqual(['Barata SA', 'Cara SA', 'Descartada SA']);
  });

  it('sólo ofrece decidir y auditar donde corresponde', async () => {
    await renderListado([
      presupuesto(1, 2, 'Abierta SA', 'RECIBIDO', '3600'),
      presupuesto(2, 2, 'Aprobada SA', 'APROBADO', '3000', { estados_posibles: [] }),
      presupuesto(3, 2, 'Descartada SA', 'RECHAZADO', '100'),
    ]);

    expect(within(fila('Abierta SA')).getByRole('button', { name: 'Decidir' })).toBeInTheDocument();
    expect(
      within(fila('Abierta SA')).getByRole('button', { name: 'Auditoría' }),
    ).toBeInTheDocument();
    expect(
      within(fila('Aprobada SA')).queryByRole('button', { name: 'Decidir' }),
    ).not.toBeInTheDocument();
    expect(
      within(fila('Aprobada SA')).queryByRole('button', { name: 'Auditoría' }),
    ).not.toBeInTheDocument();
    expect(
      within(fila('Descartada SA')).queryByRole('button', { name: 'Decidir' }),
    ).not.toBeInTheDocument();
  });

  it('con un filtro que esconde ofertas, el encabezado dice cuántas se ven de cuántas hay', async () => {
    const { user } = await renderListado([
      presupuesto(1, 2, 'Abierta SA', 'RECIBIDO', '3600'),
      presupuesto(2, 2, 'Otra Abierta SA', 'RECIBIDO', '3000'),
      presupuesto(3, 2, 'Descartada SA', 'RECHAZADO', '100'),
      presupuesto(4, 1, 'Única SA', 'RECIBIDO', '1000'),
    ]);

    expect(screen.getByText('3 ofertas')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Estado' }));
    await user.click(screen.getByRole('checkbox', { name: 'Recibido' }));

    expect(screen.getByText('2 de 3 ofertas')).toBeInTheDocument();
    expect(screen.queryByText('Descartada SA')).not.toBeInTheDocument();
    // El filtro no le escondió nada a este: sigue sin el "de".
    expect(screen.getByText('1 oferta')).toBeInTheDocument();
  });

  describe('paginación', () => {
    // 11 reclamos con una oferta cada uno, salvo el 10, que tiene tres y queda justo en el
    // corte: paginando por oferta, la 10.ª fila sería su primera oferta y las otras dos
    // pasarían a la página siguiente.
    const onceReclamos = () => [
      ...Array.from({ length: 9 }, (_, i) =>
        presupuesto(i + 1, i + 1, `Empresa ${i + 1}`, 'RECIBIDO', '500'),
      ),
      presupuesto(100, 10, 'Primera SA', 'RECIBIDO', '1000'),
      presupuesto(101, 10, 'Segunda SA', 'RECIBIDO', '1100'),
      presupuesto(102, 10, 'Tercera SA', 'RECIBIDO', '1200'),
      presupuesto(11, 11, 'Empresa 11', 'RECIBIDO', '500'),
    ];

    it('pagina por reclamo y no parte las ofertas de un reclamo entre páginas', async () => {
      const { user } = await renderListado(onceReclamos(), 'REC-00000001');

      expect(screen.getByText('REC-00000010')).toBeInTheDocument();
      expect(screen.getByText('3 ofertas')).toBeInTheDocument();
      for (const empresa of ['Primera SA', 'Segunda SA', 'Tercera SA']) {
        expect(screen.getByText(empresa)).toBeInTheDocument();
      }
      expect(screen.queryByText('REC-00000011')).not.toBeInTheDocument();

      await user.click(screen.getByRole('button', { name: '2' }));

      expect(screen.getByText('REC-00000011')).toBeInTheDocument();
      expect(screen.queryByText('REC-00000010')).not.toBeInTheDocument();
      expect(screen.queryByText('Tercera SA')).not.toBeInTheDocument();
    });

    it('sin una segunda página no muestra el paginador', async () => {
      await renderListado(onceReclamos().slice(0, 12), 'REC-00000001');

      expect(screen.queryByRole('button', { name: '2' })).not.toBeInTheDocument();
    });

    it('vuelve a la primera página al cambiar un filtro', async () => {
      const { user } = await renderListado(onceReclamos(), 'REC-00000001');

      await user.click(screen.getByRole('button', { name: '2' }));
      // Todos los IDs tienen un 0, así que siguen siendo dos páginas.
      await user.type(screen.getByLabelText('Reclamo'), '0');

      expect(screen.getByText('REC-00000001')).toBeInTheDocument();
      expect(screen.queryByText('REC-00000011')).not.toBeInTheDocument();
    });
  });
});
