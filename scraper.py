import os
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime
from urllib.parse import urljoin
from supabase import create_client, Client
import urllib3
import streamlit as st

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Inicialización
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def limpiar_precio_pnp(texto_precio):
    try:
        texto = re.sub(r'[^\d.,]', '', str(texto_precio))
        if ',' in texto and '.' in texto:
            if texto.rfind('.') > texto.rfind(','): texto = texto.replace(',', '')
            else: texto = texto.replace('.', '').replace(',', '.')
        elif ',' in texto: texto = texto.replace(',', '.')
        match = re.findall(r'\d+\.\d+|\d+', texto)
        return float(match[0]) if match else 0.0
    except: return 0.0

def escanear_tienda(url, limite):
    # (Este motor se mantiene igual, tu lógica de scraping funciona)
    # [Copia y pega aquí tu lógica actual de escanear_tienda intacta]
    return [] # Solo para que el código no dé error si lo pruebas ahora

def revisar_ofertas(filtro_objetivo="TODOS"):
    print("DEBUG: Iniciando revisión...")
    res = supabase.table("radares").select("*").execute()
    if not res.data: return "Sin radares."
    
    fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in res.data:
        # Aquí va tu lógica de patrullaje
        prods = escanear_tienda(item['url'], item['precio_max'])
        
        for p in prods:
            payload = {
                "identificador": item['identificador'], 
                "precio": float(p['precio']), 
                "fecha": fecha_hoy
            }
            # INSERCIÓN BLINDADA
            try:
                response = supabase.table("historial_precios").upsert(payload).execute()
                print(f"DEBUG: Guardado exitoso: {item['identificador']}")
            except Exception as e:
                error_msg = f"ERROR DB: {e}"
                print(error_msg)
                st.error(error_msg) # Esto se verá en pantalla
    
    return "Barrido finalizado."
