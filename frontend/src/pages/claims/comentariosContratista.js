const PREFIJO_WHATSAPP = /^\[WhatsApp — ([^\]]+)\]\s*/;

/** Lo que manda el contratista por WhatsApp (avances, estimados): va en la pestaña Avance. */
export function esComentarioContratista(comentario) {
  return PREFIJO_WHATSAPP.test(comentario.texto || '');
}

/** Empresa y texto de un comentario del contratista, sin el prefijo `[WhatsApp — ...]`. */
export function partesComentarioContratista(comentario) {
  const texto = comentario.texto || '';
  const match = PREFIJO_WHATSAPP.exec(texto);
  return {
    empresa: match ? match[1] : 'Contratista',
    texto: texto.replace(PREFIJO_WHATSAPP, '').trim(),
  };
}
