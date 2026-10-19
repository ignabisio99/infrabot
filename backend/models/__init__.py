"""Registro de modelos.

SQLAlchemy resuelve las relaciones por nombre ("FotoReclamo", "Reclamo", ...) recién
al configurar los mappers, así que todas las clases tienen que estar importadas antes
de la primera consulta. Y `create_all` sólo crea las tablas de las clases ya importadas:
un modelo que no pasó por acá no da error, simplemente no existe en la base.

Importarlas acá hace que alcance con `import models` desde cualquier entrypoint
(main.py, seed.py, un script suelto) en vez de que cada uno tenga que acordarse de la
lista completa. Ojo que la lista tiene que estar completa igual: TokenBlacklist, por
ejemplo, no se registra solo porque core/auth.py lo importa dentro de las funciones.
"""

from models.adjunto_presupuesto import AdjuntoPresupuesto, TipoAdjuntoPresupuesto
from models.busqueda_reclamo import BusquedaReclamo
from models.comentario_reclamo import ComentarioReclamo
from models.configuracion_atencion import ConfiguracionAtencion
from models.configuracion_auditoria import ConfiguracionAuditoria
from models.conversacion import Conversacion, EstadoConversacion
from models.conversacion_participante import ConversacionParticipante
from models.contratista import Contratista
from models.estimacion_preliminar import EstimacionPreliminar
from models.foto_reclamo import FotoReclamo
from models.historial_estado_presupuesto import HistorialEstadoPresupuesto
from models.historial_estado_reclamo import HistorialEstadoReclamo, OrigenCambioEstado
from models.indice_inflacion import IndiceInflacion
from models.notificacion import Notificacion
from models.institucion import Institucion
from models.lista_contratistas import ListaContratistas, lista_contratista_asociacion
from models.mensaje_conversacion import AutorMensaje, MensajeConversacion, TipoMensaje
from models.presupuesto import (
    EstadoPresupuesto,
    ItemPresupuesto,
    Presupuesto,
    TipoItemPresupuesto,
    VersionPresupuesto,
)
from models.reclamo import EstadoReclamo, PrioridadReclamo, Reclamo
from models.recomendacion_ia import RecomendacionIA, TipoRecomendacionIA
from models.recordatorio_contratista import RecordatorioContratista
from models.referencia_costo import ReferenciaCosto
from models.rol_mano_obra import RolManoObra
from models.solicitud_presupuesto import SolicitudPresupuesto
from models.token_blacklist import TokenBlacklist
from models.usuario import EstadoUsuario, TipoUsuario, Usuario
from models.visita import EstadoVisita, Visita

__all__ = [
    "AdjuntoPresupuesto",
    "BusquedaReclamo",
    "ComentarioReclamo",
    "ConfiguracionAtencion",
    "ConfiguracionAuditoria",
    "Conversacion",
    "ConversacionParticipante",
    "Contratista",
    "EstadoConversacion",
    "EstadoPresupuesto",
    "EstadoReclamo",
    "EstadoUsuario",
    "EstimacionPreliminar",
    "FotoReclamo",
    "HistorialEstadoPresupuesto",
    "HistorialEstadoReclamo",
    "IndiceInflacion",
    "Institucion",
    "ItemPresupuesto",
    "ListaContratistas",
    "MensajeConversacion",
    "Notificacion",
    "OrigenCambioEstado",
    "PrioridadReclamo",
    "Presupuesto",
    "Reclamo",
    "RecomendacionIA",
    "RecordatorioContratista",
    "ReferenciaCosto",
    "RolManoObra",
    "SolicitudPresupuesto",
    "TipoAdjuntoPresupuesto",
    "TipoMensaje",
    "AutorMensaje",
    "TipoItemPresupuesto",
    "TipoRecomendacionIA",
    "TipoUsuario",
    "TokenBlacklist",
    "Usuario",
    "VersionPresupuesto",
    "EstadoVisita",
    "Visita",
    "lista_contratista_asociacion",
]
