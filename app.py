import streamlit as st
import json
import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Radar Pro - Panel Central", layout="wide")

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

# Credenciales reales de tu bot de Telegram
TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

# --- FUNCIONES NATIVAS DEL ROBOT (SCRAPER) ---
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    payload = {"chat_id": CHAT_ID_TELEGRAM, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        st.error(f"Error al enviar notificación de Telegram: {e}")

def escanear_tienda(url, limite_precio, tienda, talla_buscada):
    productos_encontrados = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        respuesta = requests.get(url, headers=headers, timeout=15)
        if respuesta.status_code != 200:
            return []
            
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        t_low = tienda.lower()
        tarjetas = []
        
        # Selectores según la tienda configurada
        if "adidas" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x) or soup.find_all('div', attrs={"data-glass-item": "product-card"})
        elif "falabella" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x) or soup.find_all('div', class_=lambda x: x and 'pod-details' in x)
        elif "marathon" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-item' in x) or soup.find_all('div', class_=lambda x: x and 'productCard' in x)
        elif "ripley" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'catalog-product' in x) or soup.find_all('a', class_='ProductCard__ProductLink')
        else:
            tarjetas = soup.find_all('div', class_=lambda x: x and ('product' in x or 'item' in x or 'card' in x))

        for tarjeta in tarjetas:
            tit = tarjeta.find(['p', 'b', 'h3', 'div', 'a'], class_=re.compile(r'(title|name|heading|pod-title)', re.I)) or tarjeta.find('p')
            prc = tarjeta.find(class_=re.compile(r'(price|sale|oferta|current)', re.I)) or tarjeta.find(lambda tag: tag.name in ['span', 'div'] and 'S/.' in tag.text)
            
            if tit and prc:
                nombre_prod = tit.text.strip().replace("\n", "").replace(",", "")
                text_precio = prc.text.strip()
                
                nums = ''.join(filter(str.isdigit, text_precio))
                if not nums:
                    continue
                    
                p_num = int(nums) / 100 if len(nums) > 4 and ("adidas" in t_low or "marathon" in t_low) else int(nums[:4]) if len(nums) > 5 else int(nums)
                
                if p_num <= limite_precio:
                    talla_check = str(talla_buscada).upper().strip()
                    if talla_check and talla_check not in ["TODAS", "N/A", ""]:
                        patron = r'\b' + re.escape(talla_check) + r'\b'
                        if not re.search(patron, tarjeta.text.upper()):
                            continue
                    
                    productos_encontrados.append({"nombre": nombre_prod, "precio": int(p_num)})
        return productos_encontrados
    except:
        return []

def ejecutar_escaneo_completo():
    if not os.path.exists(URLS_FILE):
        return False, "No tienes ningún enlace registrado en urls.txt."
        
    historial = {}
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                historial = json.load(f)
        except:
            historial = {}
            
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    with open(URLS_FILE, "r", encoding="utf-8") as f:
        lineas = [l.strip() for l in f.readlines() if l.strip() and "," in l]

    if not lineas:
        return False, "El archivo urls.txt está vacío."

    conteo
