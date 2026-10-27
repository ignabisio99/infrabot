import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { obtenerAuditoria } from '../../api/ai';
import { render } from '../../test/render';
import { estadosFinales } from '../claims/estados';
import { BudgetItemsModal } from './BudgetItemsModal';

vi.mock('../../api/ai', () => ({ auditarPresupuesto: vi.fn(), obtenerAuditoria: vi.fn() }));
vi.mock('../../api/presupuestos');
vi.mock('../../layout/NotificationBell', () => ({ avisarNotificacionesCambiaron: vi.fn() }));
vi.mock('../../utils/notifications', () => ({ notifyError: vi.fn(), notifySuccess: vi.fn() }));
vi.mock('../../utils/auth', () => ({ esAdministrador: () => true }));

const INFORME = {
  recomendacion: 'REVISAR',
  total_presupuesto: '110000',
  total_estimacion: '100000',
  desvio_porcentual: '0.1',
  notas_tecnicas: 'Precio algo por encima de lo habitual.',
  sin_estimacion: false,
  sin_precedentes: false,
};

function crearPresupuesto(estadoReclamo) {
  return {
    id: 7,
    estado: 'RECIBIDO',
    estados_posibles: [],
    monto: '110000',
    version: 1,
    items: [],
    motivo_estado: null,
    detalle_tarea: null,
    observaciones: null,
    contratista: { id: 3, nombre_empresa: 'Plomería Integral SA' },
    reclamo: { id: 1, nombre_escuela: 'Escuela Primaria N°10', estado: estadoReclamo },
  };
}

function renderModal(estadoReclamo) {
  return render(
    <BudgetItemsModal presupuesto={crearPresupuesto(estadoReclamo)} onClose={vi.fn()} />,
  );
}

describe('BudgetItemsModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('con el reclamo abierto deja recalcular la auditoría', async () => {
    obtenerAuditoria.mockResolvedValue(INFORME);
    renderModal('EN_EVALUACION');

    await screen.findByText(INFORME.notas_tecnicas);
    expect(screen.getByRole('button', { name: 'Recalcular auditoría' })).toBeEnabled();
  });

  it.each(estadosFinales)(
    'en %s muestra la auditoría guardada pero no deja recalcularla',
    async (estado) => {
      obtenerAuditoria.mockResolvedValue(INFORME);
      renderModal(estado);

      await screen.findByText(INFORME.notas_tecnicas);
      expect(screen.getByRole('button', { name: 'Recalcular auditoría' })).toBeDisabled();
    },
  );

  it('sin auditoría guardada explica que un reclamo cerrado ya no se audita', async () => {
    obtenerAuditoria.mockResolvedValue(null);
    renderModal('FINALIZADO');

    expect(await screen.findByText(/ya no se puede auditar/)).toBeInTheDocument();
    expect(screen.queryByText(/Podés recalcular ahora/)).not.toBeInTheDocument();
  });
});
