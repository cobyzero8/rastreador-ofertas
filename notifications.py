import os
import requests
import streamlit as st
from utils import safe_log

def enviar_alerta_telegram(tienda, nombre, precio_oferta, precio_regular, link, imagen="", tipo_alerta="NUEVO_PRODUCTO"):
    token = None
    chat_id = None
    
    # Intentar obtener credenciales desde Streamlit Secrets
    try:
        if hasattr(st, "secrets"):
            token = st.secrets.get("TELEGRAM_TOKEN")
            chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
    except Exception:
        pass

    # Intentar obtener credenciales desde Variables de Entorno (GitHub Actions)
    if not token:
        token = os.environ.get("TELEGRAM_TOKEN")
    if not chat_id:
        chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        safe_log("⚠️ Credenciales de Telegram faltantes.", "warning")
        return False

    # 🟢 AJUSTE EXCLUSIVO PARA FALABELLA: Convierte /public a Scene7 para que Telegram no rechace sendPhoto
    if imagen and "falabella" in str(imagen).lower() and "/public" in str(imagen):
        sku_id = str(imagen).replace("/public", "").split("/")[-1]
        imagen = f"https://falabella.scene7.com/is/image/FalabellaPE/{sku_id}?wid=800&hei=800"

    # Sanitizar el nombre para evitar que caracteres < o > rompan el parseo HTML de Telegram
    nombre_clean = str(nombre).replace("<", "&lt;").replace(">", "&gt;")

    # 🎯 ENCABEZADOS Y TEXTO SEGÚN EL TIPO DE EVENTO
    if tipo_alerta == "BAJA_PRECIO":
        header = "📉 <b>¡EL PRODUCTO BAJÓ DE PRECIO APROVECHA COBY!</b> 📉"
        label_precio = "💰 <b>Nuevo Precio Menor:</b>"
    else:
        header = "🆕 <b>¡NUEVO ARTÍCULO ENCONTRADO!</b> 🆕"
        label_precio = "💰 <b>Precio Encontrado:</b>"

    mensaje = (
        f"{header}\n\n"
        f"📦 <b>Producto:</b> {nombre_clean}\n"
        f"🏪 <b>Tienda:</b> {tienda}\n"
        f"{label_precio} S/. {precio_oferta:.2f}\n"
    )
    
    if precio_regular > precio_oferta:
        ahorro = precio_regular - precio_oferta
        mensaje += f"🏷️ <b>Precio Regular / Anterior:</b> <s>S/. {precio_regular:.2f}</s> (Ahorro: S/. {ahorro:.2f})\n"

    mensaje += f"\n👉 <a href='{link}'><b>¡VER EN TIENDA!</b></a>"

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
        if resp.status_code == 200:
            return True
        else:
            safe_log(f"🚨 Telegram rechazó el mensaje (HTTP {resp.status_code}): {resp.text}", "error")
            return False

    except Exception as e:
        safe_log(f"🚨 Error enviando a Telegram: {e}", "error")
        return False
            resp_photo = requests.post(url_photo, json=payload_photo, timeout=10)
            if resp_photo.status_code == 200:
                return True
            
            safe_log(
                f"⚠️ Telegram rechazó la foto de {tienda} (HTTP {resp_photo.status_code}). Reintentando como texto simple...",
                "warning"
            )
        except Exception as e_img:
            safe_log(f"⚠️ Error al enviar foto: {e_img}. Reintentando como texto simple...", "warning")

    # 🟢 INTENTO 2 / RESPALDO: Enviar solo texto HTML
    try:
        url_text = f"https://api.telegram.org/bot{token}/sendMessage"
        payload_text = {
            "chat_id": chat_id,
            "text": mensaje,
            "parse_mode": "HTML",
            "disable_web_page_preview": False
        }
        resp_text = requests.post(url_text, json=payload_text, timeout=10)
        if resp_text.status_code == 200:
            return True
        else:
            safe_log(f"🚨 Telegram rechazó el mensaje de texto (HTTP {resp_text.status_code}): {resp_text.text}", "error")
            return False

    except Exception as e_text:
        safe_log(f"🚨 Error enviando mensaje de texto a Telegram: {e_text}", "error")
        return False
