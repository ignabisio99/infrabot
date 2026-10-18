"""Envío de emails por SMTP: Gmail en producción, Mailpit en desarrollo."""

import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)

SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
APP_URL = os.getenv("APP_URL", "http://localhost:3000")


def enviar_email(destinatario: str, asunto: str, html: str) -> bool:
    """Envía un email. Devuelve True si fue exitoso."""
    if not SMTP_EMAIL:
        logger.warning("Email no configurado. Asunto: %s → %s", asunto, destinatario)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = f"InfraBot <{SMTP_EMAIL}>"
    msg["To"] = destinatario
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            # Gmail exige TLS y login; Mailpit, el SMTP de desarrollo, no ofrece ninguno.
            server.ehlo()
            if server.has_extn("starttls"):
                server.starttls()
                server.ehlo()
            if server.has_extn("auth"):
                server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, destinatario, msg.as_string())
        logger.info("Email enviado a %s - Asunto: %s", destinatario, asunto)
        return True
    except Exception as e:
        logger.error("Error enviando email a %s: %s", destinatario, e)
        return False


def enviar_confirmacion(destinatario: str, token: str) -> bool:
    """Envía el email de confirmación de cuenta."""
    link = f"{APP_URL}/confirmar?token={token}"
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #132a4d;">¡Bienvenido a InfraBot!</h2>
        <p>Gracias por registrarte. Para activar tu cuenta, hacé click en el siguiente botón:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{link}" 
               style="background-color: #1fa7b3; color: white; padding: 12px 30px; 
                      text-decoration: none; border-radius: 6px; font-weight: bold;">
                Confirmar mi cuenta
            </a>
        </div>
        <p style="color: #666; font-size: 13px;">
            Si no creaste esta cuenta, ignorá este mensaje.
        </p>
        <p style="color: #666; font-size: 13px;">
            Si el botón no funciona, copiá y pegá este enlace en tu navegador:<br>
            <a href="{link}">{link}</a>
        </p>
    </div>
    """
    return enviar_email(destinatario, "Confirmá tu cuenta - InfraBot", html)


def enviar_aprobacion(destinatario: str) -> bool:
    """Envía un email notificando que la cuenta fue aprobada."""
    link = APP_URL
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #132a4d;">¡Tu cuenta fue aprobada!</h2>
        <p>Un administrador revisó tu solicitud y aprobó tu cuenta en InfraBot.</p>
        <p>Ya podés iniciar sesión y comenzar a usar el sistema.</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{link}" 
               style="background-color: #1fa7b3; color: white; padding: 12px 30px; 
                      text-decoration: none; border-radius: 6px; font-weight: bold;">
                Iniciar sesión
            </a>
        </div>
    </div>
    """
    return enviar_email(destinatario, "Tu cuenta fue aprobada - InfraBot", html)


def enviar_solicitud_presupuesto(
    destinatario: str,
    reclamo_id: int,
    nombre_escuela: str,
    ubicacion: str,
    link: str,
) -> bool:
    """Notifica a un contratista que fue seleccionado para cargar un presupuesto."""
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #132a4d;">Solicitud de presupuesto</h2>
        <p>Fue seleccionado para cargar el presupuesto del <strong>reclamo #{reclamo_id}</strong>.</p>
        <div style="background:#f4f6fb; border-radius:8px; padding:16px; margin:16px 0;">
            <p style="margin:4px 0;"><strong>🏫 Escuela:</strong> {nombre_escuela}</p>
            <p style="margin:4px 0;"><strong>📍 Ubicación:</strong> {ubicacion}</p>
        </div>
        <p>Ingresá para ver el detalle y cargar tu presupuesto:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{link}"
               style="background-color: #1fa7b3; color: white; padding: 12px 30px;
                      text-decoration: none; border-radius: 6px; font-weight: bold;">
                Cargar presupuesto
            </a>
        </div>
        <p style="color: #666; font-size: 13px;">
            Si el botón no funciona, copiá y pegá este enlace en tu navegador:<br>
            <a href="{link}">{link}</a>
        </p>
    </div>
    """
    return enviar_email(destinatario, f"Solicitud de presupuesto - Reclamo #{reclamo_id}", html)


def enviar_aprobado_presupuesto(
    destinatario: str,
    reclamo_id: int,
    nombre_escuela: str,
    ubicacion: str,
    link: str,
) -> bool:
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #132a4d;">¡Presupuesto aprobado!</h2>
        <p>Tu presupuesto para el <strong>reclamo #{reclamo_id}</strong> fue aprobado.</p>
        <div style="background:#f4f6fb; border-radius:8px; padding:16px; margin:16px 0;">
            <p style="margin:4px 0;"><strong>🏫 Escuela:</strong> {nombre_escuela}</p>
            <p style="margin:4px 0;"><strong>📍 Ubicación:</strong> {ubicacion}</p>
        </div>
        <p>Para coordinar la visita de trabajo te escribimos por WhatsApp: respondé ese mensaje
        con tu disponibilidad. Si no te llegó, comunicate con la administración.</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{link}"
               style="background-color: #1fa7b3; color: white; padding: 12px 30px;
                      text-decoration: none; border-radius: 6px; font-weight: bold;">
                Ver mis presupuestos
            </a>
        </div>
        <p style="color: #666; font-size: 13px;">
            Si el botón no funciona, copiá y pegá este enlace en tu navegador:<br>
            <a href="{link}">{link}</a>
        </p>
    </div>
    """
    return enviar_email(destinatario, f"Presupuesto aprobado - Reclamo #{reclamo_id}", html)


