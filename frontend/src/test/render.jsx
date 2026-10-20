import { render as rtlRender } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MantineProvider } from '@mantine/core';

// env="test" apaga transiciones y portales de Mantine: los modales y los dropdowns
// aparecen al instante y dentro del contenedor del test.
function Providers({ children }) {
  return <MantineProvider env="test">{children}</MantineProvider>;
}

export function render(ui) {
  const user = userEvent.setup();
  const resultado = rtlRender(ui, { wrapper: Providers });
  return { user, ...resultado };
}
