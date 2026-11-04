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

  it('muestra la calificación con su nivel, la observación y el teléfono formateado', async () => {
    listarContratistas.mockResolvedValue([
      { ...TECHOS_SUR, telefono: 'sim5491147779012', observaciones_calificacion: 'Cumple plazos' },
      {
        ...TECHOS_SUR,
        id: 3,
        nombre_empresa: 'Nuevo SRL',
        telefono: '+5493514779012',
        calificacion: null,
      },
    ]);
    await renderPagina();

    expect(screen.getByText('4/5 · Buena')).toBeInTheDocument();
    expect(screen.getByText('Sin calificar')).toBeInTheDocument();
    expect(screen.getByText('Cumple plazos')).toBeInTheDocument();
    expect(screen.getByText('+54 9 11 4777-9012')).toBeInTheDocument();
    expect(screen.getAllByText('Simulado')).toHaveLength(1);
  });

  it('busca por nombre, especialidad o teléfono y ordena por calificación', async () => {
    listarContratistas.mockResolvedValue([
      {
        ...TECHOS_SUR,
        id: 1,
        nombre_empresa: 'Alfa Techos',
        calificacion: 3,
        telefono: '+541100000001',
      },
      {
        ...TECHOS_SUR,
        id: 3,
        nombre_empresa: 'Beta Plomería',
        especialidad: 'Plomería',
        calificacion: 5,
        telefono: '+541100000003',
      },
      {
        ...TECHOS_SUR,
        id: 4,
        nombre_empresa: 'Gama Techos',
        calificacion: null,
        telefono: '+541100000004',
      },
    ]);
    const { user } = render(
      <MemoryRouter>
        <ContractorsListPage />
      </MemoryRouter>,
    );
    await screen.findByText('Alfa Techos');
    const nombres = () =>
      screen
        .getAllByRole('row')
        .slice(1)
        .map((fila) => within(fila).getAllByRole('cell')[0].textContent);

    expect(nombres()).toEqual(['Alfa Techos', 'Beta Plomería', 'Gama Techos']);

    await user.click(screen.getByRole('combobox', { name: 'Ordenar contratistas' }));
    await user.click(screen.getByRole('option', { name: 'Mejor calificación' }));
    expect(nombres()).toEqual(['Beta Plomería', 'Alfa Techos', 'Gama Techos']);

    const buscador = screen.getByRole('textbox', { name: 'Buscar contratista' });
    await user.type(buscador, 'plomeria');
    expect(nombres()).toEqual(['Beta Plomería']);
    expect(screen.getByText('1 de 3 contratistas')).toBeInTheDocument();

    await user.clear(buscador);
    await user.type(buscador, '0004');
    expect(nombres()).toEqual(['Gama Techos']);

    await user.clear(buscador);
    await user.type(buscador, 'zzz');
    expect(
      screen.getByText('No hay contratistas que coincidan con la búsqueda.'),
    ).toBeInTheDocument();
  });

  it('marca los activos que comparten teléfono, sin contar a los dados de baja', async () => {
    listarContratistas.mockResolvedValue([
      { ...TECHOS_SUR, telefono: 'sim5491147779012' },
      { ...TECHOS_SUR, id: 3, nombre_empresa: 'Techos Sur Bis', telefono: '+54 9 11 4777-9012' },
      RETIRADO,
    ]);
    await renderPagina();

    expect(screen.getAllByText('Teléfono repetido')).toHaveLength(2);
    expect(screen.getByText(/2 con teléfono repetido/)).toBeInTheDocument();
  });

  it('no marca como repetido a quien comparte teléfono con un dado de baja', async () => {
    await renderPagina();
    expect(screen.queryByText('Teléfono repetido')).not.toBeInTheDocument();
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
