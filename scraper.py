import os
import json
import requests
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from supabase import create_client, Client
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configuración (sin cambios)
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY")
try:
    import streamlit as st
    if "SUPABASE_KEY" in st.secrets: SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except: pass
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def escanear_tienda(url, limite, palabra_clave=""):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/126.0.0.0 Safari/537.36"}
    productos = []
    
    if "mifarma" in url or "inkafarma" in url:
        dom = "mifarma" if "mifarma" in url else "inkafarma"
        # Ajustamos el keyword usando la palabra clave del radar
        kw = palabra_clave.strip().replace(" ", "%20")
        api_url = f"https://www.{dom}.com.pe/api/catalog_system/pub/products/search?ft={kw}&_from=0&_to=20"
        
        try:
            resp = requests.get(api_url, headers=headers, timeout=15)
            data = resp.json()
            
            # --- DIAGNÓSTICO ---
            if not data:
                print(f"DEBUG: La API de {dom} devolvió una lista vacía para la palabra '{kw}'.")
            else:
                for item in data:
                    precio = item["items"][0]["sellers"][0]["commertialOffer"]["Price"]
                    if precio > 0:
                        productos.append({
                            "nombre": item["productName"].upper(),
                            "precio": float(precio),
                            "link": item["link"],
                            "img": item["items"][0]["images"][0]["imageUrl"]
                        })
        except Exception as e:
            print(f"Error técnico en {dom}: {e}")
            
    return productos

def revisar_ofertas(categoria_filtro="TODOS"):
    res = supabase.table("radares").select("*").execute()
    total = 0
    for item in res.data:
        # Lógica de filtrado igual a la anterior
        parts = item['identificador'].split("-")
        grupo = "CUIDADO_PERSONAL" if parts[1].upper() in ["SHAMPOO", "JABON", "CUIDADO"] else "OTROS"
        if categoria_filtro != "TODOS" and categoria_filtro != grupo: continue
        
        prods = escanear_tienda(item['url'], item['precio_max'], parts[2])
        for p in prods:
            if p['precio'] <= item['precio_max']:
                # Insertar en Historial
                supabase.table("historial_precios").insert({
                    "identificador": item['identificador'], 
                    "precio": p['precio'], 
                    "fecha": datetime.now().strftime("%Y-%m-%d")
                }).execute()
                total += 1
    return f"Éxito: Se inyectaron {total} productos."
