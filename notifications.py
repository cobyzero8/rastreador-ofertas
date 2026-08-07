import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
from utils import sanitizar_url

def enviar_telegram_real(mensaje, link_producto="", url_imagen=""):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return False
    link_producto = sanitizar_url(link_producto)
    url_imagen = sanitizar_url(url_imagen)
    mensaje_html = f"{mensaje}\n\n👉 <a href='{link_producto}'><b>¡COMPRAR AQUÍ!</b></a>"
    url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto" if url_imagen else f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "parse_mode": "HTML"}

    if url_imagen:
        if len(mensaje_html) > 1000:
            mensaje_html = mensaje[:850] + f"...\n\n👉 <a href='{link_producto}'><b>¡COMPRAR AQUÍ!</b></a>"
        payload["photo"], payload["caption"] = url_imagen, mensaje_html
    else:
        payload["text"] = mensaje_html

    try:
        return requests.post(url_api, json=payload, timeout=10).status_code == 200
    except Exception:
        return False
