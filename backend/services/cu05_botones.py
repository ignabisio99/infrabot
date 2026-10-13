"""IDs de los botones interactivos del seguimiento de obra (CU-05).

Centralizados para que los schedulers (que envían las preguntas) y el handler de WhatsApp
(que interpreta las respuestas) usen exactamente los mismos identificadores. Los títulos
van en el envío; acá solo los IDs, que son lo que vuelve en el button_reply.
"""

# Pieza 1: ¿pudiste empezar el trabajo? (en el horario pactado)
INICIO_SI = "cu05_inicio_si"
INICIO_NO = "cu05_inicio_no"

# Pieza 2: ¿terminaste el trabajo?
TERMINO_SI = "cu05_termino_si"
TERMINO_NO = "cu05_termino_no"

# Pieza 3: ¿quedó resuelto? (a la escuela)
RESUELTO_SI = "cu05_resuelto_si"
RESUELTO_NO = "cu05_resuelto_no"

TODOS = frozenset(
    {INICIO_SI, INICIO_NO, TERMINO_SI, TERMINO_NO, RESUELTO_SI, RESUELTO_NO}
)
