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
    except Exception:
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
    except Exception:
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
            api_url = "https://lbel.tiendabel
