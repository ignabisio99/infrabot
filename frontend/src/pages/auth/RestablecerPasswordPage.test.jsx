import { screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { restablecerPassword, validarLinkRestablecer } from '../../api/auth';
import { render } from '../../test/render';
import { RestablecerPasswordPage } from './RestablecerPasswordPage';

vi.mock('../../api/auth');

function abrir(url) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <RestablecerPasswordPage />
    </MemoryRouter>,
  );
}

describe('RestablecerPasswordPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('sin token avisa que el link no sirve', () => {
    abrir('/restablecer-password');

    expect(screen.getByText(/El link no es válido/)).toBeInTheDocument();
    expect(validarLinkRestablecer).not.toHaveBeenCalled();
  });

  it('con un link vencido lo dice antes de pedir la contraseña', async () => {
    validarLinkRestablecer.mockRejectedValue(new Error('El link no es válido o ya venció.'));

    abrir('/restablecer-password?token=viejo');

    expect(await screen.findByText('El link no es válido o ya venció.')).toBeInTheDocument();
    expect(screen.queryByLabelText(/Contraseña nueva/)).not.toBeInTheDocument();
  });

  it('no deja mandar dos contraseñas distintas', async () => {
    validarLinkRestablecer.mockResolvedValue({ email: 'ana@ejemplo.com' });
    const { user } = abrir('/restablecer-password?token=abc');

    await user.type(await screen.findByLabelText(/Contraseña nueva/), 'Clave123!');
    await user.type(screen.getByLabelText(/Repetí la contraseña/), 'Otra123!');
    await user.click(screen.getByRole('button', { name: 'Cambiar contraseña' }));

    expect(screen.getByText('Las contraseñas no coinciden.')).toBeInTheDocument();
    expect(restablecerPassword).not.toHaveBeenCalled();
  });

  it('cambia la contraseña con el token del link', async () => {
    validarLinkRestablecer.mockResolvedValue({ email: 'ana@ejemplo.com' });
    restablecerPassword.mockResolvedValue({ mensaje: 'ok' });
    const { user } = abrir('/restablecer-password?token=abc');

    expect(await screen.findByText(/ana@ejemplo.com/)).toBeInTheDocument();
    await user.type(screen.getByLabelText(/Contraseña nueva/), 'Clave123!');
    await user.type(screen.getByLabelText(/Repetí la contraseña/), 'Clave123!');
    await user.click(screen.getByRole('button', { name: 'Cambiar contraseña' }));

    expect(restablecerPassword).toHaveBeenCalledWith('abc', 'Clave123!');
    expect(await screen.findByText(/cambiaste tu contraseña/)).toBeInTheDocument();
  });
});
