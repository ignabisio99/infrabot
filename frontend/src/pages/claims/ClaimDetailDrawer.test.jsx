import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { buscarDuplicados, listarRecomendaciones, obtenerEstimacion } from '../../api/ai';
import { listarSolicitudesPresupuesto } from '../../api/listasContratistas';
import {
  listarComentariosReclamo,
  listarSolicitudesInspeccion,
  obtenerHistorialReclamo,
  obtenerMovimientosPresupuestos,
  obtenerReclamo,
  obtenerVisitaReclamo,
} from '../../api/reclamos';
import { render } from '../../test/render';
import { ClaimDetailDrawer } from './ClaimDetailDrawer';
import { estadosFinales } from './estados';

vi.mock('../../api/ai');
vi.mock('../../api/contratistas');
vi.mock('../../api/conversaciones');
vi.mock('../../api/listasContratistas');
vi.mock('../../api/presupuestos');
vi.mock('../../api/reclamos');
vi.mock('../../layout/NotificationBell', () => ({ avisarNotificacionesCambiaron: vi.fn() }));
vi.mock('../../utils/notifications', () => ({ notifyError: vi.fn(), notifySuccess: vi.fn() }));
vi.mock('../../utils/auth', () => ({
  esAdministrador: () => true,
  esContratista: () => false,
  esInspector: () => false,
  getUsuarioActual: () => ({ id: 1 }),
}));

function crearReclamo(datos = {}) {
  return {
    id: 1,
    estado: 'EN_EJECUCION',
    estados_posibles: ['FINALIZADO', 'CANCELADO'],
    prioridad: 'MEDIA',
    categoria: 'Plomería',
    nombre_escuela: 'Escuela Primaria N°10',
    ubicacion: 'Calle 1',
    descripcion: 'Pierde el tanque de agua',
    observaciones: null,
    telefono_creador: null,
    fotos: [{ id: 10, tipo: 'IMAGEN', url: '/fotos/10.jpg', usuario_id: null }],
    ...datos,
  };
}

async function abrirPestañaIA(reclamo) {
  obtenerReclamo.mockResolvedValue(reclamo);
  const resultado = render(<ClaimDetailDrawer reclamoId={reclamo.id} onClose={vi.fn()} />);
  await resultado.user.click(await screen.findByRole('tab', { name: 'IA' }));
  await screen.findByText('No se encontraron reclamos similares.');
  return resultado;
}

describe('ClaimDetailDrawer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    obtenerHistorialReclamo.mockResolvedValue([]);
    obtenerVisitaReclamo.mockResolvedValue(null);
    listarComentariosReclamo.mockResolvedValue([]);
    obtenerMovimientosPresupuestos.mockResolvedValue([]);
    listarSolicitudesInspeccion.mockResolvedValue([]);
    listarSolicitudesPresupuesto.mockResolvedValue([]);
    obtenerEstimacion.mockResolvedValue(null);
    buscarDuplicados.mockResolvedValue({ reclamo_id: 1, candidatos: [] });
    listarRecomendaciones.mockResolvedValue([]);
  });

  it('con el reclamo abierto deja usar las acciones de IA', async () => {
    await abrirPestañaIA(crearReclamo());

    expect(screen.getByRole('button', { name: 'Regenerar todo el análisis' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Reaplicar clasificación' })).toBeEnabled();
    expect(screen.getByRole('button', { name: 'Cambiar estado del reclamo' })).toBeEnabled();
  });

  // DESIERTO no es final: se puede volver a llamar a presupuesto.
  it('un reclamo desierto sigue con las acciones de IA habilitadas', async () => {
    await abrirPestañaIA(
      crearReclamo({ estado: 'DESIERTO', estados_posibles: ['PENDIENTE_PRESUPUESTO'] }),
    );

    expect(screen.getByRole('button', { name: 'Regenerar todo el análisis' })).toBeEnabled();
  });

  it.each(estadosFinales)('en %s deshabilita las acciones de IA', async (estado) => {
    await abrirPestañaIA(crearReclamo({ estado, estados_posibles: [] }));

    for (const accion of [
      'Reaplicar clasificación',
      'Volver a buscar',
      'Regenerar estimación',
      'Reanalizar fotos',
      'Regenerar todo el análisis',
    ]) {
      expect(screen.getByRole('button', { name: accion })).toBeDisabled();
    }
    expect(screen.getByText(/El reclamo está cerrado/)).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Cambiar estado del reclamo' }),
    ).not.toBeInTheDocument();
  });
});
