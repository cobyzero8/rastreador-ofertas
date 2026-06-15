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

# ... (Configuración Supabase y Telegram igual) ...
# [MANTÉN TUS CONFIGURACIONES DE SUPABASE Y TELEGRAM IGUALES]

def escanear_tienda(url_base, limite_precio, tienda, talla_buscada, item_id):
    productos_encontrados = []
    headers = {"User-Agent": random.choice(USER_AGENTS_POOL)}
    
    try:
        respuesta = requests.get(url_base, headers=headers, timeout=15)
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        # Buscamos las tarjetas de producto de forma más robusta
        tarjetas = soup.find_all('div', class_=lambda x: x and ('product' in x or 'item' in x or 'card' in x))

        for tarjeta in tarjetas:
            # 1. CAPTURA DE LINK DIRECTO
            a_tag = tarjeta.find('a', href=True)
            link_directo = urljoin(url_base, a_tag['href']) if a_tag else url_base
            
            # 2. LIMPIEZA DE NOMBRE (ELIMINAMOS PORCENTAJES Y BASURA)
            tit = tarjeta.find(['h3', 'h2', 'span', 'p'], class_=re.compile(r'(title|name)', re.I))
            if not tit: continue
            
            nombre_sucio = tit.text.strip()
            # Limpiamos: borramos cualquier cosa que empiece con "-" o números seguidos de %
            nombre_limpio = re.sub(r'(-\d+%|\d+%)', '', nombre_sucio).strip()
            nombre_limpio = re.sub(r'\s+', ' ', nombre_limpio)
            
            # 3. EXTRACCIÓN DE PRECIOS
            precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', tarjeta.text)
            valores = sorted([float(p.replace(',', '.')) for p in precios if float(p.replace(',', '.')) > 2])
            
            if not valores: continue
            precio_descuento, precio_original = valores[0], valores[-1]

            tiene_combo = any(palabra in tarjeta.text.upper() for palabra in PALABRAS_COMBOS)
            caida_flotante = ((precio_original - precio_descuento) / precio_original) * 100 >= 30 if precio_original > 0 else False

            if (precio_descuento <= limite_precio) or tiene_combo or caida_flotante:
                productos_encontrados.append({
                    "nombre": nombre_limpio, 
                    "precio_original": precio_original, 
                    "precio_descuento": precio_descuento, 
                    "link": link_directo, # <--- AHORA VA EL LINK ESPECÍFICO
                    "es_combo": tiene_combo
                })
        return productos_encontrados
    except: return []

# ... (El resto de la lógica de enviar_telegram y revisar_ofertas queda igual) ...
