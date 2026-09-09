import { ChangeStateModal } from '../../components/ChangeStateModal';
import { decidirPresupuesto } from '../../api/presupuestos';
import { BudgetStatusBadge } from './BudgetStatusBadge';
import { etiquetaPorEstado, requiereMotivo, textoMotivoPorEstado } from './estados';

const config = {
  titulo: 'Decidir sobre el presupuesto',
  labelNuevoEstado: 'Decisión',
  etiquetaSubmit: 'Guardar decisión',
  Badge: BudgetStatusBadge,
  etiquetaPorEstado,
  requiereMotivo,
  textoMotivoPorEstado,
  descripcionMotivo: 'Queda registrado en el historial del presupuesto.',
  textoSinTransiciones: 'Ya se decidió sobre este presupuesto y no puede cambiar.',
  avisoPorEstado: {
    APROBADO:
      'El reclamo va a quedar aprobado con este presupuesto, y el resto de las ofertas ' +
      'van a quedar como no seleccionadas. No se puede deshacer.',
  },
  mensajeExito: (etiqueta) => `El presupuesto quedó "${etiqueta}".`,
};

export function DecideBudgetModal({ presupuesto, onClose, onDecidido }) {
  return (
    <ChangeStateModal
      entidad={presupuesto}
      config={config}
      onSubmit={decidirPresupuesto}
      onClose={onClose}
      onCambiado={onDecidido}
    />
  );
}
