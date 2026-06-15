import requests
from bs4 import BeautifulSoup
import re
import time
import random
import json
from datetime import datetime

# Configuración
TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"
PALABRAS_COMBOS = ["GRATIS", "2X1", "3X2", "REGALO", "LLEVATE", "COMBO"]

def escanear_tienda(url_base, limite_precio):
    time.sleep(random.uniform(2, 4)) # Camuflaje
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36"}
    
    productos = []
    try:
        resp = requests.get(url_base, headers=headers, timeout=30)
        soup = BeautifulSoup(resp.text, 'html.parser')
        tarjetas = soup.find_all('div', class_=lambda x: x and ('product' in x or 'card' in x))

        for t in tarjetas:
            # Nombre limpio
            tit = t.find(['h3', 'h2', 'span', 'p'], class_=re.compile(r'(title|name)', re.I))
            if not tit: continue
            nombre = re.sub(r'(-\d+%|\d+%)', '', tit.text.strip())
            
            # Link y Foto
            a = t.find('a', href=True)
            link = "https://www.adidas.pe" + a['href'] if a and a['href'].startswith('/') else (a['href'] if a else url_base)
            img = t.find('img', src=True)
            img_url = img['src'] if img else "https://via.placeholder.com/150"
            
            # Precio
            precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', t.text)
            valores = sorted([float(p.replace(',', '.')) for p in precios if float(p.replace(',', '.')) > 2])
            
            if valores:
                p_desc = valores[0]
                if p_desc <= limite_precio or any(p in t.text.upper() for p in PALABRAS_COMBOS):
                    productos.append({"nombre": nombre, "precio": p_desc, "link": link, "img": img_url})
        return productos
    except Exception as e:
        print(f"Error escaneando: {e}")
        return []

def revisar_ofertas():
    # 1. Obtener radares de Supabase
    # 2. Iterar por cada radar
    # 3. Llamar a escanear_tienda
    # 4. Enviar a Telegram
    print("Iniciando revisión...")
    # ... aquí va tu lógica de bucle ...
