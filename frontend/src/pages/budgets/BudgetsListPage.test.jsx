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

async function renderListado(presupuestos) {
  listarPresupuestos.mockResolvedValue(presupuestos);
  render(
    <MemoryRouter>
      <BudgetsListPage />
    </MemoryRouter>,
  );
  await screen.findByText('REC-00000002');
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
});
