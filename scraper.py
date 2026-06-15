import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import random  # Para el Paso A: Rotación aleatoria
from urllib.parse import urljoin

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"
TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

# --- PASO A: BANCO DE IDENTIDADES (USER-AGENTS) PARA EVITAR BLOQUEOS ---
USER_AGENTS_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"
]

def enviar_telegram_con_foto_y_botones(mensaje, url_compra, categoria, url_foto, id_radar):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendPhoto"
    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🛒 Ir a Comprar Oferta", "url": url_compra},
                {"text": f"📦 Ver #{categoria.upper()}", "callback_data": f"filter_{categoria}"}
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
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def escanear_tienda(url_base, limite_precio, tienda, talla_buscada):
    productos_encontrados = []
    
    # --- PASO A: ROTACIÓN EN CADA VISITA ---
    headers = {
        "User-Agent": random.choice(USER_AGENTS_POOL),
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Referer": "https://www.google.com/"
    }
    
    # --- PASO C: TIMEOUT STRICTO Y MANEJO DE ERRORES SILENCIOSO ---
    try:
        respuesta = requests.get(url_base, headers=headers, timeout=12) # Si demora más de 12s se corta solo
        if respuesta.status_code != 200: 
            return [] # Retorna vacío sin colapsar el programa
            
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        t_low = tienda.lower()
        tarjetas = []
        
        if "adidas" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x) or soup.find_all('div', attrs={"data-glass-item": "product-card"})
        elif "falabella" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x) or soup.find_all('div', class_=lambda x: x and 'pod-details' in x)
        elif "marathon" in t_low or "triathlon" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and ('product-item' in x or 'productCard' in x or 'item' in x or 'vtex' in x))
        elif "ripley" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'catalog-product' in x) or soup.find_all('a', class_='ProductCard__ProductLink')
        else:
            tarjetas = soup.find_all('div', class_=lambda x: x and ('product' in x or 'item' in x or 'card' in x))

        if not tarjetas: 
            tarjetas = [soup]

        for tarjeta in tarjetas:
            tit = tarjeta.find(['p', 'b', 'h1', 'h2', 'h3', 'div', 'a'], class_=re.compile(r'(title|name|heading|pod-title|productName|item__title|product-name)', re.I)) or tarjeta.find('p')
            if not tit: 
                continue
                
            nombre_prod = tit.text.strip().replace("\n", "").replace(",", "")
            
            # --- PASO B: FILTRADO ANTIBASURA ESTRICTO ---
            # Si el texto está vacío, es muy corto o contiene palabras sueltas del sistema, lo salta
            nombre_prod_lower = nombre_prod.lower()
            if len(nombre_prod) < 4: 
                continue
            if nombre_prod_lower in ["brand", "marca", "ver producto", "agregar al carrito", "talla"]: 
                continue
            # Limpia espacios dobles raros creados por el HTML de la tienda
            nombre_prod = re.sub(r'\s+', ' ', nombre_prod).strip()

            img_tag = tarjeta.find('img', src=True) or tarjeta.find('img', attrs={"data-src": True})
            link_foto = ""
            if img_tag:
                link_foto = img_tag.get('data-src') or img_tag.get('src', '')
                link_foto = urljoin(url_base, link_foto)

            pct_tag = tarjeta.find(text=re.compile(r'-\d+%\s*|%\s*OFF', re.I)) or tarjeta.find(class_=re.compile(r'(discount|porcentaje|badge|pct)', re.I))
            porcentaje_txt = "N/A"
            if pct_tag:
                match_pct = re.search(r'(-\d+%|\d+%)', pct_tag.text if hasattr(pct_tag, 'text') else str(pct_tag))
                if match_pct: 
                    porcentaje_txt = match_pct.group(1)

            texto_tarjeta = tarjeta.text
            precios_encontrados = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', texto_tarjeta)
            
            valores_limpios = []
            for p_str in precios_encontrados:
                p_limpio = p_str.replace(',', '.')
                try:
                    val = float(p_limpio)
                    # Filtramos montos ridículos o cuotas que confunden el precio final
                    if val > 5 and val not in valores_limpios: 
                        valores_limpios.append(val)
                except: 
                    continue

            if not valores_limpios: 
                continue
            valores_limpios = sorted(valores_limpios)
            precio_descuento = valores_limpios[0]
            precio_original = valores_limpios[-1] if len(valores_limpios) > 1 else precio_descuento

            link_tag = tarjeta.find('a', href=True) or (tarjeta if tarjeta.name == 'a' and tarjeta.has_attr('href') else None)
            link_articulo = url_base
            if link_tag and link_tag['href']: 
                link_articulo = urljoin(url_base, link_tag['href'])

            talla_check = str(talla_buscada).upper().strip()
            if talla_check and talla_check not in ["TODAS", "N/A", ""]:
                patron = r'\b' + re.escape(talla_check) + r'\b'
                if not re.search(patron, tarjeta.text.upper()): 
                    continue

            if precio_descuento <= limite_precio:
                productos_encontrados.append({
