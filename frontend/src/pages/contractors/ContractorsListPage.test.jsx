import { screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  darDeBajaContratista,
  listarContratistas,
  reactivarContratista,
} from '../../api/contratistas';
import { render } from '../../test/render';
import { ContractorsListPage } from './ContractorsListPage';

vi.mock('../../api/contratistas', () => ({
  darDeBajaContratista: vi.fn(),
  listarContratistas: vi.fn(),
  reactivarContratista: vi.fn(),
}));
vi.mock('../../utils/notifications', () => ({ notifyError: vi.fn(), notifySuccess: vi.fn() }));

const TECHOS_SUR = {
  id: 1,
  nombre_empresa: 'Techos Sur',
  telefono: '1111',
  direccion: 'Calle 1',
  especialidad: 'Techos',
  calificacion: 4,
  fecha_baja: null,
};
const RETIRADO = {
  ...TECHOS_SUR,
  id: 2,
  nombre_empresa: 'Retirado SA',
  fecha_baja: '2026-10-01T12:00:00Z',
};

async function renderPagina() {
  const resultado = render(
    <MemoryRouter>
      <ContractorsListPage />
    </MemoryRouter>,
  );
  await screen.findByText('Techos Sur');
  return resultado;
}

async function abrirAcciones(user, nombre) {
  const fila = screen.getByText(nombre).closest('tr');
  await user.click(within(fila).getByRole('button', { name: 'Acciones' }));
}

describe('ContractorsListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listarContratistas.mockResolvedValue([TECHOS_SUR, RETIRADO]);
  });

  it('oculta los dados de baja hasta que se pide verlos', async () => {
    const { user } = await renderPagina();

    expect(listarContratistas).toHaveBeenCalledWith({ incluirBaja: true });
    expect(screen.queryByText('Retirado SA')).not.toBeInTheDocument();

    await user.click(screen.getByLabelText('Mostrar dados de baja (1)'));

    expect(screen.getByText('Retirado SA')).toBeInTheDocument();
    expect(screen.getByText('Dado de baja')).toBeInTheDocument();
  });

  it('da de baja tras confirmar', async () => {
    darDeBajaContratista.mockResolvedValue();
    const { user } = await renderPagina();

    await abrirAcciones(user, 'Techos Sur');
    await user.click(screen.getByRole('menuitem', { name: 'Dar de baja' }));
    expect(
      screen.getByText(/Sus presupuestos y visitas anteriores se conservan/),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Dar de baja' }));

    expect(darDeBajaContratista).toHaveBeenCalledWith(1);
    expect(await screen.findByText('No hay contratistas activos.')).toBeInTheDocument();
  });

  it('si tiene trabajo en curso muestra por qué no se pudo y no lo saca de la lista', async () => {
    darDeBajaContratista.mockRejectedValue(
      new Error(
        'No se puede dar de baja a Techos Sur: tiene presupuestos en curso en el reclamo #7.',
      ),
    );
    const { user } = await renderPagina();

    await abrirAcciones(user, 'Techos Sur');
    await user.click(screen.getByRole('menuitem', { name: 'Dar de baja' }));
    await user.click(screen.getByRole('button', { name: 'Dar de baja' }));

    expect(await screen.findByText(/en curso en el reclamo #7/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(screen.getByText('Techos Sur')).toBeInTheDocument();
  });

  it('reactiva a un dado de baja', async () => {
    reactivarContratista.mockResolvedValue({ ...RETIRADO, fecha_baja: null });
    const { user } = await renderPagina();
    await user.click(screen.getByLabelText('Mostrar dados de baja (1)'));

    await abrirAcciones(user, 'Retirado SA');
    expect(screen.queryByRole('menuitem', { name: 'Dar de baja' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('menuitem', { name: 'Reactivar' }));

    expect(reactivarContratista).toHaveBeenCalledWith(2);
    expect(await screen.findByText('Retirado SA')).toBeInTheDocument();
    expect(screen.queryByText('Dado de baja')).not.toBeInTheDocument();
  });
});
