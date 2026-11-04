import { screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { listarReclamos } from '../../api/reclamos';
import { render } from '../../test/render';
import { ClaimsListPage } from './ClaimsListPage';

vi.mock('../../api/reclamos');
vi.mock('../../utils/auth', () => ({ esInspector: () => false }));
vi.mock('./ClaimDetailDrawer', () => ({ ClaimDetailDrawer: () => null }));

const DIA = 24 * 60 * 60 * 1000;
const haceDias = (dias) => new Date(Date.now() - dias * DIA).toISOString();

function reclamo(datos) {
  return {
    prioridad: 'MEDIA',
    categoria: 'Plomería',
    nombre_escuela: 'ESCUELA DE EDUCACIÓN PRIMARIA N°10 ESTADOS UNIDOS DE NORTEAMERICA',
    ubicacion: 'MITRE 5110',
    descripcion: 'Pierde la canilla',
    estados_posibles: [],
    ofertas_en_carrera: 0,
    alta_whatsapp: false,
    requiere_revision: false,
    fecha_creacion: haceDias(20),
    ...datos,
  };
}

async function renderListado(reclamos) {
  listarReclamos.mockResolvedValue(reclamos);
  render(
    <MemoryRouter>
      <ClaimsListPage />
    </MemoryRouter>,
  );
  await screen.findByText('REC-00000001');
}

const fila = (id) => screen.getByText(id).closest('tr');

describe('ClaimsListPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('acorta el nombre de la escuela y muestra la fecha relativa', async () => {
    await renderListado([reclamo({ id: 1, estado: 'PENDIENTE_REVISION' })]);

    expect(screen.getByText('EP N°10 Estados Unidos de Norteamerica')).toHaveAttribute(
      'title',
      'ESCUELA DE EDUCACIÓN PRIMARIA N°10 ESTADOS UNIDOS DE NORTEAMERICA',
    );
    expect(screen.getByText('Mitre 5110')).toBeInTheDocument();
    expect(screen.getByText('hace 20 días')).toBeInTheDocument();
  });

  it('avisa que el bot lo derivó sólo mientras sigue en revisión', async () => {
    await renderListado([
      reclamo({
        id: 1,
        estado: 'PENDIENTE_REVISION',
        requiere_revision: true,
        alta_whatsapp: true,
      }),
      reclamo({ id: 2, estado: 'PENDIENTE_PRESUPUESTO', requiere_revision: true }),
    ]);

    expect(
      within(fila('REC-00000001')).getByLabelText('El bot lo derivó a un operador'),
    ).toBeInTheDocument();
    expect(
      within(fila('REC-00000001')).getByLabelText('Creado desde WhatsApp'),
    ).toBeInTheDocument();
    expect(
      within(fila('REC-00000002')).queryByLabelText('El bot lo derivó a un operador'),
    ).not.toBeInTheDocument();
  });
});
