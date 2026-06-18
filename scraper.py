import os
import json
import requests
from bs4 import BeautifulSoup
import re
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from supabase import create_client, Client

# --- CONFIGURACIÓN DE ÉLITE ---
# RECUERDA: Cambiar esta clave por tu "service_role" secreta en GitHub para saltar el bloqueo RLS de Supabase
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_secret_UNSyaeXMv0nHZT4Ipih0-g__t6fxuJc" 

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

def enviar_telegram(mensaje, url_compra, url_foto):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID_TELEGRAM,
        "photo": url_foto if url_foto else "https://via.placeholder.com/150",
        "caption": mensaje,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps({"inline_keyboard": [[{"text": "🛒 Comprar Aquí", "url": url_compra}]]})
    }
    try: 
        requests.post(url, json=payload, timeout=10)
    except: 
        pass

def escanear_tienda(url, limite):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36"}
        resp = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(resp.text, 'html.parser')
        productos = []
        for t in soup.find_all('div', class_=lambda x: x and ('product' in x or 'card' in x)):
            tit = t.find(['h3', 'h2', 'span', 'p'], class_=re.compile(r'(title|name)', re.I))
            if not tit: continue
            nombre = tit.text.strip()
            a = t.find('a', href=True)
            link = urljoin(url, a['href']) if a else url
            img = t.find('img', src=True)
            img_url = img['src'] if img else ""
            precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', t.text)
            valores = sorted([float(p.replace(',', '.')) for p in precios if float(p.replace(',', '.')) > 2])
            if valores:
                productos.append({"nombre": nombre, "precio": valores[0], "link": link, "img": img_url})
        return productos
    except: 
        return []

# --- MOTOR DE REVISIÓN Y ENVIOS OPTIMIZADO ---
def revisar_ofertas():
    res = supabase.table("radares").select("*").execute()
    if not res.data:
        return
    
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    for item in res.data:
        identificador = item['identificador']
        limite = float(item['precio_max'])
        
        # 1. Extraemos la metadata del identificador ANTES del bucle de mensajes
        parts = identificador.split("-")
        tienda_txt = parts[0].upper() if len(parts) > 0 else "TIENDA"
        cat_txt = parts[1].upper() if len(parts) > 1 else "OTROS"
        talla_txt = parts[3] if len(parts) > 3 else "Todas"
        
        # 2. Escaneamos la tienda capturando los productos reales con límite infinito
        prods = escanear_tienda(item['url'], 999999.0)
        
        if prods:
            # Tomamos el primer precio encontrado para guardarlo en tu historial básico
            precio_actual = prods[0]['precio']
            
            # Registro obligatorio en el historial de Supabase
            try:
                supabase.table("historial_precios").insert({
                    "identificador": identificador,
                    "precio": precio_actual,
                    "fecha": fecha_hoy
                }).execute()
            except: 
                pass
            
            # 3. Recorremos los productos para verificar si alguno bajó de tu precio límite
            for p in prods:
                if p['precio'] <= limite:
                    # Calculamos el ahorro y el porcentaje de descuento
                    ahorro = limite - p['precio']
                    porcentaje = (ahorro / limite) * 100 if limite > 0 else 0
                    
                    # Estructura limpia y premium para Telegram
                    msg = (
                        f"🔥 *¡OFERTA DETECTADA POR COBY!* 🔥\n"
                        f"━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📦 *Producto:* {p['nombre']}\n"
                        f"🏪 *Tienda:* `{tienda_txt}`\n"
                        f"🏷️ *Talla/Filtro:* `{talla_txt}`\n\n"
                        f"💵 *Precio Actual:* `S/. {p['precio']:.2f}`\n"
                        f"🎯 *Tu Precio Límite:* `S/. {limite:.2f}`\n"
                    )
                    
                    if p['precio'] < limite:
                        msg += f"📉 *¡Te estás ahorrando:* S/. {ahorro:.2f} ({porcentaje:.1f}% menos)!\n"
                    else:
                        msg += f"⚖️ *¡Llegó a tu precio objetivo exacto!*\n"
                        
                    msg += f"\n🚨 _¡Aprovecha antes de que vuele el stock!_"
                    
                    # Envío seguro al bot de Telegram
                    enviar_telegram(msg, p['link'], p['img'])
                    
