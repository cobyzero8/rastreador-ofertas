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
    
    try:
        resp = requests.get(url, headers=headers, timeout=20, verify=False)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # Este selector es universal para Mifarma y tiendas similares
        items = soup.find_all('div', class_=lambda x: x and ('product-item' in x or 'vtex-search-result' in x or 'product-card' in x))
        
        for item in items:
            # Captura Nombre
            tit = item.find(['h3', 'a', 'div'], class_=re.compile(r'(name|title|product-item__name)', re.I))
            if not tit: continue
            nombre = tit.text.strip().upper()
            
            # Captura Precio
            precio_tag = item.find('span', class_=re.compile(r'(price|best-price)', re.I))
            if not precio_tag: continue
            
            precios = re.findall(r'(\d+[\.,]\d{2})', precio_tag.text.replace(',', '.'))
            if precios:
                precio = float(precios[0])
                # Captura Link e Imagen
                a_tag = item.find('a', href=True)
                link = urljoin(url, a_tag['href']) if a_tag else url
                img_tag = item.find('img', src=True)
                img = img_tag['src'] if img_tag else ""
                
                productos.append({"nombre": nombre, "precio": precio, "link": link, "img": img})
                
    except Exception as e:
        print(f"Error de escaneo: {e}")

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
