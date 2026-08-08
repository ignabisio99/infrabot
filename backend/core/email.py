"""Envío de emails usando Gmail SMTP."""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
APP_URL = os.getenv("APP_URL", "http://localhost:3000")


def enviar_email(destinatario: str, asunto: str, html: str) -> bool:
    """Envía un email. Devuelve True si fue exitoso."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        print(f"[EMAIL] No configurado. Asunto: {asunto} → {destinatario}")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = asunto
    msg["From"] = f"InfraBot <{SMTP_EMAIL}>"
    msg["To"] = destinatario
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_EMAIL, SMTP_PASSWORD)
            server.sendmail(SMTP_EMAIL, destinatario, msg.as_string())
        return True
    except Exception as e:
        print(f"[EMAIL] Error enviando a {destinatario}: {e}")
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
