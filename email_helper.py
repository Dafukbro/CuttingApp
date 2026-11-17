from email.message import EmailMessage
import smtplib


def ocultar_email(email_str):
    """Oculta parcialmente el correo (ej. al***@outlook.com) para proteger la privacidad."""
    if not email_str or "@" not in email_str:
        return ""
    local, dominio = email_str.split("@", 1)
    prefijo = local[:2] if len(local) >= 2 else local[:1]
    return f"{prefijo}***@{dominio}"


def enviar_codigo_email(destinatario, usuario_nombre, codigo, smtp_email, smtp_password):
    """
    Envía el código de recuperación de 6 dígitos a cualquier correo (Gmail, Outlook, Hotmail, iCloud, etc.).
    Detecta automáticamente si la cuenta remitente (SMTP_EMAIL) es Gmail u Outlook/Hotmail.
    """
    if not smtp_email or not smtp_password:
        return False, "Falta configurar SMTP_EMAIL y SMTP_PASSWORD en los Secrets de Streamlit."

    remitente = str(smtp_email).strip()
    pwd_smtp = str(smtp_password).strip()

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

    dominio_remitente = remitente.split("@")[-1].lower() if "@" in remitente else ""

    try:
        if dominio_remitente in ("outlook.com", "hotmail.com", "live.com", "msn.com") or "office365" in dominio_remitente:
            with smtplib.SMTP("smtp.office365.com", 587, timeout=10) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.ehlo()
                smtp.login(remitente, pwd_smtp)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as smtp:
                smtp.login(remitente, pwd_smtp.replace(" ", ""))
                smtp.send_message(msg)
        return True, "Código enviado con éxito."
    except Exception as e:
        return False, f"No se pudo enviar el correo: {e}"
