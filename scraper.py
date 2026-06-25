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

# [AQUÍ VA TU FUNCIÓN escanear_tienda TAL CUAL LA TENÍAS]
# (La que hace el scraping de las webs, esa no la toques)

def revisar_ofertas(filtro_objetivo="TODOS"):
    res = supabase.table("radares").select("*").execute()
    if not res.data: return "Sin radares."
    
    fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_guardados = 0
    
    for item in res.data:
        # [AQUÍ VA TU LÓGICA DE GRUPOS, NO LA BORRES]
        
        prods = escanear_tienda(item['url'], item['precio_max'])
        
        for p in prods:
            payload = {
                "identificador": item['identificador'], 
                "precio": float(p['precio']), 
                "fecha": fecha_hoy
            }
            try:
                # Guardamos directamente
                supabase.table("historial_precios").upsert(payload).execute()
                total_guardados += 1
            except Exception as e:
                print(f"Error al guardar {item['identificador']}: {e}")
                
    return f"Barrido completo. Se guardaron {total_guardados} registros nuevos."
