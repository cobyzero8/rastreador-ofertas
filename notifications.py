import os
import requests
import streamlit as st
from utils import safe_log

def enviar_alerta_telegram(tienda, nombre, precio_oferta, precio_regular, link, imagen=""):
    token = None
    chat_id = None
    
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
        safe_log("⚠️ Credenciales de Telegram faltantes.", "warning")
        return False

    mensaje = (
        f"✨ <b>¡OFERTA DETECTADA!</b> ✨\n\n"
        f"📦 <b>Producto:</b> {nombre}\n"
        f"🏪 <b>Tienda:</b> {tienda}\n"
        f"💰 <b>Precio Encontrado:</b> S/. {precio_oferta:.2f}\n"
    )
    
    if precio_regular > precio_oferta:
        ahorro = precio_regular - precio_oferta
        mensaje += f"📉 <b>Precio Anterior / Regular:</b> <s>S/. {precio_regular:.2f}</s> (Ahorro: S/. {ahorro:.2f})\n"

    mensaje += f"\n👉 <a href='{link}'><b>¡VER OFERTA AQUÍ!</b></a>"

    try:
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
        return resp.status_code == 200

    except Exception as e:
        safe_log(f"🚨 Error enviando a Telegram: {e}", "error")
        return False
