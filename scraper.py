import os
import json
import requests
from bs4 import BeautifulSoup
import re
import time
import random
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse
from supabase import create_client, Client
import urllib3
import streamlit as st

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURACIÓN ---
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", st.secrets.get("SUPABASE_KEY"))
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", st.secrets.get("TELEGRAM_TOKEN"))
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", st.secrets.get("TELEGRAM_CHAT_ID"))

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

LISTA_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
]

def limpiar_precio_pnp(texto_precio):
    if not texto_precio: return 0.0
    try:
        texto = re.sub(r'[^\d.,]', '', texto_precio).strip()
        if not texto: return 0.0
        if ',' in texto and '.' in texto:
            if texto.rfind('.') > texto.rfind(','): texto = texto.replace(',', '')
            else: texto = texto.replace('.', '').replace(',', '.')
        else:
            if ',' in texto and len(texto.split(',')[-1]) != 2: texto = texto.replace(',', '')
            elif '.' in texto and len(texto.split('.')[-1]) != 2: texto = texto.replace('.', '')
            elif ',' in texto: texto = texto.replace(',', '.')
        match = re.findall(r'\d+\.\d+|\d+', texto)
        return float(match[0]) if match else 0.0
    except: return 0.0

def safe_float(val):
    if val is None: return 0.0
    if isinstance(val, (int, float)): return float(val)
    return limpiar_precio_pnp(str(val))

def enviar_telegram_real(mensaje, link_producto="", url_imagen=""):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return False
    mensaje_html = f"{mensaje}\n\n👉 <a href='{link_producto}'><b>¡COMPRAR AQUÍ!</b></a>"
    url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto" if url_imagen else f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "parse_mode": "HTML"}
    if url_imagen: payload["photo"], payload["caption"] = url_imagen, mensaje_html
    else: payload["text"] = mensaje_html
    try: return requests.post(url_api, json=payload, timeout=10).status_code == 200
    except: return False

def escanear_tienda(url, limite):
    productos = []
    headers = {"User-Agent": random.choice(LISTA_USER_AGENTS), "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8", "Accept-Language": "es-ES,es;q=0.9"}
    dominio = urlparse(url).netloc.lower()

    if "adidas" in dominio:
        try:
            texto_html = ""
            for intento in range(1, 4):
                try:
                    from curl_cffi import requests as crequests
                    resp = crequests.get(url, impersonate="chrome120", timeout=15)
                    texto_html = resp.text
                    if resp.status_code == 200: break
                except: pass
                time.sleep(2)
            
            soup = BeautifulSoup(texto_html, 'html.parser')
            next_script = soup.find('script', id='__NEXT_DATA__')
            
            # --- LÓGICA DE EXTRACCIÓN Y CORRECCIÓN MATEMÁTICA ---
            if next_script:
                json_data = json.loads(next_script.text)
                # (Lógica para buscar productos en json_data omitida por brevedad, usa la que tenías)
                # IMPORTANTE: Aquí aplicamos el ratio de corrección:
                # if p_o > 100 and (p_o / 100) <= limite: p_o = p_o / 100
                # if p_r > (p_o * 10): p_r = p_r / 100
                pass
            # (Seguir con el resto de los motores de búsqueda de otras tiendas...)
    return productos

def revisar_ofertas(filtro_objetivo="TODOS"):
    # (Mantener tu lógica actual de revisión y Supabase)
    return "Barrido completado."
