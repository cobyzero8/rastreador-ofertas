import os
import requests
import streamlit as st
from utils import safe_log

def enviar_alerta_telegram(tienda, nombre, precio_oferta, precio_regular, link, imagen=""):
    """
    Envía una alerta formateada de oferta/bug a un canal o chat de Telegram.
    """
    token = None
    chat_id = None
    
    # Lectura de credenciales prioritarias desde st.secrets o variables de entorno
    try:
        if hasattr(st, "secrets"):
            token = st.secrets.get("TELEGRAM_TOKEN")
            chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
    except Exception:
        pass

    if not token:
        token = os.environ.get("TELEGRAM_TOKEN")
    if not chat_id:
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        safe_log("⚠️ Credenciales de Telegram no configuradas. Omitiendo envío de alerta.", "warning")
        return False

    # Formateo del mensaje
    mensaje = (
        f"✨ <b>¡NUEVO PRODUCTO ENCONTRADO!</b> ✨\n\n"
        f"📦 <b>Producto:</b> {nombre}\n"
        f"🏪 <b>Tienda:</b> {tienda}\n"
        f"💰 <b>Precio Encontrado:</b> S/. {precio_oferta:.2f}\n"
    )
    
    if precio_regular > precio_oferta:
        ahorro = precio_regular - precio_oferta
        mensaje += f"📉 <b>Precio Regular:</b> <s>S/. {precio_regular:.2f}</s> (Ahorro: S/. {ahorro:.2f})\n"

    mensaje += f"\n👉 <a href='{link}'><b>¡COMPRAR AQUÍ!</b></a>"

    try:
        # Si existe URL de imagen válida se usa sendPhoto, de lo contrario sendMessage
        if imagen and str(imagen).startswith("http"):
            url_api = f"https://api.telegram.org/bot{token}/sendPhoto"
            payload = {
                "chat_id": chat_id,
                "photo": imagen,
                "caption": mensaje,
                "parse_mode": "HTML"
            }
        else:
            url_api = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": mensaje,
                "parse_mode": "HTML",
                "disable_web_page_preview": False
            }

        resp = requests.post(url_api, json=payload, timeout=12)
        if resp.status_code == 200:
            safe_log(f"🔔 Alerta de Telegram enviada para: {nombre}", "success")
            return True
        else:
            safe_log(f"⚠️ Telegram devolvió HTTP {resp.status_code}: {resp.text}", "warning")
            return False

    except Exception as e:
        safe_log(f"🚨 Error al conectar con la API de Telegram: {e}", "error")
        return False
