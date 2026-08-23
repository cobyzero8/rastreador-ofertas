import os
import requests
from utils import safe_log

def obtener_secret(nombre_key):
    """
    Obtiene las credenciales priorizando Variables de Entorno (GitHub Actions)
    y utilizando Streamlit Secrets como respaldo.
    """
    valor = os.environ.get(nombre_key)
    if valor and str(valor).strip():
        return str(valor).strip()
    
    try:
        import streamlit as st
        if hasattr(st, "secrets") and nombre_key in st.secrets:
            return str(st.secrets[nombre_key]).strip()
    except Exception:
        pass

    return None


def sanitizar_imagen_para_telegram(url_imagen):
    """
    Higieniza y transforma URLs de imágenes (especialmente de Falabella)
    a formatos estándar CDN aceptados al 100% por la API de Telegram.
    """
    if not url_imagen:
        return ""

    url_clean = str(url_imagen).strip()

    # Corregir protocolos relativos si existieran
    if url_clean.startswith("//"):
        url_clean = "https:" + url_clean

    # 🛒 TRATAMIENTO ESPECIAL PARA FALABELLA
    if "falabella" in url_clean.lower():
        # Caso 1: URLs guardadas en BD tipo media.falabella.com.pe/falabellaPE/{sku_id}/public
        if "/public" in url_clean:
            partes = url_clean.replace("/public", "").split("/")
            sku_id = partes[-1] if partes else ""
            if sku_id and ("_" in sku_id or sku_id.isdigit()):
                return f"https://falabella.scene7.com/is/image/FalabellaPE/{sku_id}?wid=800&hei=800&qlt=80"

        # Caso 2: URLs de media.falabella.com
        if "media.falabella.com" in url_clean:
            clean_base = url_clean.split('?')[0].split('#')[0]
            match_id = [t for t in clean_base.split('/') if ('_' in t or t.isdigit()) and len(t) >= 5]
            if match_id:
                sku_id = match_id[-1]
                return f"https://falabella.scene7.com/is/image/FalabellaPE/{sku_id}?wid=800&hei=800&qlt=80"

        # Caso 3: Ajuste de Scene7 para resolución óptima
        if "scene7.com" in url_clean:
            base_img = url_clean.split('?')[0]
            return f"{base_img}?wid=800&hei=800&qlt=80"

        # Caso 4: Truco de sufijo para forzar detección de formato en Telegram
        if not any(url_clean.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
            return f"{url_clean}#.jpg"

    return url_clean


def enviar_alerta_telegram(tienda, nombre, precio_oferta, precio_regular, link, imagen="", tipo_alerta="NUEVO_PRODUCTO"):
    token = obtener_secret("TELEGRAM_TOKEN")
    chat_id = obtener_secret("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        safe_log("⚠️ Credenciales de Telegram faltantes (TELEGRAM_TOKEN o TELEGRAM_CHAT_ID).", "warning")
        return False

    # 🟢 Procesar e higienizar la imagen antes de enviar a Telegram
    imagen_procesada = sanitizar_imagen_para_telegram(imagen)

    # Sanitizar caracteres que puedan romper el formato HTML de Telegram
    nombre_clean = str(nombre).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

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

    # 🟢 INTENTO 1: Enviar con Foto (Usando la imagen higienizada)
    if imagen_procesada and str(imagen_procesada).startswith("http"):
        try:
            url_photo = f"https://api.telegram.org/bot{token}/sendPhoto"
            payload_photo = {
                "chat_id": chat_id,
                "photo": imagen_procesada,
                "caption": mensaje,
                "parse_mode": "HTML"
            }
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
