import { em } from '@mantine/core';
import { useMediaQuery } from '@mantine/hooks';

// Mismo corte que usan los layouts (AppLayout, PortalLayout) para el menú hamburguesa.
export function useEsMobile() {
  return useMediaQuery(`(max-width: ${em(767)})`);
}