def enviar_rechazo_presupuesto(
    destinatario: str,
    reclamo_id: int,
    nombre_escuela: str,
    motivo: str | None,
    link: str,
) -> bool:
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #132a4d;">Presupuesto rechazado</h2>
        <p>Tu presupuesto para el <strong>reclamo #{reclamo_id}</strong> ({nombre_escuela}) fue rechazado.</p>
        <div style="background:#f4f6fb; border-radius:8px; padding:16px; margin:16px 0;">
            <p style="margin:4px 0;"><strong>Motivo:</strong> {motivo or "—"}</p>
        </div>
        <p>Mientras la convocatoria siga abierta, podés enviar una nueva oferta desde el portal:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{link}"
               style="background-color: #1fa7b3; color: white; padding: 12px 30px;
                      text-decoration: none; border-radius: 6px; font-weight: bold;">
                Enviar una nueva oferta
            </a>
        </div>
        <p style="color: #666; font-size: 13px;">
            Si el botón no funciona, copiá y pegá este enlace en tu navegador:<br>
            <a href="{link}">{link}</a>
        </p>
    </div>
    """
    return enviar_email(destinatario, f"Presupuesto rechazado - Reclamo #{reclamo_id}", html)


def enviar_ajustes_presupuesto(
    destinatario: str,
    reclamo_id: int,
    nombre_escuela: str,
    ajustes: str | None,
    link: str,
) -> bool:
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #132a4d;">Ajustes solicitados</h2>
        <p>Te pidieron ajustes en tu presupuesto para el <strong>reclamo #{reclamo_id}</strong> ({nombre_escuela}).</p>
        <div style="background:#f4f6fb; border-radius:8px; padding:16px; margin:16px 0;">
            <p style="margin:4px 0;"><strong>Qué corregir:</strong> {ajustes or "—"}</p>
        </div>
        <p>Podés enviar la versión corregida desde el portal:</p>
        <div style="text-align: center; margin: 30px 0;">
            <a href="{link}"
               style="background-color: #1fa7b3; color: white; padding: 12px 30px;
                      text-decoration: none; border-radius: 6px; font-weight: bold;">
                Ajustar presupuesto
            </a>
        </div>
        <p style="color: #666; font-size: 13px;">
            Si el botón no funciona, copiá y pegá este enlace en tu navegador:<br>
            <a href="{link}">{link}</a>
        </p>
    </div>
    """
    return enviar_email(destinatario, f"Ajustes solicitados - Reclamo #{reclamo_id}", html)


def enviar_no_seleccionado_presupuesto(
    destinatario: str,
    reclamo_id: int,
    nombre_escuela: str,
) -> bool:
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #132a4d;">Presupuesto no seleccionado</h2>
        <p>Para el <strong>reclamo #{reclamo_id}</strong> ({nombre_escuela}) se eligió otra oferta,
        así que tu presupuesto no fue seleccionado.</p>
        <p style="color: #666; font-size: 13px;">
            Gracias por tu participación. Si hiciera falta, podés volver a ser convocado.
        </p>
    </div>
    """
    return enviar_email(
        destinatario, f"Presupuesto no seleccionado - Reclamo #{reclamo_id}", html
    )


def enviar_reclamo_cancelado_presupuesto(
    destinatario: str,
    reclamo_id: int,
    nombre_escuela: str,
    motivo: str | None,
) -> bool:
    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 520px; margin: 0 auto; padding: 20px;">
        <h2 style="color: #132a4d;">Reclamo cancelado</h2>
        <p>El <strong>reclamo #{reclamo_id}</strong> ({nombre_escuela}) se canceló, así que tu
        presupuesto ya no se va a evaluar.</p>
        <div style="background:#f4f6fb; border-radius:8px; padding:16px; margin:16px 0;">
            <p style="margin:4px 0;"><strong>Motivo:</strong> {motivo or "—"}</p>
        </div>
        <p style="color: #666; font-size: 13px;">Gracias por tu participación.</p>
    </div>
    """
    return enviar_email(destinatario, f"Reclamo cancelado - Reclamo #{reclamo_id}", html)
