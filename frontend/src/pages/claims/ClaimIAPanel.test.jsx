import { fireEvent, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  analizarMediaReclamo,
  buscarDuplicados,
  clasificarReclamo,
  crearEstimacion,
  listarRecomendaciones,
  obtenerEstimacion,
  orquestarReclamo,
} from '../../api/ai';
import { render } from '../../test/render';
import { ClaimIAPanel } from './ClaimIAPanel';

vi.mock('../../api/ai', () => ({
  analizarMediaReclamo: vi.fn(),
  buscarDuplicados: vi.fn(),
  clasificarReclamo: vi.fn(),
  crearEstimacion: vi.fn(),
  listarRecomendaciones: vi.fn(),
  obtenerEstimacion: vi.fn(),
  orquestarReclamo: vi.fn(),
}));
vi.mock('../../utils/notifications', () => ({ notifyError: vi.fn(), notifySuccess: vi.fn() }));

const ACCIONES = [
  'Reaplicar clasificación',
  'Volver a buscar',
  'Regenerar estimación',
  'Reanalizar fotos',
  'Regenerar todo el análisis',
];

const RECLAMO = {
  id: 1,
  categoria: 'Plomería',
  prioridad: 'MEDIA',
  fotos: [{ id: 10, tipo: 'IMAGEN', url: '/fotos/10.jpg' }],
};

async function renderPanel(props = {}) {
  const resultado = render(<ClaimIAPanel reclamo={RECLAMO} {...props} />);
  // Esperar la carga inicial: mientras busca duplicados ese botón queda en `loading`.
  await screen.findByText('No se encontraron reclamos similares.');
  return resultado;
}

describe('ClaimIAPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    obtenerEstimacion.mockResolvedValue(null);
    buscarDuplicados.mockResolvedValue({ reclamo_id: 1, candidatos: [] });
    listarRecomendaciones.mockResolvedValue([]);
  });

  it('con el reclamo abierto deja regenerar el análisis', async () => {
    await renderPanel();

    for (const accion of ACCIONES) {
      expect(screen.getByRole('button', { name: accion })).toBeEnabled();
    }
    expect(screen.getByText(/los botones de abajo solo regeneran/)).toBeInTheDocument();
  });

  it('en solo lectura deshabilita todas las acciones y explica por qué', async () => {
    await renderPanel({ soloLectura: true });

    for (const accion of ACCIONES) {
      expect(screen.getByRole('button', { name: accion })).toBeDisabled();
    }
    expect(screen.getByText(/El reclamo está cerrado/)).toBeInTheDocument();
  });

  it('en solo lectura sigue mostrando los resultados guardados', async () => {
    listarRecomendaciones.mockResolvedValue([
      {
        tipo: 'CLASIFICACION',
        confianza: 0.9,
        payload: JSON.stringify({ categoria: 'Electricidad', justificacion: 'Hay un corto.' }),
      },
    ]);

    render(<ClaimIAPanel reclamo={RECLAMO} soloLectura />);

    expect(await screen.findByText('Hay un corto.')).toBeInTheDocument();
    expect(screen.getByText('90%')).toBeInTheDocument();
  });

  it('sin precedentes muestra el monto y una sola aclaración', async () => {
    obtenerEstimacion.mockResolvedValue({
      id: 4,
      materiales: '62500.00',
      mano_obra: '100000.00',
      otros: '12500.00',
      total: '175000.00',
      confianza: 0.2,
      sin_precedentes: true,
      justificacion: 'Sin precedentes históricos. El monto es orientativo para el rubro.',
      detalle: JSON.stringify({
        justificacion: 'Sin precedentes históricos. El monto es orientativo para el rubro.',
        validacion: { motivo: 'sin_referencias' },
        referencias_ids: [],
      }),
    });

    await renderPanel();

    expect(screen.getByText(/Mano de obra/)).toBeInTheDocument();
    expect(screen.getByText(/Total/)).toBeInTheDocument();
    expect(screen.getByText('Sin precedentes históricos')).toBeInTheDocument();
    expect(screen.getAllByText(/trabajo histórico parecido/)).toHaveLength(1);
  });

  it('en solo lectura los clicks no llaman a la IA', async () => {
    await renderPanel({ soloLectura: true });
    buscarDuplicados.mockClear();

    // fireEvent y no user.click: userEvent se niega a clickear un botón deshabilitado.
    for (const accion of ACCIONES) {
      fireEvent.click(screen.getByRole('button', { name: accion }));
    }

    for (const llamada of [
      clasificarReclamo,
      buscarDuplicados,
      crearEstimacion,
      analizarMediaReclamo,
      orquestarReclamo,
    ]) {
      expect(llamada).not.toHaveBeenCalled();
    }
  });
});
