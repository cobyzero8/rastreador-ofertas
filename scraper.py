import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import random
import time
from urllib.parse import urljoin
from supabase import create_client, Client

SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_publishable_LG-EavkoMBYDSCS0xsCccQ_1062w4zq"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HISTORIAL_FILE = "historial_precios.json"
CUPONES_FILE = "cupones.json"
TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

USER_AGENTS_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
]
PALABRAS_COMBOS = ["GRATIS", "2X1", "3X2", "REGALO", "LLEVATE", "COMBO", "PROMOCION", "INCLUYE"]

def generar_barra_descuento(precio_orig, precio_desc):
    try:
        porcentaje = ((precio_orig - precio_desc) / precio_orig) * 100
        bloques = int(round(porcentaje / 10))
        return f"`[{('█'*bloques).ljust(10, '░')}]` *{porcentaje:.0f}% OFF*"
    except: return ""

def enviar_telegram_con_foto_y_botones(mensaje, url_compra, url_foto):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendPhoto"
    reply_markup = {"inline_keyboard": [[{"text": "🛒 Ir al Producto", "url": url_compra}]]}
    try: 
        requests.post(url, json={"chat_id": CHAT_ID_TELEGRAM, "photo": url_foto, "caption": mensaje, "parse_mode": "Markdown", "reply_markup": json.dumps(reply_markup)}, timeout=10)
    except: pass

def escanear_tienda(url_base, limite_precio, tienda, talla_buscada, item_id):
    time.sleep(random.uniform(1.5, 3.0))
    productos_encontrados = []
    headers = {"User-Agent": random.choice(USER_AGENTS_POOL)}
    try:
        respuesta = requests.get(url_base, headers=headers, timeout=15)
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        tarjetas = soup.find_all('div', class_=lambda x: x and ('product' in x or 'item' in x or 'card' in x))
        for tarjeta in tarjetas:
            tit = tarjeta.find(['h3', 'h2', 'span', 'p'], class_=re.compile(r'(title|name)', re.I))
            if not tit: continue
            nombre = re.sub(r'(-\d+%|\d+%)', '', tit.text.strip())
            link_a = tarjeta.find('a', href=True)
            link = urljoin(url_base, link_a['href']) if link_a else url_base
            precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', tarjeta.text)
            valores = sorted([float(p.replace(',', '.')) for p in precios if float(p.replace(',', '.')) > 2])
            if not valores: continue
            p_desc, p_orig = valores[0], valores[-1]
            tiene_combo = any(palabra in tarjeta.text.upper() for palabra in PALABRAS_COMBOS)
            if (p_desc <= limite_precio) or tiene_combo or ((p_orig - p_desc) / p_orig >= 0.3):
                productos_encontrados.append({"nombre": nombre, "p_orig": p_orig, "p_desc": p_desc, "link": link, "es_combo": tiene_combo})
        return productos_encontrados
    except: return []

def revisar_ofertas():
    try:
        res_s = supabase.table("radares").select("*").execute()
        lineas = res_s.data if res_s.data else []
    except: return
    
    historial = {}
    if os.path.exists(HISTORIAL_FILE):
        try: 
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f: historial = json.load(f)
        except: pass

    for item in lineas:
        meta = item["identificador"].strip().split("-")
        productos = escanear_tienda(item["url"], float(item["precio_max"]), meta[0], "", item["id"])
        
        for p in productos:
            ahorro = p['p_orig'] - p['p_desc']
            barra = generar_barra_descuento(p['p_orig'], p['p_desc'])
            header = "🎁 *¡ALERTA COMBO!*" if p['es_combo'] else "🛍️ *¡OFERTA DETECTADA!*"
            
            reporte = f"{header}\n🏢 *{meta[0]}*\n📦 {p['nombre']}\n💵 S/. {p['p_desc']:.2f}\n💰 Ahorro: S/. {ahorro:.2f}\n{barra}"
            enviar_telegram_con_foto_y_botones(reporte, p['link'], "https://images.unsplash.com/photo-1555529669-e69e7aa0ba9a?q=80&w=500")
            
    with open(HISTORIAL_FILE, "w", encoding="utf-8") as f: json.dump(historial, f, indent=4)
