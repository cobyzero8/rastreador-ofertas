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
    time.sleep(random.uniform(2, 4))
    productos = []
    headers = {"User-Agent": random.choice(USER_AGENTS_POOL)}
    try:
        resp = requests.get(url_base, headers=headers, timeout=30)
        soup = BeautifulSoup(resp.text, 'html.parser')
        tarjetas = soup.find_all('div', class_=lambda x: x and ('product' in x or 'card' in x))
        for t in tarjetas:
            tit = t.find(['h3', 'h2', 'span', 'p'], class_=re.compile(r'(title|name)', re.I))
            if not tit: continue
            nombre = re.sub(r'(-\d+%|\d+%)', '', tit.text.strip())
            link_a = t.find('a', href=True)
            link = urljoin(url_base, link_a['href']) if link_a else url_base
            img = t.find('img', src=True)
            img_url = img['src'] if img else "https://via.placeholder.com/150"
            precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', t.text)
            valores = sorted([float(p.replace(',', '.')) for p in precios if float(p.replace(',', '.')) > 2])
            if valores:
                p_desc, p_orig = valores[0], valores[-1]
                if p_desc <= limite_precio or any(p in t.text.upper() for p in PALABRAS_COMBOS):
                    productos.append({"nombre": nombre, "p_orig": p_orig, "p_desc": p_desc, "link": link, "img": img_url})
        return productos
    except: return []

def obtener_cupón_por_tienda(tienda):
    """Busca en el archivo JSON si hay cupón para la tienda."""
    try:
        if os.path.exists(CUPONES_FILE):
            with open(CUPONES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get(tienda.upper(), [])
    except: return []
    return []

def revisar_ofertas():
    res_s = supabase.table("radares").select("*").execute()
    lineas = res_s.data if res_s.data else []
    
    for item in lineas:
        meta = item["identificador"].strip().split("-")
        tienda = meta[0].upper()
        prods = escanear_tienda(item["url"], float(item["precio_max"]), tienda, "", item["id"])
        
        # Obtenemos cupones para esta tienda
        cupones = obtener_cupón_por_tienda(tienda)
        texto_cupon = ""
        if cupones:
            c = cupones[0] # Tomamos el primero
            texto_cupon = f"\n\n🎫 *Cupón activo:* `{c['codigo']}` - {c['descuento']} ({c['detalle']})"

        for p in prods:
            ahorro = p['p_orig'] - p['p_desc']
            reporte = f"🛍️ *¡OFERTA DETECTADA!*\n🏢 *{tienda}*\n📦 {p['nombre']}\n💵 S/. {p['p_desc']:.2f}\n💰 Ahorro: S/. {ahorro:.2f}{texto_cupon}"
            enviar_telegram_con_foto_y_botones(reporte, p['link'], p['img'])
            
   # for item in lineas:
        #meta = item["identificador"].strip().split("-")
        #prods = escanear_tienda(item["url"], float(item["precio_max"]), meta[0], "", item["id"])
       # for p in prods:
          #  ahorro = p['p_orig'] - p['p_desc']
           # reporte = f"🛍️ *¡OFERTA DETECTADA!*\n🏢 *{meta[0]}*\n📦 {p['nombre']}\n💵 S/. {p['p_desc']:.2f}\n💰 Ahorro: S/. {ahorro:.2f}"
            #enviar_telegram_con_foto_y_botones(reporte, p['link'], p['img'])
            # Agrega esta función a tu scraper.py

