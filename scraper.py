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

# ... (Configuración de Supabase y Telegram igual) ...
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_publishable_LG-EavkoMBYDSCS0xsCccQ_1062w4zq"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
HISTORIAL_FILE = "historial_precios.json"
TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

def escanear_tienda(url_base, limite_precio, tienda, talla_buscada, item_id):
    time.sleep(random.uniform(2, 4))
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"}
    
    try:
        respuesta = requests.get(url_base, headers=headers, timeout=20)
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        
        # AJUSTE CRÍTICO: Buscamos contenedores específicos de productos
        # Casi todas las tiendas usan clases como 'product-card', 'item', 'product-tile'
        tarjetas = soup.find_all('div', class_=lambda x: x and ('product' in x or 'card' in x or 'tile' in x))
        
        productos = []
        for t in tarjetas:
            # 1. Nombre Limpio
            tit = t.find(['h3', 'h2', 'span', 'p'], class_=re.compile(r'(title|name)', re.I))
            if not tit: continue
            nombre = re.sub(r'(-\d+%|\d+%)', '', tit.text).strip()
            
            # 2. Imagen Específica (Buscamos la etiqueta img dentro de la tarjeta)
            img = t.find('img', src=True)
            url_img = img['src'] if img else "https://via.placeholder.com/150"
            
            # 3. Link Directo
            a = t.find('a', href=True)
            link = urljoin(url_base, a['href']) if a else url_base
            
            # 4. Precios
            precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', t.text)
            valores = sorted([float(p.replace(',', '.')) for p in precios if float(p.replace(',', '.')) > 2])
            
            if valores:
                p_desc = valores[0]
                if p_desc <= limite_precio:
                    productos.append({"nombre": nombre, "precio": p_desc, "link": link, "img": url_img})
                    
        return productos
    except: return []

def revisar_ofertas():
    # ... (Lógica de revisión que llama a escanear_tienda) ...
    # Asegúrate de usar p['nombre'], p['link'], p['img'] al enviar a Telegram
    pass
