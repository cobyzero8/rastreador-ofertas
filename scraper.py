import os
import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
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

def escanear_tienda(url, limite):
    productos = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
    
    # MOTOR 1: PERFUMES (API BELCORP)
    if any(k in url for k in ["tiendabelcorp", "cyzone", "lbel", "esika"]):
        marca = "cyzone" if "cyzone" in url else "lbel" if "lbel" in url else "esika"
        api_url = f"https://{marca}.tiendabelcorp.com.pe/api/catalog_system/pub/products/search"
        params = {"ft": "perfume", "_from": 0, "_to": 20, "O": "OrderByPriceASC"}
        try:
            r = requests.get(api_url, headers=headers, params=params, timeout=10, verify=False)
            for item in r.json():
                precio = float(item["items"][0]["sellers"][0]["commertialOffer"]["Price"])
                if 0 < precio <= limite:
                    productos.append({"nombre": f"{marca.upper()} - {item['productName'].upper()}", "precio": precio, "link": item["link"]})
        except: pass

    # MOTOR 2: ZAPATILLAS, ROPA, TECNOLOGÍA (HTML)
    else:
        try:
            r = requests.get(url, headers=headers, timeout=15, verify=False)
            soup = BeautifulSoup(r.text, 'html.parser')
            # Selector universal para cualquier sitio web moderno
            for t in soup.find_all(['div', 'article', 'li'], class_=re.compile(r'(product|card|item|grid)', re.I)):
                tit = t.find(['h3', 'h2', 'a', 'span'], class_=re.compile(r'(name|title)', re.I))
                precios = re.findall(r'S/\s*(\d+[\.,]\d{2})', t.text)
                if tit and precios:
                    precio = float(precios[0].replace(',', '.'))
                    if precio <= limite:
                        a = t.find('a', href=True)
                        link = urljoin(url, a['href'])
                        productos.append({"nombre": tit.text.strip().upper(), "precio": precio, "link": link})
        except: pass
    return productos

def revisar_ofertas(cat_filtro):
    res = supabase.table("radares").select("*").execute().data
    total = 0
    for r in res:
        id_r = r['identificador'].upper()
        # Clasificación exacta
        grupo = "PERFUMES" if "PERFUME" in id_r else "ZAPATILLAS" if "ZAPATILLA" in id_r else "ROPA" if "ROPA" in id_r else "TECNOLOGIA" if "TEC" in id_r or "TV" in id_r else "OTROS"
        if cat_filtro != "TODOS" and cat_filtro != grupo: continue
        
        prods = escanear_tienda(r['url'], r['precio_max'])
        for p in prods:
            try:
                supabase.table("historial_precios").insert({"identificador": r['identificador'], "precio": p['precio'], "fecha": datetime.now().strftime("%Y-%m-%d")}).execute()
                total += 1
            except: pass
    return f"Procesados {total} productos."
