from email.message import EmailMessage
import smtplib


def ocultar_email(email_str):
    """Oculta parcialmente el correo (ej. al***@gmail.com) para proteger la privacidad."""
    if not email_str or "@" not in email_str:
        return ""
    local, dominio = email_str.split("@", 1)
    prefijo = local[:2] if len(local) >= 2 else local[:1]
    return f"{prefijo}***@{dominio}"


def enviar_codigo_email(destinatario, usuario_nombre, codigo, smtp_email, smtp_password):
    """Envía el código de recuperación de 6 dígitos por correo usando Gmail SMTP."""
    if not smtp_email or not smtp_password:
        return False, "Falta configurar SMTP_EMAIL y SMTP_PASSWORD en los Secrets de Streamlit."

    remitente = str(smtp_email).strip()
    pwd_smtp = str(smtp_password).strip().replace(" ", "")

    msg = EmailMessage()
    msg["Subject"] = f"🔥 Tu código de recuperación ({codigo}) - Cutting Tracker"
    msg["From"] = f"Cutting Tracker <{remitente}>"
    msg["To"] = destinatario
    msg.set_content(
        f"Hola {usuario_nombre},\n\n"
        f"Tu código de verificación para restablecer tu contraseña en Cutting Tracker es:\n\n"
        f"    {codigo}\n\n"
        f"Este código es válido por 10 minutos.\n"
        f"Si no solicitaste este cambio, puedes ignorar este mensaje."
    )

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
            smtp.login(remitente, pwd_smtp)
            smtp.send_message(msg)
        return True, "Código enviado con éxito."
    except Exception as e:
        return False, f"No se pudo enviar el correo: {e}"
