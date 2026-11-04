import { screen } from '@testing-library/react';
import dayjs from 'dayjs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { obtenerReporte } from '../../api/reportes';
import { render } from '../../test/render';
import { ReportsPage } from './ReportsPage';

vi.mock('../../api/reportes');
vi.mock('../../utils/notifications', () => ({ notifyError: vi.fn() }));

describe('ReportsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    obtenerReporte.mockResolvedValue({ resumen: { total: 3 }, columnas: ['ID'], filas: [['1']] });
  });

  it('al entrar genera el reporte de los últimos 30 días', async () => {
    render(<ReportsPage />);

    expect(await screen.findByText('Total')).toBeInTheDocument();
    expect(obtenerReporte).toHaveBeenCalledWith('reclamos', {
      desde: dayjs().subtract(29, 'day').format('YYYY-MM-DD'),
      hasta: dayjs().format('YYYY-MM-DD'),
    });
    expect(screen.queryByText('Seleccioná un rango de fechas para ver el reporte.')).toBeNull();
  });
});
