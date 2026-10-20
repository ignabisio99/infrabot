import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach, vi } from 'vitest';

afterEach(() => {
  cleanup();
});

// jsdom no trae estas APIs y Mantine las usa (media queries, ScrollArea, Combobox).
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: (query) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }),
});

class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.ResizeObserver = ResizeObserver;

window.HTMLElement.prototype.scrollIntoView = () => {};

// Lo usa el Textarea con `autosize`.
Object.defineProperty(document, 'fonts', {
  configurable: true,
  value: { addEventListener() {}, removeEventListener() {} },
});
