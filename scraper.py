import os
import json
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime
from urllib.parse import urljoin
from supabase import create_client, Client
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuración
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
try:
    import streamlit as st
    if "SUPABASE_KEY" in st.secrets: SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except: pass
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def enviar_telegram(mensaje, url_compra, url_foto):
    # (Mantén tu función de Telegram aquí igual)
    pass

def escanear_tienda(url, limite, palabra_clave=""):
    productos = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

    # --- MOTOR 1: BELCORP (PERFUMES) ---
    if any(k in url for k in ["tiendabelcorp", "cyzone", "lbel", "esika"]):
        marca = "cyzone" if "cyzone" in url else "lbel" if "lbel" in url else "esika"
        api_url = f"https://{marca}.tiendabelcorp.com.pe/api/catalog_system/pub/products/search"
        params = {"ft": "perfume", "_from": 0, "_to": 20, "O": "OrderByPriceASC"}
        try:
            resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False)
            for item in resp.json():
                precio = float(item["items"][0]["sellers"][0]["commertialOffer"]["Price"])
                if 0 < precio <= limite:
                    productos.append({"nombre": f"{marca.upper()} - {item['productName'].upper()}", "precio": precio, "link": item["link"], "img": item["items"][0]["images"][0]["imageUrl"]})
        except: pass

    # --- MOTOR 2: PLAZA VEA (FUERZA BRUTA) ---
    elif "plazavea" in url:
        try:
            resp = requests.get(url, headers=headers, timeout=20)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for a in soup.find_all('a', href=re.compile(r'/p/')):
                parent = a.find_parent(['div', 'li', 'article'])
                if not parent: continue
                nombre = a.text.strip().upper()
                precio_tag = parent.find(string=re.compile(r'S/\s*\d+'))
                if nombre and precio_tag:
                    precio = float(re.sub(r'[^\d.]', '', precio_tag))
                    if precio <= limite:
                        img = parent.find('img')
                        productos.append({"nombre": nombre, "precio": precio, "link": urljoin("https://www.plazavea.com.pe", a['href']), "img": img['src'] if img else ""})
        except: pass

    # --- MOTOR 3: COMODÍN GENERAL (PLATANITOS, ETC) ---
    else:
        try:
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for t in soup.find_all(['div', 'article', 'li'], class_=lambda x: x and any(k in x.lower() for k in ['product', 'card', 'item', 'grid'])):
                tit = t.find(['h3', 'h2', 'span', 'p', 'a'], class_=re.compile(r'(title|name|nombre)', re.I))
                if not tit: continue
                precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', t.text)
                if precios:
                    precio = float(precios[0].replace(',', '.'))
                    if precio <= limite:
                        a = t.find('a', href=True)
                        img = t.find('img', src=True)
                        productos.append({"nombre": tit.text.strip().upper(), "precio": precio, "link": urljoin(url, a['href']), "img": img['src'] if img else ""})
        except: pass

    return productos

def revisar_ofertas(categoria_filtro="TODOS"):
    res = supabase.table("radares").select("*").execute()
    total = 0
    for item in res.data:
        # Lógica de mapeo a botón
        ident = item['identificador'].upper()
        grupo = "ZAPATILLAS" if "ZAPATILLA" in ident else "PERFUMES" if "PERFUME" in ident else "CUIDADO_PERSONAL" if "SHAMPOO" in ident or "CUIDADO" in ident else "OTROS"
        if categoria_filtro != "TODOS" and categoria_filtro != grupo: continue
        
        prods = escanear_tienda(item['url'], item['precio_max'])
        for p in prods:
            try:
                supabase.table("historial_precios").insert({"identificador": item['identificador'], "precio": p['precio'], "fecha": datetime.now().strftime("%Y-%m-%d")}).execute()
                total += 1
            except: pass
    return f"Se procesaron {total} productos."
