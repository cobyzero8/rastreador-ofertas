import os
import requests
from bs4 import BeautifulSoup
import time
import json

# ===== TUS CREDENCIALES DE TELEGRAM =====
TOKEN_REAL = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI" # Tu token completo
ID_REAL = "8019752668" # Tu ID real

HISTORIAL_FILE = "historial_precios.json"

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN_REAL}/sendMessage"
    payload = {
        "chat_id": ID_REAL,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error al enviar a Telegram: {e}")

def cargar_historial():
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}

def guardar_historial(historial):
    try:
        with open(HISTORIAL_FILE, "w") as f:
            json.dump(historial, f, indent=4)
    except Exception as e:
        print(f"Error al guardar historial: {e}")

def escanear_seccion(url, limite_precio, nombre_seccion):
    print(f"🕵️‍♂️ Analizando: {nombre_seccion}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    productos_encontrados = []
    
    try:
        url_pasarela = f"https://api.allorigins.win/get?url={requests.utils.quote(url)}"
        respuesta = requests.get(url_pasarela, timeout=15)
        
        if respuesta.status_code == 200:
            html_puro = respuesta.json().get('contents', '')
            soup = BeautifulSoup(html_puro, 'html.parser')
            
            if "adidas" in url:
                tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x)
                for tarjeta in tarjetas:
                    titulo_reg = tarjeta.find(class_=lambda x: x and 'title' in x)
                    precio_reg = tarjeta.find(class_=lambda x: x and 'price' in x)
                    
                    if titulo_reg and precio_reg:
                        nombre = titulo_reg.text.strip()
                        precio_texto = precio_reg.text.strip()
                        numeros = ''.join(filter(str.isdigit, precio_texto))
                        if numeros:
                            precio_num = int(numeros)
                            if precio_num <= limite_precio:
                                productos_encontrados.append({"nombre": nombre, "precio": precio_num, "texto": precio_texto})
                                
        return productos_encontrados
    except Exception as e:
        print(f"Error en {nombre_seccion}: {e}")
        return []

def revisar_ofertas():
    print("🚀 Iniciando rastreador con memoria histórica...")
    
    if not os.path.exists("urls.txt"):
        print("Error: No existe urls.txt")
        return

    historial = cargar_historial()
    alertas_baja_precio = ""
    hubo_baja = False
    
    with open("urls.txt", "r", encoding="utf-8") as f:
        lineas = f.readlines()

    for linea in lineas:
        linea = linea.strip()
        if not linea or "," not in linea:
            continue
            
        partes = linea.split(",")
        url = partes[0].strip()
        presupuesto_max = int(partes[1].strip())
        nombre_seccion = partes[2].strip()
        
        productos = escanear_seccion(url, presupuesto_max, nombre_seccion)
        
        for p in productos:
            id_producto = f"{nombre_seccion}_{p['nombre']}"
            precio_actual = p['precio']
            
            if id_producto in historial:
                precio_anterior = historial[id_producto]
                
                # Alerta si detecta que el precio bajó en comparación a la última revisión
                if precio_actual < precio_anterior:
                    hubo_baja = True
                    alertas_baja_precio += (
                        f"📉 *¡BAJÓ DE PRECIO INMEDIATO!* 📉\n"
                        f"📦 *Producto:* {p['nombre']}\n"
                        f"💰 *Antes:* S/. {precio_anterior} ➡️ *Ahora:* {p['texto']}\n"
                        f"🏷️ *Sección:* {nombre_seccion}\n"
                        f"🔗 [Ir a la Oferta]({url})\n\n"
                    )
            
            historial[id_producto] = precio_actual
        
        time.sleep(4) # Pausa de seguridad
    
    guardar_historial(historial)
    
    if hubo_baja:
        enviar_telegram(alertas_baja_precio)
    else:
        print("El robot terminó. No se detectaron caídas de precio en esta revisión.")

if __name__ == "__main__":
    revisar_ofertas()
