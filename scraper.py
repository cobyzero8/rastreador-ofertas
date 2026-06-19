import os
import json
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs
from supabase import create_client, Client

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURACIÓN DE ÉLITE MULTI-ENTORNO ---
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY")
if not SUPABASE_KEY:
    try:
        import streamlit as st
        SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    except:
        pass

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

def enviar_telegram(mensaje, url_compra, url_foto):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID_TELEGRAM,
        "photo": url_foto if url_foto else "https://via.placeholder.com/150",
        "caption": mensaje,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps({"inline_keyboard": [[{"text": "🛒 Comprar Aquí", "url": url_compra}]]})
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def escanear_tienda(url, limite):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9"
    }
    productos = []
    url_clean = str(url).strip().lower()

    # =========================================================
    # 🕵️‍♂️ TIENDAS BELCORP (CYZONE, LBEL, ESIKA) - CONTROL TOTAL
    # =========================================================
    if "tiendabelcorp" in url_clean or "cyzone" in url_clean or "lbel" in url_clean or "esika" in url_clean:
        marca = "cyzone" if "cyzone" in url_clean else "lbel" if "lbel" in url_clean else "esika"
        
        if "cyzone" in marca:
            api_url = "https://cyzone.tiendabelcorp.com.pe/api/catalog_system/pub/products/search"
        elif "lbel" in marca:
            api_url = "https://lbel.tiendabelcorp.com.pe/api/catalog_system/pub/products/search"
        else:
            api_url = "https://esika.tiendabelcorp.com.pe/api/catalog_system/pub/products/search"

        params = {
            "ft": "perfume",
            "_from": 0,
            "_to": 20,
            "O": "OrderByPriceASC"
        }
        
        try:
            resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False)
            if resp.status_code == 200:
                items = resp.json()
                for item in items:
                    nombre = item.get("productName", "Perfume Belcorp")
                    link_completo = item.get("link", url)
                    
                    img_url = ""
                    items_internos = item.get("items", [])
                    if items_internos and items_internos[0].get("images"):
                        img_url = items_internos[0]["images"][0].get("imageUrl", "")
                    
                    precio = 999.0
                    if items_internos and items_internos[0].get("sellers"):
                        comm_offer = items_internos[0]["sellers"][0].get("commertialOffer", {})
                        precio = float(comm_offer.get("Price", 999.0))
                    
                    productos.append({
                        "nombre": f"{marca.upper()} - {nombre.upper()}",
                        "precio": precio,
                        "link": link_completo,
                        "img": img_url
                    })
        except:
            pass

    # =========================================================
    # 👟 COMODÍN GENERAL
    # =========================================================
    else:
        try:
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for t in soup.find_all('div', class_=lambda x: x and ('product' in x or 'card' in x)):
                tit = t.find(['h3', 'h2', 'span', 'p'], class_=re.compile(r'(title|name)', re.I))
                if not tit: continue
                nombre = tit.text.strip()
                a = t.find('a', href=True)
                link = urljoin(url, a['href']) if a else url
                img = t.find('img', src=True)
                img_url = img
