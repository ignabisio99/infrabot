import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { cambiarEstadoReclamo } from '../../api/reclamos';
import { render } from '../../test/render';
import { notifyError, notifySuccess } from '../../utils/notifications';
import { ChangeStatusModal } from './ChangeStatusModal';

vi.mock('../../api/reclamos', () => ({ cambiarEstadoReclamo: vi.fn() }));
vi.mock('../../utils/notifications', () => ({ notifyError: vi.fn(), notifySuccess: vi.fn() }));

function crearReclamo(datos = {}) {
  return {
    id: 1,
    estado: 'EN_EVALUACION',
    estados_posibles: ['APROBADO', 'CANCELADO'],
    ofertas_en_carrera: 0,
    ...datos,
  };
}

function renderModal(reclamo, props = {}) {
  const onClose = vi.fn();
  const onEstadoCambiado = vi.fn();
  const resultado = render(
    <ChangeStatusModal
      reclamo={reclamo}
      onClose={onClose}
      onEstadoCambiado={onEstadoCambiado}
      {...props}
    />,
  );
  return { ...resultado, onClose, onEstadoCambiado };
}

async function elegirEstado(user, etiqueta) {
  await user.click(screen.getByRole('combobox', { name: 'Nuevo estado' }));
  await user.click(screen.getByRole('option', { name: etiqueta }));
}

describe('ChangeStatusModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('ofrece sólo los estados que habilita el backend', async () => {
    const { user } = renderModal(crearReclamo());

    await user.click(screen.getByRole('combobox', { name: 'Nuevo estado' }));

    const opciones = screen.getAllByRole('option').map((opcion) => opcion.textContent);
    expect(opciones).toEqual(['Aprobado', 'Cancelado']);
  });

  it('avisa en plural cuántas ofertas en carrera se notifican al cancelar', async () => {
    const { user } = renderModal(crearReclamo({ ofertas_en_carrera: 2 }));

    await elegirEstado(user, 'Cancelado');

    expect(screen.getByText(/Hay 2 ofertas en carrera/)).toBeInTheDocument();
  });

  it('avisa en singular cuando hay una sola oferta en carrera', async () => {
    const { user } = renderModal(crearReclamo({ ofertas_en_carrera: 1 }));

    await elegirEstado(user, 'Cancelado');

    expect(screen.getByText(/Hay 1 oferta en carrera/)).toBeInTheDocument();
  });

  it('no muestra aviso al cancelar un reclamo sin ofertas en carrera', async () => {
    const { user } = renderModal(crearReclamo({ ofertas_en_carrera: 0 }));

    await elegirEstado(user, 'Cancelado');

    expect(screen.queryByText(/en carrera/)).not.toBeInTheDocument();
  });

  it('no muestra aviso en los estados que no lo tienen', async () => {
    const { user } = renderModal(crearReclamo({ ofertas_en_carrera: 2 }));

    await elegirEstado(user, 'Aprobado');

    expect(screen.queryByText(/en carrera/)).not.toBeInTheDocument();
  });

  it('se cierra sin romper después de elegir un estado con aviso', async () => {
    const reclamo = crearReclamo({ ofertas_en_carrera: 2 });
    const { user, rerender, onClose, onEstadoCambiado } = renderModal(reclamo);
    await elegirEstado(user, 'Cancelado');

    // El padre cierra el modal pasando reclamo={null} (ver ClaimsListPage).
    rerender(
      <ChangeStatusModal reclamo={null} onClose={onClose} onEstadoCambiado={onEstadoCambiado} />,
    );

    expect(screen.queryByText('Cambiar estado del reclamo')).not.toBeInTheDocument();
  });

  it('exige el motivo de la cancelación antes de guardar', async () => {
    const actualizado = crearReclamo({ estado: 'CANCELADO', estados_posibles: [] });
    cambiarEstadoReclamo.mockResolvedValue(actualizado);
    const { user, onClose, onEstadoCambiado } = renderModal(crearReclamo());

    await elegirEstado(user, 'Cancelado');
    const guardar = screen.getByRole('button', { name: 'Cambiar estado' });
    expect(guardar).toBeDisabled();

    await user.type(
      screen.getByRole('textbox', { name: /Motivo de la cancelación/ }),
      'La escuela lo resolvió',
    );
    await user.click(guardar);

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(cambiarEstadoReclamo).toHaveBeenCalledWith(1, 'CANCELADO', 'La escuela lo resolvió');
    expect(notifySuccess).toHaveBeenCalledWith('El reclamo pasó a "Cancelado".');
    expect(onEstadoCambiado).toHaveBeenCalledWith(actualizado);
  });

  it('muestra el error del backend y deja el modal abierto', async () => {
    cambiarEstadoReclamo.mockRejectedValue(new Error('No se puede pasar de "A" a "B"'));
    const { user, onClose, onEstadoCambiado } = renderModal(crearReclamo());

    await elegirEstado(user, 'Aprobado');
    await user.click(screen.getByRole('button', { name: 'Cambiar estado' }));

    expect(cambiarEstadoReclamo).toHaveBeenCalledWith(1, 'APROBADO', '');
    await waitFor(() => expect(notifyError).toHaveBeenCalledWith('No se puede pasar de "A" a "B"'));
    expect(onEstadoCambiado).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it('explica que un reclamo en estado final ya no puede cambiar', () => {
    renderModal(crearReclamo({ estado: 'FINALIZADO', estados_posibles: [] }));

    expect(screen.getByText(/está en un estado final/)).toBeInTheDocument();
    expect(screen.queryByRole('combobox', { name: 'Nuevo estado' })).not.toBeInTheDocument();
  });
});
