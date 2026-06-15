import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import random
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
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

PALABRAS_COMBOS = ["GRATIS", "2X1", "3X2", "REGALO", "LLEVATE", "COMBO", "PROMOCION", "INCLUYE"]

def generar_barra_descuento(precio_orig, precio_desc):
    try:
        if precio_orig <= 0: return ""
        porcentaje = ((precio_orig - precio_desc) / precio_orig) * 100
        if porcentaje <= 0: return ""
        bloques = int(round(porcentaje / 10))
        barra = "█" * max(1, min(bloques, 10))
        return f"`[{barra.ljust(10, '░')}]` *¡{porcentaje:.0f}% Real OFF!*"
    except: return ""

def enviar_telegram_con_foto_y_botones(mensaje, url_compra, url_foto):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendPhoto"
    reply_markup = {"inline_keyboard": [[{"text": "🛒 Ir al Catálogo / Comprar", "url": url_compra}]]}
    foto_final = url_foto if url_foto and url_foto.startswith("http") else "https://images.unsplash.com/photo-1555529669-e69e7aa0ba9a?q=80&w=500"
    try: requests.post(url, json={"chat_id": CHAT_ID_TELEGRAM, "photo": foto_final, "caption": mensaje, "parse_mode": "Markdown", "reply_markup": json.dumps(reply_markup)}, timeout=10)
    except: pass

def escanear_tienda(url_base, limite_precio, tienda, talla_buscada, item_id):
    productos_encontrados = []
    headers = {
        "User-Agent": random.choice(USER_AGENTS_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }
    try:
        respuesta = requests.get(url_base, headers=headers, timeout=15)
        if respuesta.status_code != 200:
            return []
            
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        tarjetas = soup.find_all('div', class_=lambda x: x and ('product' in x or 'item' in x or 'card' in x or 'grid' in x or 'tile' in x)) or [soup]

        for tarjeta in tarjetas:
            texto_tarjeta = tarjeta.text.upper()
            
            tit = tarjeta.find(['p', 'b', 'h1', 'h2', 'h3', 'span', 'a'], class_=re.compile(r'(title|name|pod|product-name)', re.I)) or tarjeta.find('p')
            if not tit: continue
            nombre_prod = re.sub(r'\s+', ' ', tit.text.strip().replace(",", ""))
            if len(nombre_prod) < 4: continue
            
            img_tag = tarjeta.find('img', src=True)
            link_foto = urljoin(url_base, img_tag['src']) if img_tag else ""
            
            # --- LÍNEA 68 COMPLETAMENTE CORREGIDA Y PARENTESIS CERRADO ---
            precios = re.findall(r'(?:S/\.?\s*|\$\s*)(\d+[\.,]\d{2}|\d+)', tarjeta.text)
            valores = sorted(list(set([float(p.replace(',', '.')) for p in precios if float(p.replace(',', '.')) > 2])))
            
            precio_descuento = valores[0] if valores else 0.0
            precio_original = valores[-1] if valores else 0.0

            tiene_combo = any(palabra in texto_tarjeta for palabra in PALABRAS_COMBOS)
            
            if (precio_descuento > 0 and precio_descuento <= limite_precio) or tiene_combo:
                productos_encontrados.append({
                    "nombre": nombre_prod, 
                    "precio_original": precio_original if precio
