import { screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listarAdministradores } from '../../api/usuarios';
import { useEsMobile } from '../../hooks/useEsMobile';
import { render } from '../../test/render';
import { AdminsListPage } from './AdminsListPage';

vi.mock('../../api/usuarios', () => ({ listarAdministradores: vi.fn() }));
vi.mock('../../hooks/useEsMobile', () => ({ useEsMobile: vi.fn(() => false) }));

const ANA = {
  id: 1,
  nombre: 'Ana Pérez',
  email: 'ana@utn.local',
  telefono: '+5491122334455',
  direccion: 'Calle 1',
  fecha_creacion: '2026-03-10T12:00:00Z',
};
const BETO = {
  id: 2,
  nombre: 'Beto Gómez',
  email: 'beto@utn.local',
  telefono: null,
  direccion: null,
  fecha_creacion: '2026-05-02T12:00:00Z',
};

describe('AdminsListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useEsMobile.mockReturnValue(false);
  });

  it('lista los administradores y marca al usuario logueado', async () => {
    listarAdministradores.mockResolvedValue([ANA, BETO]);
    render(<AdminsListPage usuarioId={BETO.id} />);

    const filaAna = (await screen.findByText('Ana Pérez')).closest('tr');
    expect(within(filaAna).getByText('ana@utn.local')).toBeInTheDocument();
    expect(within(filaAna).getByText('+5491122334455')).toBeInTheDocument();
    expect(within(filaAna).queryByText('Vos')).not.toBeInTheDocument();

    const filaBeto = screen.getByText('Beto Gómez').closest('tr');
    expect(within(filaBeto).getByText('Vos')).toBeInTheDocument();
    expect(within(filaBeto).getAllByText('—')).toHaveLength(2);
  });

  it('no ofrece crear, editar ni eliminar', async () => {
    listarAdministradores.mockResolvedValue([ANA]);
    render(<AdminsListPage />);

    await screen.findByText('Ana Pérez');
    expect(screen.queryByRole('button')).not.toBeInTheDocument();
  });

  it('en celular muestra tarjetas en vez de tabla', async () => {
    useEsMobile.mockReturnValue(true);
    listarAdministradores.mockResolvedValue([ANA]);
    render(<AdminsListPage />);

    await screen.findByText('Ana Pérez');
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
    expect(screen.getByText('ana@utn.local')).toBeInTheDocument();
  });

  it('en celular muestra los mismos campos aunque falten datos', async () => {
    useEsMobile.mockReturnValue(true);
    listarAdministradores.mockResolvedValue([BETO]);
    render(<AdminsListPage usuarioId={BETO.id} />);

    await screen.findByText('Beto Gómez');
    expect(screen.getByText('Vos')).toBeInTheDocument();
    expect(screen.getByText('Teléfono')).toBeInTheDocument();
    expect(screen.getByText('Dirección')).toBeInTheDocument();
    expect(screen.getAllByText('—')).toHaveLength(2);
  });

  it('muestra el error del backend', async () => {
    listarAdministradores.mockRejectedValue(new Error('Solo los administradores pueden verlo'));
    render(<AdminsListPage />);

    expect(await screen.findByText('Solo los administradores pueden verlo')).toBeInTheDocument();
    expect(screen.queryByText(/Todavía no hay/)).not.toBeInTheDocument();
  });

  it('avisa cuando no hay administradores', async () => {
    listarAdministradores.mockResolvedValue([]);
    render(<AdminsListPage />);

    expect(
      await screen.findByText('Todavía no hay administradores registrados.'),
    ).toBeInTheDocument();
  });
});
