import { ChangeStateModal } from '../../components/ChangeStateModal';
import { cambiarEstadoReclamo } from '../../api/reclamos';
import { StatusBadge } from './StatusBadge';
import { etiquetaPorEstado, requiereMotivo, textoMotivoPorEstado } from './estados';

const config = {
  titulo: 'Cambiar estado del reclamo',
  labelNuevoEstado: 'Nuevo estado',
  etiquetaSubmit: 'Cambiar estado',
  Badge: StatusBadge,
  etiquetaPorEstado,
  requiereMotivo,
  textoMotivoPorEstado,
  descripcionMotivo: 'Queda registrado en el historial del reclamo.',
  textoSinTransiciones: 'Este reclamo está en un estado final y ya no puede cambiar.',
  mensajeExito: (etiqueta) => `El reclamo pasó a "${etiqueta}".`,
  avisoPorEstado: {
    CANCELADO: ({ ofertas_en_carrera: n }) =>
      n > 0 &&
      (n === 1
        ? 'Hay 1 oferta en carrera: queda sin evaluar y le avisamos al contratista por WhatsApp y mail.'
        : `Hay ${n} ofertas en carrera: quedan sin evaluar y les avisamos a los contratistas por WhatsApp y mail.`),
  },
};

export function ChangeStatusModal({ reclamo, onClose, onEstadoCambiado }) {
  return (
    <ChangeStateModal
      entidad={reclamo}
      config={config}
      onSubmit={cambiarEstadoReclamo}
      onClose={onClose}
      onCambiado={onEstadoCambiado}
    />
  );
}
