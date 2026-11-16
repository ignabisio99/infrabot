import { screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { obtenerMiFicha, obtenerMiPresupuesto } from '../../api/contratistas';
import { crearPresupuesto } from '../../api/presupuestos';
import { obtenerReclamo } from '../../api/reclamos';
import { render } from '../../test/render';
import { notifySuccess } from '../../utils/notifications';
import { PRESUPUESTOS_DEMO } from '../../utils/presupuestosDemo';
import { PresupuestarReclamoPage } from './PresupuestarReclamoPage';

vi.mock('react-router', () => ({ useParams: () => ({ id: '7' }) }));
vi.mock('../../api/reclamos', () => ({ obtenerReclamo: vi.fn() }));
vi.mock('../../api/contratistas', () => ({
  obtenerMiFicha: vi.fn(),
  obtenerMiPresupuesto: vi.fn(),
  solicitarInformacionReclamo: vi.fn(),
}));
vi.mock('../../api/presupuestos', () => ({
  actualizarPresupuesto: vi.fn(),
  crearPresupuesto: vi.fn(),
}));
vi.mock('../../api/rolesManoObra', () => ({ listarRolesManoObra: vi.fn().mockResolvedValue([]) }));
vi.mock('./ClaimComments', () => ({ ClaimComments: () => null }));
vi.mock('../../utils/notifications', () => ({ notifyError: vi.fn(), notifySuccess: vi.fn() }));

const RECLAMO = {
  id: 7,
  nombre_escuela: 'Escuela Nº 13',
  ubicacion: 'Calle 1',
  prioridad: 'ALTA',
  categoria: 'Plomería',
  descripcion: 'Desborde constante en el inodoro del baño de varones.',
  estado: 'PENDIENTE_PRESUPUESTO',
  admite_presupuesto: true,
  fotos: [],
  telefono_creador: null,
};

async function renderPagina(nombreEmpresa) {
  obtenerMiFicha.mockResolvedValue({ id: 3, nombre_empresa: nombreEmpresa, fecha_baja: null });
  const resultado = render(<PresupuestarReclamoPage />);
  await screen.findByText('Cargar presupuesto');
  return resultado;
}

const botonAutocompletar = () => screen.findByRole('button', { name: 'Autocompletar presupuesto' });

describe('PresupuestarReclamoPage · autocompletar presupuesto de la demo', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.setItem('infrabot_user', JSON.stringify({ tipo: 'CONTRATISTA' }));
    obtenerReclamo.mockResolvedValue(RECLAMO);
    obtenerMiPresupuesto.mockResolvedValue(null);
  });

  it('Rodriguez Repara SRL completa el presupuesto 1 de $90.000', async () => {
    const { user } = await renderPagina('Rodriguez Repara SRL');

    await user.click(await botonAutocompletar());

    expect(await screen.findByDisplayValue('Visita y diagnóstico')).toBeInTheDocument();
    expect(
      screen.getByDisplayValue('Destapación de sifón (sonda manual / desarme y limpieza)'),
    ).toBeInTheDocument();
    expect(screen.getByDisplayValue('Limpieza y secado básico del área')).toBeInTheDocument();
    expect(screen.getByDisplayValue(PRESUPUESTOS_DEMO[0].detalle_tarea)).toBeInTheDocument();
    expect(screen.getByDisplayValue(PRESUPUESTOS_DEMO[0].observaciones)).toBeInTheDocument();
    expect(screen.getByText(/^Total:.*90\.000,00/)).toBeInTheDocument();
    expect(notifySuccess).toHaveBeenCalledWith(expect.stringContaining('90.000,00'));
  });

  it('la Cooperativa La Nueva Fabriquera completa el presupuesto 2 de $1.080.000', async () => {
    const { user } = await renderPagina('Cooperativa La Nueva Fabriquera');

    await user.click(await botonAutocompletar());

    expect(await screen.findByDisplayValue('Inspección con cámara de cañería')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Kit de materiales “premium”')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Garantía extendida')).toBeInTheDocument();
    expect(screen.getByText(/^Total:.*1\.080\.000,00/)).toBeInTheDocument();
  });

  it('otros contratistas no ven el botón', async () => {
    await renderPagina('Plomería Integral SA');

    expect(
      screen.queryByRole('button', { name: 'Autocompletar presupuesto' }),
    ).not.toBeInTheDocument();
  });

  it('lo autocompletado se puede enviar tal cual', async () => {
    crearPresupuesto.mockResolvedValue({});
    const { user } = await renderPagina('Rodriguez Repara SRL');

    await user.click(await botonAutocompletar());
    await screen.findByDisplayValue('Visita y diagnóstico');
    await user.click(screen.getByRole('button', { name: 'Enviar presupuesto' }));

    expect(crearPresupuesto).toHaveBeenCalledTimes(1);
    const enviado = crearPresupuesto.mock.calls[0][0];
    expect(enviado).toMatchObject({
      reclamo_id: 7,
      contratista_id: 3,
      detalle_tarea: PRESUPUESTOS_DEMO[0].detalle_tarea,
      observaciones: PRESUPUESTOS_DEMO[0].observaciones,
    });
    expect(enviado.items).toHaveLength(4);
    expect(enviado.items[0]).toEqual({
      tipo: 'MATERIAL',
      descripcion: 'Visita y diagnóstico',
      cantidad: 1,
      unidad: 'unidad',
      costo_unitario: 20000,
    });
  });
});
