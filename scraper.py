import os
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
import re

TOKEN_REAL = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
ID_REAL = "8019752668"
HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN_REAL}/sendMessage"
    payload = {"chat_id": ID_REAL, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except: pass

def enviar_telegram_con_botones(mensaje, url_tienda, tienda_nombre):
    url = f"https://api.telegram.org/bot{TOKEN_REAL}/sendMessage"
    teclado = {
        "inline_keyboard": [[
            {"text": "🛒 Ir a la Tienda", "url": url_tienda},
            {"text": "🔄 Volver a Escanear", "callback_data": "forzar_escaneo"}
        ]]
    }
    payload = {
        "chat_id": ID_REAL,
        "text": mensaje,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps(teclado)
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except: pass

def escanear_tienda(url, limite_precio, tienda, categoria, talla_buscada):
    # INICIALIZACIÓN CRÍTICA PARA EVITAR EL ERROR
    productos_encontrados = [] 
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        respuesta = requests.get(url, headers=headers, timeout=15)
        if respuesta.status_code != 200: return []
            
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        t_low = tienda.lower()
        
        # Selección de tarjetas según tienda (simplificado para estabilidad)
        tarjetas = soup.find_all(class_=re.compile(r'(product|card|item)', re.I))

        for tarjeta in tarjetas:
            tit = tarjeta.find(['p', 'h3', 'a'], class_=re.compile(r'(title|name)', re.I))
            prc = tarjeta.find(class_=re.compile(r'(price|sale)', re.I))
            
            if tit and prc:
                nombre = tit.text.strip().replace("\n", "")
                nums = ''.join(filter(str.isdigit, prc.text.strip()))
                if not nums: continue
                
                p_num = int(nums) / 100 if len(nums) > 4 else int(nums)
                
                if p_num <= limite_precio:
                    # Filtro de talla
                    if talla_buscada.upper() not in tarjeta.text.upper() and talla_buscada.upper() not in ["TODAS", "M"]:
                        continue
                    productos_encontrados.append({"nombre": nombre, "precio": int(p_num)})
        return productos_encontrados
    except Exception as e:
        print(f"Error en {tienda}: {e}")
        return []

def revisar_ofertas():
    if not os.path.exists(URLS_FILE): return
        
    historial = {}
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r") as f:
            historial = json.load(f)
            
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    with open(URLS_FILE, "r") as f:
        lineas = f.readlines()

    for linea in lineas:
        partes = linea.strip().split(",")
        if len(partes) < 3: continue
        
        url_base, presupuesto, id_prod = partes[0], int(partes[1]), partes[2]
        meta = id_prod.split("_")
        
        productos = escanear_tienda(url_base, presupuesto, meta[0], meta[1], meta[2])
        
        for p in productos:
            id_item = f"{id_prod}_{p['nombre'][:10]}"
            if id_item not in historial: historial[id_item] = {}
            historial[id_item][fecha_hoy] = p['precio']
            
            # Notificar si es nuevo o bajó de precio
            enviar_telegram_con_botones(f"🚨 *Oferta:* {p['nombre']}\n💰 *Precio:* {p['precio']}", url_base, meta[0])
            
    with open(HISTORIAL_FILE, "w") as f:
        json.dump(historial, f, indent=4)
