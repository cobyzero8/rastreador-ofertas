import os
import requests
from bs4 import BeautifulSoup

# ===== PON AQUÍ TUS CREDENCIALES REALES =====
TOKEN_REAL = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI" # Pon tu token completo
ID_REAL = "8019752668" # Pon tu ID real
# ============================================

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN_REAL}/sendMessage"
    payload = {
        "chat_id": ID_REAL,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        print(f"Respuesta de Telegram: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

def revisar_ofertas():
    print("Conectando con el servidor...")
    
    # Intentamos leer Adidas de forma ultra simple para el reporte
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        requests.get("https://www.adidas.pe", headers=headers, timeout=10)
        estado_web = "Conexión con Adidas establecida desde la nube. ✅"
    except:
        estado_web = "Adidas bloqueó la IP del servidor, pero el robot sigue vivo. ⚠️"

    # Forzamos el envío del mensaje para confirmar que la nube te habla
    mensaje_nube = (
        f"🚀 *¡REPORTE DESDE LA NUBE GITHUB!* 🚀\n\n"
        f"🤖 *Estado:* El robot se ejecutó correctamente en el servidor.\n"
        f"🌐 *Tienda:* {estado_web}\n\n"
        f"🔔 _Monitoreo automático activo cada mañana._"
    )
    enviar_telegram(mensaje_nube)

if __name__ == "__main__":
    revisar_ofertas()
