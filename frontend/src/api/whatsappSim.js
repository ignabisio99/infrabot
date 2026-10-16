import { API_URL, extraerMensajeError, fetchConAuth } from './apiClient';

async function leerJson(response, mensajePorDefecto) {
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(extraerMensajeError(error?.detail, mensajePorDefecto));
  }
  return response.json();
}

export async function simularWhatsAppTexto(origen, texto) {
  const response = await fetchConAuth(`${API_URL}/whatsapp/simular`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ origen, texto }),
  });
  return leerJson(response, 'No se pudo simular el mensaje.');
}

export async function reiniciarSimuladorWhatsApp(origen) {
  const response = await fetchConAuth(`${API_URL}/whatsapp/simular/reiniciar`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ origen }),
  });
  return leerJson(response, 'No se pudo reiniciar la charla.');
}

export async function listarMensajesSim(origen, despuesDe) {
  const params = new URLSearchParams({ origen });
  if (despuesDe) params.set('despues_de', String(despuesDe));
  const response = await fetchConAuth(`${API_URL}/whatsapp/simular/mensajes?${params}`);
  return leerJson(response, 'No se pudieron cargar los mensajes del simulador.');
}

export async function simularWhatsAppMedia(origen, archivo, caption = '', proveedorStt = '') {
  const form = new FormData();
  form.append('origen', origen);
  form.append('caption', caption);
  if (proveedorStt) form.append('proveedor_stt', proveedorStt);
  form.append('archivo', archivo);
  const response = await fetchConAuth(`${API_URL}/whatsapp/simular/media`, {
    method: 'POST',
    body: form,
  });
  return leerJson(response, 'No se pudo simular el archivo.');
}
