import { screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listarContratistas } from '../../api/contratistas';
import {
  ContratistasYaNotificadosError,
  listarListas,
  notificarContratistas,
} from '../../api/listasContratistas';
import { render } from '../../test/render';
import { notifyError, notifySuccess } from '../../utils/notifications';
import { NotifyContractorsModal } from './NotifyContractorsModal';

vi.mock('../../api/contratistas', () => ({ listarContratistas: vi.fn() }));
vi.mock('../../api/listasContratistas', async (importOriginal) => ({
  ...(await importOriginal()),
  listarListas: vi.fn(),
  notificarContratistas: vi.fn(),
}));
vi.mock('../../utils/notifications', () => ({ notifyError: vi.fn(), notifySuccess: vi.fn() }));

const TECHOS_SUR = { id: 1, nombre_empresa: 'Techos Sur', especialidad: 'Techos' };
const PLOMERIA = { id: 2, nombre_empresa: 'Plomería', especialidad: 'Sanitarios' };

function yaNotificado(contratista, datos = {}) {
  return {
    contratista_id: contratista.id,
    nombre_empresa: contratista.nombre_empresa,
    fecha_ultimo_aviso: new Date(Date.now() - 10 * 60 * 1000).toISOString(),
    presupuesto_cargado: false,
    ...datos,
  };
}

function exito(total) {
  return { total, enviados: total, resultados: [] };
}

async function renderModal() {
  const onClose = vi.fn();
  const resultado = render(<NotifyContractorsModal reclamoId={5} opened onClose={onClose} />);
  await screen.findByText('Seleccionar contratistas');
  return { ...resultado, onClose };
}

async function notificarA(user, ...contratistas) {
  for (const c of contratistas) {
    await user.click(screen.getByRole('combobox', { name: 'Contratistas' }));
    await user.click(screen.getByRole('option', { name: new RegExp(c.nombre_empresa) }));
  }
  await user.click(screen.getByRole('button', { name: 'Enviar notificación' }));
}

describe('NotifyContractorsModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listarContratistas.mockResolvedValue([TECHOS_SUR, PLOMERIA]);
    listarListas.mockResolvedValue([]);
  });

  it('pide confirmación si alguno ya fue notificado y al cancelar no reenvía', async () => {
    notificarContratistas.mockRejectedValueOnce(
      new ContratistasYaNotificadosError([yaNotificado(TECHOS_SUR, { presupuesto_cargado: true })]),
    );
    const { user, onClose } = await renderModal();

    await notificarA(user, TECHOS_SUR, PLOMERIA);

    expect(
      await screen.findByText('Este contratista ya fue notificado para este reclamo'),
    ).toBeInTheDocument();
    expect(screen.getByText(/hace 10 min/)).toBeInTheDocument();
    expect(screen.getByText(/ya mandó una oferta/)).toBeInTheDocument();
    expect(notificarContratistas).toHaveBeenCalledWith(5, {
      contratistaIds: [1, 2],
      yaNotificados: 'preguntar',
    });

    await user.click(screen.getByRole('button', { name: 'Cancelar' }));

    expect(screen.getByRole('button', { name: 'Enviar notificación' })).toBeInTheDocument();
    expect(notificarContratistas).toHaveBeenCalledTimes(1);
    expect(onClose).not.toHaveBeenCalled();
  });

  it('reenvía a todos al confirmar', async () => {
    notificarContratistas
      .mockRejectedValueOnce(new ContratistasYaNotificadosError([yaNotificado(TECHOS_SUR)]))
      .mockResolvedValueOnce(exito(2));
    const { user, onClose } = await renderModal();

    await notificarA(user, TECHOS_SUR, PLOMERIA);
    await user.click(await screen.findByRole('button', { name: 'Reenviar a todos' }));

    expect(notificarContratistas).toHaveBeenLastCalledWith(5, {
      contratistaIds: [1, 2],
      yaNotificados: 'reenviar',
    });
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });

  it('puede notificar solo a los que todavía no tenían aviso', async () => {
    notificarContratistas
      .mockRejectedValueOnce(new ContratistasYaNotificadosError([yaNotificado(TECHOS_SUR)]))
      .mockResolvedValueOnce(exito(1));
    const { user } = await renderModal();

    await notificarA(user, TECHOS_SUR, PLOMERIA);
    await user.click(await screen.findByRole('button', { name: 'Solo a los nuevos (1)' }));

    expect(notificarContratistas).toHaveBeenLastCalledWith(5, {
      contratistaIds: [1, 2],
      yaNotificados: 'omitir',
    });
    await waitFor(() =>
      expect(notifySuccess).toHaveBeenCalledWith(
        'Notificación enviada a 1 de 1 contratista(s). No se reenvió al que ya estaba notificado.',
      ),
    );
  });

  it('si no le llegó a ninguno no da el envío por exitoso', async () => {
    notificarContratistas.mockResolvedValueOnce({
      total: 1,
      enviados: 0,
      resultados: [{ ...PLOMERIA, contratista_id: 2, enviado: false }],
    });
    const { user } = await renderModal();

    await notificarA(user, PLOMERIA);

    await waitFor(() =>
      expect(notifyError).toHaveBeenCalledWith('No se pudo notificar a: Plomería'),
    );
    expect(notifySuccess).not.toHaveBeenCalled();
  });

  it('si todos ya fueron notificados solo ofrece reenviar', async () => {
    notificarContratistas.mockRejectedValueOnce(
      new ContratistasYaNotificadosError([yaNotificado(TECHOS_SUR)]),
    );
    const { user } = await renderModal();

    await notificarA(user, TECHOS_SUR);

    expect(await screen.findByRole('button', { name: 'Reenviar' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Solo a los nuevos/ })).not.toBeInTheDocument();
  });
});
