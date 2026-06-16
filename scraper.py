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

# CONFIGURACIÓN
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_publishable_LG-EavkoMBYDSCS0xsCccQ_1062w4zq"
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
    try: requests.post(url, json=payload, timeout=10)
    except: pass

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
    except: return []

# --- REEMPLAZA DESDE AQUÍ HASTA EL FINAL DE TU ARCHIVO ---

def revisar_ofertas():
    res = supabase.table("radares").select("*").execute()
    if not res.data:
        return
    
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    for item in res.data:
        identificador = item['identificador']
        limite = float(item['precio_max'])
        
        # Rompemos el identificador para extraer la metadata real
        parts = identificador.split("-")
        tienda_txt = parts[0].upper() if len(parts) > 0 else "TIENDA"
        cat_txt = parts[1].upper() if len(parts) > 1 else "OTROS"
        # Si el scraper no saca el nombre detallado, usamos el del radar mapeado
        nombre_radar = parts[2].replace("_", " ").title() if len(parts) > 2 else "Producto"
        talla_txt = parts[3] if len(parts) > 3 else "Todas"
        
        # Truco del límite infinito para capturar precio real
        prods = escanear_tienda(item['url'], 999999.0)
        
        if prods:
            precio_actual = prods[0]['precio']
            nombre_web = prods[0]['nombre']
            
            # 1. Registro obligatorio en el historial de Supabase
            try:
                supabase.table("historial_precios").insert({
                    "identificador": identificador,
                    "precio": precio_actual,
                    "fecha": fecha_hoy
                }).execute()
            except: pass
            
            # 2. Filtro de Alerta Inteligente (Solo si bajó de tu tope)
            if precio_actual <= limite:
                # Calculamos el ahorro y porcentaje frente al tope de compra
                ahorro = limite - precio_actual
                porcentaje = (ahorro / limite) * 100 if limite > 0 else 0
                
                # Armamos un diseño premium con bloques limpios para Telegram
                msg = (
                    f"🔥 COBY *¡OFERTA DETECTADA!* 🔥\n"
                    f"━━━━━━━━━━━━━━━━━━━\n\n"
                    f"📦 *Producto:* {nombre_web}\n"
                    f"🏪 *Tienda:* `{tienda_txt}`\n"
                    f"🏷️ *Talla/Filtro:* `{talla_txt}`\n\n"
                    f"💵 *Precio Actual:* `S/. {precio_actual:.2f}`\n"
                    f"🎯 *Tu Precio Limite:* `S/. {limite:.2f}`\n"
                )
                
                # Si el precio es estrictamente menor al tope, le metemos la medalla de ahorro
                if precio_actual < limite:
                    msg += f"📉 *¡Te estás ahorrando:* S/. {ahorro:.2f} ({porcentaje:.1f}% menos)!\n"
                else:
                    msg += f"⚖️ *¡Llegó a tu precio objetivo exacto!*\n"
                    
                msg += f"\n🚨 _¡Aprovecha antes de que vuele el stock!_"
                
                enviar_telegram(msg, prods[0]['link'], prods[0]['img'])
