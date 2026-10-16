import { Paper, Text } from '@mantine/core';

import { ChangeStateModal } from '../../components/ChangeStateModal';
import { decidirPresupuesto } from '../../api/presupuestos';
import { avisarNotificacionesCambiaron } from '../../layout/NotificationBell';
import { formatearIdReclamo } from '../../utils/ids';
import { formatoMoneda } from '../../utils/formatters';
import { BudgetStatusBadge } from './BudgetStatusBadge';
import { etiquetaPorEstado, requiereMotivo, textoMotivoPorEstado } from './estados';

// Con varias ofertas por reclamo, sin esto no se sabe sobre cuál se está decidiendo.
function ResumenPresupuesto({ presupuesto }) {
  return (
    <Paper withBorder radius="sm" p="sm">
      <Text fw={600}>
        {presupuesto.contratista.nombre_empresa} · {formatoMoneda.format(Number(presupuesto.monto))}
        {presupuesto.version > 1 && ` · versión ${presupuesto.version}`}
      </Text>
      <Text size="sm" c="dimmed" truncate="end">
        {formatearIdReclamo(presupuesto.reclamo.id)} · {presupuesto.reclamo.nombre_escuela}
      </Text>
    </Paper>
  );
}

const config = {
  titulo: 'Decidir sobre el presupuesto',
  labelNuevoEstado: 'Decisión',
  etiquetaSubmit: 'Guardar decisión',
  Badge: BudgetStatusBadge,
  resumen: (presupuesto) => <ResumenPresupuesto presupuesto={presupuesto} />,
  etiquetaPorEstado,
  etiquetaPorAccion: {
    APROBADO: 'Aprobar',
    RECHAZADO: 'Rechazar',
    AJUSTES_SOLICITADOS: 'Solicitar ajustes',
  },
  requiereMotivo,
  textoMotivoPorEstado,
  descripcionMotivo: 'Queda registrado en el historial del presupuesto.',
  textoSinTransiciones: 'Ya se decidió sobre este presupuesto y no puede cambiar.',
  avisoPorEstado: {
    APROBADO:
      'El reclamo va a quedar aprobado con este presupuesto, y el resto de las ofertas ' +
      'van a quedar como no seleccionadas. No se puede deshacer.',
    RECHAZADO:
      'Esta oferta queda descartada; el contratista puede enviar otra mientras la ' +
      'convocatoria siga abierta. Si la oferta sirve pero hay que corregir algo, pedí ajustes.',
    AJUSTES_SOLICITADOS:
      'Se le avisa al contratista por WhatsApp y mail. Cuando envíe la corrección, ' +
      'la versión actual queda archivada y el presupuesto vuelve a Recibido.',
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
      onCambiado={(actualizado) => {
        // Decidir saca la versión corregida de la campanita.
        avisarNotificacionesCambiaron();
        onDecidido(actualizado);
      }}
    />
  );
}
