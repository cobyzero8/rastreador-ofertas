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

# --- CONFIGURACIÓN ---
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY")
try:
    import streamlit as st
    if "SUPABASE_KEY" in st.secrets: SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except: pass
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def escanear_tienda(url, limite, palabra_clave=""):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36"}
    productos = []
    url_clean = str(url).strip().lower()

    # --- MODO 1: API (Búsqueda Directa) ---
    if "catalog_system" in url_clean:
        try:
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            items = resp.json()
            for item in items:
                precio = float(item["items"][0]["sellers"][0]["commertialOffer"]["Price"])
                productos.append({"nombre": item["productName"].upper(), "precio": precio, "link": item["link"], "img": item["items"][0]["images"][0]["imageUrl"]})
        except: pass

    # --- MODO 2: WEB (Navegación Visual) ---
    else:
        try:
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            soup = BeautifulSoup(resp.text, 'html.parser')
            # Busca todos los contenedores de producto estándar
            for t in soup.find_all(['div', 'li', 'article'], class_=lambda x: x and any(k in x.lower() for k in ['product', 'card', 'item'])):
                tit = t.find(['h3', 'h2', 'span', 'p'], class_=re.compile(r'(title|name|nombre)', re.I))
                if not tit: continue
                precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', t.text)
                if precios:
                    precio = float(precios[0].replace(',', '.'))
                    a = t.find('a', href=True)
                    img = t.find('img', src=True)
                    productos.append({"nombre": tit.text.strip().upper(), "precio": precio, "link": urljoin(url, a['href']), "img": img['src'] if img else ""})
        except Exception as e:
            print(f"Error en escaneo web: {e}")

    return productos

def revisar_ofertas(categoria_filtro="TODOS"):
    res = supabase.table("radares").select("*").execute()
    if not res or not res.data: return "Sin radares."
    
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    filtro_web = str(categoria_filtro).upper().strip()
    total_procesados = 0
    
    for item in res.data:
        identificador = str(item['identificador']).strip()
        limite = float(item['precio_max'])
        parts = identificador.split("-")
        cat_txt = parts[1].upper().strip()
        
        # Mapeo al botón
        grupo_sistema = "OTROS"
        if any(k in cat_txt for k in ["ZAPATILLA", "RUNNING"]): grupo_sistema = "ZAPATILLAS"
        elif any(k in cat_txt for k in ["PERFUME"]): grupo_sistema = "PERFUMES"
        elif any(k in cat_txt for k in ["SHAMPOO", "CUIDADO"]): grupo_sistema = "CUIDADO_PERSONAL"

        if filtro_web != "TODOS" and filtro_web != grupo_sistema: continue

        prods = escanear_tienda(item['url'], limite, parts[2])
        
        for p in prods:
            if p['precio'] <= limite:
                nombre_limpio = str(p['nombre']).upper().replace(" ", "_")
                id_reg = f"{parts[0]}-{cat_txt}-{nombre_limpio}-{parts[3]}"
                
                try:
                    supabase.table("historial_precios").insert({"identificador": id_reg, "precio": p['precio'], "fecha": fecha_hoy}).execute()
                    total_procesados += 1
                except: pass
                    
    return f"Procesados {total_procesados} productos."
