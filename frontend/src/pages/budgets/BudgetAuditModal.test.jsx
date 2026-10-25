import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { auditarPresupuesto, obtenerAuditoria } from '../../api/ai';
import { render } from '../../test/render';
import { notifyError } from '../../utils/notifications';
import { estadosFinales } from '../claims/estados';
import { BudgetAuditModal } from './BudgetAuditModal';

vi.mock('../../api/ai', () => ({ auditarPresupuesto: vi.fn(), obtenerAuditoria: vi.fn() }));
vi.mock('../../utils/notifications', () => ({ notifyError: vi.fn() }));

const INFORME = {
  recomendacion: 'REVISAR',
  total_presupuesto: '110000',
  total_estimacion: '100000',
  desvio_absoluto: '10000',
  desvio_porcentual: '0.1',
  notas_tecnicas: 'Precio algo por encima de lo habitual.',
  sin_estimacion: false,
  sin_precedentes: false,
};

function renderModal(estadoReclamo) {
  const presupuesto = { id: 7, reclamo: { id: 1, estado: estadoReclamo } };
  return render(<BudgetAuditModal presupuesto={presupuesto} onClose={vi.fn()} />);
}

describe('BudgetAuditModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('con el reclamo abierto audita solo si no había auditoría guardada', async () => {
    obtenerAuditoria.mockResolvedValue(null);
    auditarPresupuesto.mockResolvedValue(INFORME);
    renderModal('EN_EVALUACION');

    await screen.findByText(INFORME.notas_tecnicas);
    expect(auditarPresupuesto).toHaveBeenCalledWith(7);
    expect(screen.getByRole('button', { name: 'Recalcular' })).toBeEnabled();
  });

  it.each(estadosFinales)('en %s no audita al abrir y lo explica', async (estado) => {
    obtenerAuditoria.mockResolvedValue(null);
    renderModal(estado);

    expect(await screen.findByText(/ya no se puede auditar/)).toBeInTheDocument();
    expect(auditarPresupuesto).not.toHaveBeenCalled();
    expect(notifyError).not.toHaveBeenCalled();
  });

  it('en un reclamo cerrado muestra la auditoría guardada sin dejar recalcularla', async () => {
    obtenerAuditoria.mockResolvedValue(INFORME);
    renderModal('CANCELADO');

    await screen.findByText(INFORME.notas_tecnicas);
    expect(screen.getByRole('button', { name: 'Recalcular' })).toBeDisabled();
    expect(auditarPresupuesto).not.toHaveBeenCalled();
  });
});
