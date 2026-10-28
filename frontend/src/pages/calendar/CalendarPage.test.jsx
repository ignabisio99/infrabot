import { screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  listarComentariosReclamo,
  obtenerHistorialReclamo,
  obtenerReclamo,
  obtenerVisitaReclamo,
} from '../../api/reclamos';
import { listarVisitas } from '../../api/visitas';
import { render } from '../../test/render';
import { CalendarPage } from './CalendarPage';

vi.mock('../../api/visitas');
vi.mock('../../api/reclamos');
vi.mock('../../api/conversaciones');
vi.mock('../../utils/notifications', () => ({ notifyError: vi.fn(), notifySuccess: vi.fn() }));
vi.mock('../../utils/auth', () => ({
  esAdministrador: () => false,
  esContratista: () => true,
  esInspector: () => false,
  getUsuarioActual: () => ({ id: 7, tipo: 'CONTRATISTA' }),
}));

function RutaActual() {
  const { pathname } = useLocation();
  return <div>ruta:{pathname}</div>;
}

function renderCalendario() {
  return render(
    <MemoryRouter initialEntries={['/calendario']}>
      <Routes>
        <Route
          path="/calendario"
          element={
            <>
              <CalendarPage />
              <RutaActual />
            </>
          }
        />
        <Route path="/portal/reclamos/:id/presupuestar" element={<RutaActual />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe('CalendarPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    listarVisitas.mockResolvedValue([
      {
        id: 1,
        reclamo_id: 12,
        nombre_escuela: 'Escuela 12',
        ubicacion: 'Mitre 10',
        nombre_empresa: 'Plomería Integral',
        estado: 'CONFIRMADA',
        fecha_visita: new Date().toISOString(),
        horario_confirmado: '30/10/2026 10:00',
      },
    ]);
    obtenerReclamo.mockResolvedValue({
      id: 12,
      estado: 'VISITA_COORDINADA',
      estados_posibles: [],
      prioridad: 'MEDIA',
      categoria: 'Plomería',
      nombre_escuela: 'Escuela 12',
      ubicacion: 'Mitre 10',
      descripcion: 'Pérdida de agua en el baño.',
      observaciones: null,
      fotos: [],
      telefono_creador: null,
    });
    obtenerHistorialReclamo.mockResolvedValue([]);
    obtenerVisitaReclamo.mockResolvedValue(null);
    listarComentariosReclamo.mockResolvedValue([]);
  });

  it('abre el reclamo de la visita y no el formulario del presupuesto', async () => {
    const { user } = renderCalendario();

    await user.click(await screen.findByText('Visita - Escuela 12'));
    await user.click(screen.getByRole('button', { name: 'Ver reclamo' }));

    expect(await screen.findByText('Pérdida de agua en el baño.')).toBeInTheDocument();
    expect(screen.queryByText('Tu presupuesto ya no se puede modificar')).not.toBeInTheDocument();
    expect(screen.queryByText('Próximo paso')).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'Avance' })).not.toBeInTheDocument();
    expect(screen.queryByRole('tab', { name: 'IA' })).not.toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Fotos' })).toBeInTheDocument();
    expect(screen.getByText('ruta:/calendario')).toBeInTheDocument();
  });
});
