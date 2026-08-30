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
