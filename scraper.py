import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import random
from urllib.parse import urljoin

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"
CUPONES_FILE = "cupones.json"
TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

USER_AGENTS_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1"
]

def generar_barra_descuento(precio_orig, precio_desc):
    try:
        if precio_orig <= 0: return ""
        porcentaje = ((precio_orig - precio_desc) / precio_orig) * 100
        if porcentaje <= 0: return ""
        bloques_llenos = int(round(porcentaje / 10))
        bloques_llenos = max(1, min(bloques_llenos, 10))
        bloques_vacios = 10 - bloques_llenos
        barra = "█" * bloques_llenos + "░" * bloques_vacios
        return f"`[{barra}]` *¡Ahorro del {porcentaje:.0f}%!*"
    except:
        return ""

def enviar_telegram_con_foto_y_botones(mensaje, url_compra, categoria, url_foto, id_radar):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendPhoto"
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🛒 Ir a Comprar / Ver Oferta", "url": url_compra},
                {"text": f"📂 Ver #{categoria.upper()}", "callback_data": f"filter_{categoria}"}
            ],
            [
                {"text": "🔕 Pausar este Radar", "callback_data": f"pausar_{id_radar}"}
            ]
        ]
    }
    foto_final = url_foto if url_foto and url_foto.startswith("http") else "https://images.unsplash.com/photo-1555529669-e69e7aa0ba9a?q=80&w=500"
    payload = {
        "chat_id": CHAT_ID_TELEGRAM, 
        "photo": foto_final,
        "caption": mensaje, 
        "parse_mode": "Markdown",
        "reply_markup": json.dumps(reply_markup)
    }
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def escanear_tienda(url_base, limite_precio, tienda, talla_buscada):
    productos_encontrados = []
    headers = {
        "User-Agent": random.choice(USER_AGENTS_POOL),
        "Accept-Language": "es-PE,es;q=0.9",
        "Referer": "https://www.google.com/"
    }
    try:
        respuesta = requests.get(url_base, headers=headers, timeout=12)
        if respuesta.status_code != 200: return []
            
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        t_low = tienda.lower()
        tarjetas = []
        
        if "vea" in t_low or "tottus" in t_low or "metro" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and ('product' in x or 'Item' in x or 'card' in x)) or soup.find_all('a', class_=lambda x: x and 'product' in x)
        elif "latam" in t_low or "sky" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and ('flight' in x or 'fare' in x or 'item' in x or 'sc-' in x))
        elif "adidas" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x)
        elif "falabella" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x) or soup.find_all('div', class_=lambda x: x and 'pod-details' in x)
        else:
            tarjetas = soup.find_all('div', class_=lambda x: x and ('product' in x or 'item' in x or 'card' in x))

        if not tarjetas: tarjetas = [soup]

        for tarjeta in tarjetas:
            tit = tarjeta.find(['p', 'b', 'h1', 'h2', 'h3', 'span', 'div', 'a'], class_=re.compile(r'(title|name|heading|pod-title|productName|flight-title|destination)', re.I)) or tarjeta.find('p')
            if not tit: continue
                
            nombre_prod = tit.text.strip().replace("\n", "").replace(",", "")
            nombre_prod_lower = nombre_prod.lower()
            if len(nombre_prod) < 4 or nombre_prod_lower in ["brand", "marca", "ver producto"]: continue
            nombre_prod = re.sub(r'\s+', ' ', nombre_prod).strip()

            img_tag = tarjeta.find('img', src=True) or tarjeta.find('img', attrs={"data-src": True})
            link_foto = ""
            if img_tag:
                link_foto = img_tag.get('data-src') or img_tag.get('src', '')
                link_foto = urljoin(url_base, link_foto)

            pct_tag = tarjeta.find(text=re.compile(r'-\d+%\s*|%\s*OFF', re.I))
            porcentaje_txt = "N/A"
            if pct_tag:
                match_pct = re.search(r'(-\d+%|\d+%)', pct_tag.text if hasattr(pct_tag, 'text') else str(pct_tag))
                if match_pct: porcentaje_txt = match_pct.group(1)

            texto_tarjeta = tarjeta.text
            precios_encontrados = re.findall(r'(?:S/\.?\s*|\$\s*)(\d+[\.,]\d{2}|\d+)', texto_tarjeta)
            
            valores_limpios = []
            for p_str in precios_encontrados:
                p_limpio = p_str.replace(',', '.')
                try:
                    val = float(p_limpio)
                    if val > 2 and val not in valores_limpios: valores_limpios.append(val)
                except: continue

            if not valores_limpios: continue
            valores_limpios = sorted(valores_limpios)
            precio_descuento = valores_limpios[0]
            precio_original = valores_limpios[-1] if len(valores_limpios) > 1 else precio_descuento

            link_tag = tarjeta.find('a', href=True) or (tarjeta if tarjeta.name == 'a' and tarjeta.has_attr('href') else None)
            link_articulo = url_base
            if link_tag and link_tag['href']: link_articulo = urljoin(url_base, link_tag['href'])

            talla_check = str(talla_buscada).upper().strip()
            if talla_check and talla_check not in ["TODAS", "N/A", ""]:
                patron = r'\b' + re.escape(talla_check) + r'\b'
                if not re.search(patron, tarjeta.text.upper()): continue

            if precio_descuento <= limite_precio:
                productos_encontrados.append({
                    "nombre": nombre_prod, "precio_original": precio_original,
                    "precio_descuento": precio_descuento, "porcentaje": porcentaje_txt,
                    "link": link_articulo, "foto": link_foto
                })
        return productos_encontrados
    except: return []

# --- NUEVO SUB-MOTOR: RECOLECTOR DE CUPONES AUTOMÁTICO EN ESPAÑOL ---
def simular_rastreo_cupones_global():
    # Banco inteligente de cupones activos
