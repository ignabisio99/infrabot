import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { buscarDuplicados, listarRecomendaciones, obtenerEstimacion } from '../../api/ai';
import { listarSolicitudesPresupuesto } from '../../api/listasContratistas';
import { obtenerPresupuesto } from '../../api/presupuestos';
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
// Solo interesa que avise que se decidió; los modales de decisión tienen sus propios tests.
vi.mock('../budgets/BudgetItemsModal', () => ({
  BudgetItemsModal: ({ presupuesto, onDecidido }) =>
    presupuesto ? <button onClick={onDecidido}>Decidir (simulado)</button> : null,
}));
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

  function oferta(datos) {
    return {
      contratista_id: datos.presupuesto_id,
      especialidad: 'Plomería',
      telefono: '+5491147779012',
      fecha_solicitud: '2026-11-02T10:00:00Z',
      presupuesto_cargado: true,
      presupuesto_fecha: '2026-11-03T10:00:00Z',
      version: 1,
      ...datos,
    };
  }

  async function abrirPresupuestos(reclamo, solicitudes) {
    obtenerReclamo.mockResolvedValue(reclamo);
    listarSolicitudesPresupuesto.mockResolvedValue(solicitudes);
    const resultado = render(<ClaimDetailDrawer reclamoId={reclamo.id} onClose={vi.fn()} />);
    await resultado.user.click(await screen.findByRole('tab', { name: 'Presupuestos' }));
    return resultado;
  }

  it('resume arriba el presupuesto aprobado con contratista y monto', async () => {
    await abrirPresupuestos(crearReclamo({ estado: 'PENDIENTE_COORDINACION' }), [
      oferta({
        presupuesto_id: 8,
        nombre_empresa: 'Electricidad del Sur',
        presupuesto_estado: 'RECHAZADO',
        monto: '3000.00',
      }),
      oferta({
        presupuesto_id: 7,
        nombre_empresa: 'Plomería Integral',
        presupuesto_estado: 'APROBADO',
        monto: '4200.00',
        version: 2,
      }),
    ]);

    expect(screen.getByText('Presupuesto aprobado')).toBeInTheDocument();
    expect(screen.getByText(/\+54 9 11 4777-9012 · Versión 2/)).toBeInTheDocument();
    expect(screen.getAllByText('$ 4.200,00')).toHaveLength(2);
    // La aprobada va primero aunque la rechazada sea más barata, y no se marca "más barata".
    const empresas = screen.getAllByText(/^(Plomería Integral|Electricidad del Sur)$/);
    expect(empresas.map((e) => e.textContent)).toEqual([
      'Plomería Integral',
      'Plomería Integral',
      'Electricidad del Sur',
    ]);
    expect(screen.queryByText('Más barata')).not.toBeInTheDocument();
  });

  it('marca la más barata entre las ofertas que siguen en carrera', async () => {
    await abrirPresupuestos(crearReclamo({ estado: 'EN_EVALUACION' }), [
      oferta({
        presupuesto_id: 7,
        nombre_empresa: 'Cara SA',
        presupuesto_estado: 'RECIBIDO',
        monto: '3600',
      }),
      oferta({
        presupuesto_id: 8,
        nombre_empresa: 'Barata SA',
        presupuesto_estado: 'RECIBIDO',
        monto: '3000',
      }),
      oferta({
        presupuesto_id: 9,
        nombre_empresa: 'Descartada SA',
        presupuesto_estado: 'RECHAZADO',
        monto: '100',
      }),
    ]);

    const empresas = screen.getAllByText(/^(Cara|Barata|Descartada) SA$/);
    expect(empresas.map((e) => e.textContent)).toEqual(['Barata SA', 'Cara SA', 'Descartada SA']);
    expect(screen.getAllByText('Más barata')).toHaveLength(1);
    expect(screen.getByText('+20% que la más barata')).toBeInTheDocument();
    expect(screen.queryByText('Presupuesto aprobado')).not.toBeInTheDocument();
  });

  it('muestra la derivación del bot como aviso y no como información adicional', async () => {
    obtenerReclamo.mockResolvedValue(
      crearReclamo({
        observaciones:
          'Llamar antes de ir\n[DERIVADO A OPERADOR] confianza de clasificación baja (0.00)',
      }),
    );
    render(<ClaimDetailDrawer reclamoId={1} onClose={vi.fn()} />);

    expect(await screen.findByText('El bot lo derivó a un operador')).toBeInTheDocument();
    expect(screen.getByText('Confianza de clasificación baja (0.00)')).toBeInTheDocument();
    expect(screen.getByText('Llamar antes de ir')).toBeInTheDocument();
    expect(screen.queryByText(/DERIVADO A OPERADOR/)).not.toBeInTheDocument();
  });

  it('al decidir un presupuesto recarga el reclamo y avisa al listado', async () => {
    obtenerReclamo
      .mockResolvedValueOnce(
        crearReclamo({ estado: 'EN_EVALUACION', estados_posibles: ['CANCELADO'] }),
      )
      .mockResolvedValue(crearReclamo({ estado: 'APROBADO', estados_posibles: ['CANCELADO'] }));
    listarSolicitudesPresupuesto.mockResolvedValue([
      {
        contratista_id: 2,
        nombre_empresa: 'Plomería Integral',
        especialidad: 'Plomería',
        presupuesto_cargado: true,
        presupuesto_id: 7,
        presupuesto_estado: 'RECIBIDO',
        presupuesto_fecha: '2026-11-03T10:00:00Z',
        version: 1,
      },
    ]);
    obtenerPresupuesto.mockResolvedValue({ id: 7 });
    const onReclamoActualizado = vi.fn();
    const { user } = render(
      <ClaimDetailDrawer
        reclamoId={1}
        onClose={vi.fn()}
        onReclamoActualizado={onReclamoActualizado}
      />,
    );

    expect(await screen.findByText('Evaluar presupuestos')).toBeInTheDocument();
    await user.click(screen.getByRole('tab', { name: 'Presupuestos' }));
    await user.click(await screen.findByText('Plomería Integral'));
    await user.click(await screen.findByRole('button', { name: 'Decidir (simulado)' }));

    expect(await screen.findByText('Iniciar coordinación')).toBeInTheDocument();
    expect(obtenerReclamo).toHaveBeenCalledTimes(2);
    expect(onReclamoActualizado).toHaveBeenCalledOnce();
  });
});
