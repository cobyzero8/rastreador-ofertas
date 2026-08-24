import os
import requests
import streamlit as st
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
        if hasattr(st, "secrets") and nombre_key in st.secrets:
            return str(st.secrets[nombre_key]).strip()
    except Exception:
        pass

    return None


def calcular_termometro_oferta(precio_oferta, precio_regular):
    """
    Calcula una barra visual de calor y el nivel de recomendación 
    según el porcentaje de descuento del producto.
    """
    if precio_regular <= 0 or precio_oferta >= precio_regular:
        return "🔴⚪⚪⚪⚪ <b>0%</b> (<i>Sin descuento</i>)"

    descuento_pct = ((precio_regular - precio_oferta) / precio_regular) * 100

    if descuento_pct < 15:
        barra = "🔴⚪⚪⚪⚪"
        texto = "Poco conveniente"
    elif descuento_pct < 30:
        barra = "🟠🟠⚪⚪⚪"
        texto = "Oferta regular"
    elif descuento_pct < 45:
        barra = "🟡🟡🟡⚪⚪"
        texto = "Buena oferta"
    elif descuento_pct < 60:
        barra = "🟢🟢🟢🟢⚪"
        texto = "¡Muy recomendable!"
    else:
        barra = "🔥🟢🟢🟢🟢"
        texto = "¡OFERTÓN IMPERDIBLE!"

    return f"{barra} <b>-{descuento_pct:.0f}%</b> (<i>{texto}</i>)"


def enviar_alerta_telegram(tienda, nombre, precio_oferta, precio_regular, link, imagen="", tipo_alerta="NUEVO_PRODUCTO"):
    token = obtener_secret("TELEGRAM_TOKEN")
    chat_id = obtener_secret("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        safe_log("⚠️ Credenciales de Telegram faltantes.", "warning")
        return False

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
        termometro = calcular_termometro_oferta(precio_oferta, precio_regular)
        mensaje += f"🏷️ <b>Precio Regular / Anterior:</b> <s>S/. {precio_regular:.2f}</s> (Ahorro: S/. {ahorro:.2f})\n"
        mensaje += f"🔥 <b>Nivel de Oferta:</b> {termometro}\n"

    mensaje += f"\n👉 <a href='{link}'><b>¡VER EN TIENDA!</b></a>"

    # 🟢 INTENTO 1: DESCARGAR IMAGEN Y SUBIR COMO ARCHIVO BINARIO (Evita bloqueos de CDN)
    if imagen and str(imagen).startswith("http"):
        try:
            url_photo = f"https://api.telegram.org/bot{token}/sendPhoto"
            headers_img = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            # Descargar bytes de la imagen
            res_img = requests.get(imagen, headers=headers_img, timeout=8)
            
            if res_img.status_code == 200 and len(res_img.content) > 1000:
                payload = {
                    "chat_id": chat_id,
                    "caption": mensaje,
                    "parse_mode": "HTML"
                }
                files = {
                    "photo": ("producto.jpg", res_img.content, "image/jpeg")
                }
                resp_photo = requests.post(url_photo, data=payload, files=files, timeout=12)
                if resp_photo.status_code == 200:
                    return True
                
                safe_log(f"⚠️ Telegram rechazó el archivo de la foto (HTTP {resp_photo.status_code}): {resp_photo.text}", "warning")
        except Exception as e_img:
            safe_log(f"⚠️ Error al descargar/subir foto de {tienda}: {e_img}. Reintentando como texto...", "warning")

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
        
