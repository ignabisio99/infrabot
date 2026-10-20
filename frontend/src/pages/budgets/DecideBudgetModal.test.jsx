import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { decidirPresupuesto } from '../../api/presupuestos';
import { avisarNotificacionesCambiaron } from '../../layout/NotificationBell';
import { render } from '../../test/render';
import { notifyError, notifySuccess } from '../../utils/notifications';
import { DecideBudgetModal } from './DecideBudgetModal';

vi.mock('../../api/presupuestos', () => ({ decidirPresupuesto: vi.fn() }));
vi.mock('../../layout/NotificationBell', () => ({ avisarNotificacionesCambiaron: vi.fn() }));
vi.mock('../../utils/notifications', () => ({ notifyError: vi.fn(), notifySuccess: vi.fn() }));

function crearPresupuesto(datos = {}) {
  return {
    id: 7,
    estado: 'RECIBIDO',
    estados_posibles: ['AJUSTES_SOLICITADOS', 'APROBADO', 'RECHAZADO'],
    monto: '103000.00',
    version: 1,
    contratista: { nombre_empresa: 'Plomería Integral SA' },
    reclamo: { id: 1, nombre_escuela: 'Escuela Primaria N°10' },
    ...datos,
  };
}

function renderModal(presupuesto) {
  const onClose = vi.fn();
  const onDecidido = vi.fn();
  const resultado = render(
    <DecideBudgetModal presupuesto={presupuesto} onClose={onClose} onDecidido={onDecidido} />,
  );
  return { ...resultado, onClose, onDecidido };
}

async function elegirDecision(user, etiqueta) {
  await user.click(screen.getByRole('combobox', { name: 'Decisión' }));
  await user.click(screen.getByRole('option', { name: etiqueta }));
}

describe('DecideBudgetModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('muestra sobre qué oferta se decide', () => {
    renderModal(crearPresupuesto({ version: 2 }));

    expect(screen.getByText(/Plomería Integral SA/)).toHaveTextContent('versión 2');
    expect(screen.getByText(/Escuela Primaria N°10/)).toBeInTheDocument();
  });

  it('ofrece las decisiones como acciones, no como estados', async () => {
    const { user } = renderModal(crearPresupuesto());

    await user.click(screen.getByRole('combobox', { name: 'Decisión' }));

    const opciones = screen.getAllByRole('option').map((opcion) => opcion.textContent);
    expect(opciones).toEqual(['Solicitar ajustes', 'Aprobar', 'Rechazar']);
  });

  it.each([
    ['Aprobar', /el resto de las ofertas van a quedar como no seleccionadas/],
    ['Rechazar', /Esta oferta queda descartada/],
    ['Solicitar ajustes', /Se le avisa al contratista por WhatsApp y mail/],
  ])('al elegir "%s" muestra su aviso', async (decision, aviso) => {
    const { user } = renderModal(crearPresupuesto());

    await elegirDecision(user, decision);

    expect(screen.getByText(aviso)).toBeInTheDocument();
  });

  it('aprueba sin pedir motivo y avisa a la campanita', async () => {
    const actualizado = crearPresupuesto({ estado: 'APROBADO', estados_posibles: [] });
    decidirPresupuesto.mockResolvedValue(actualizado);
    const { user, onClose, onDecidido } = renderModal(crearPresupuesto());

    await elegirDecision(user, 'Aprobar');
    await user.click(screen.getByRole('button', { name: 'Guardar decisión' }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(decidirPresupuesto).toHaveBeenCalledWith(7, 'APROBADO', '');
    expect(notifySuccess).toHaveBeenCalledWith('El presupuesto quedó "Aprobado".');
    expect(avisarNotificacionesCambiaron).toHaveBeenCalled();
    expect(onDecidido).toHaveBeenCalledWith(actualizado);
  });

  it.each([
    ['Rechazar', /Motivo del rechazo/, 'RECHAZADO'],
    ['Solicitar ajustes', /Qué tiene que corregir/, 'AJUSTES_SOLICITADOS'],
  ])('"%s" exige un motivo antes de guardar', async (decision, campo, estado) => {
    decidirPresupuesto.mockResolvedValue(crearPresupuesto({ estado }));
    const { user } = renderModal(crearPresupuesto());

    await elegirDecision(user, decision);
    const guardar = screen.getByRole('button', { name: 'Guardar decisión' });
    expect(guardar).toBeDisabled();

    await user.type(screen.getByRole('textbox', { name: campo }), 'Falta el disyuntor');
    await user.click(guardar);

    expect(decidirPresupuesto).toHaveBeenCalledWith(7, estado, 'Falta el disyuntor');
  });

  it('muestra el error del backend y no da la decisión por hecha', async () => {
    decidirPresupuesto.mockRejectedValue(new Error('No hay una evaluación abierta'));
    const { user, onClose, onDecidido } = renderModal(crearPresupuesto());

    await elegirDecision(user, 'Aprobar');
    await user.click(screen.getByRole('button', { name: 'Guardar decisión' }));

    await waitFor(() => expect(notifyError).toHaveBeenCalledWith('No hay una evaluación abierta'));
    expect(avisarNotificacionesCambiaron).not.toHaveBeenCalled();
    expect(onDecidido).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('explica que un presupuesto ya decidido no puede cambiar', () => {
    renderModal(crearPresupuesto({ estado: 'APROBADO', estados_posibles: [] }));

    expect(screen.getByText(/Ya se decidió sobre este presupuesto/)).toBeInTheDocument();
  });
});
