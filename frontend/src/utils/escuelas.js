import { normalizarTexto } from './filtros';

const EN_MINUSCULA = new Set(['de', 'del', 'la', 'las', 'los', 'el', 'y', 'e', 'en']);

// Los nombres que vienen del padrón están todos en mayúsculas; los que alguien escribió a
// mano se dejan como están.
export function capitalizarMayusculas(texto) {
  if (!texto || texto !== texto.toUpperCase()) return texto;
  return texto
    .toLowerCase()
    .split(' ')
    .map((palabra, i) =>
      i > 0 && EN_MINUSCULA.has(palabra)
        ? palabra
        : palabra.replace(/^(\P{L}*)(\p{L})/u, (_, previo, letra) => previo + letra.toUpperCase()),
    )
    .join(' ');
}

// Las siglas que usa la Provincia de Buenos Aires; de más largo a más corto para que
// "secundaria técnica" no quede como "secundaria".
const SIGLAS = [
  ['escuela de educacion secundaria tecnica', 'EEST'],
  ['escuela de educacion secundaria', 'EES'],
  ['escuela de educacion primaria', 'EP'],
];

export function nombreCortoEscuela(nombre) {
  const texto = (nombre || '').normalize('NFC').trim();
  const comparable = normalizarTexto(texto);
  for (const [prefijo, sigla] of SIGLAS) {
    if (comparable.startsWith(`${prefijo} `)) {
      return `${sigla} ${capitalizarMayusculas(texto.slice(prefijo.length).trim())}`;
    }
  }
  return capitalizarMayusculas(texto);
}
