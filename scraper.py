import os
import json
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
from supabase import create_client, Client
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =======================================================
# INICIALIZACIÓN GLOBAL BLINDADA DE SUPABASE
# =======================================================
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

try:
    import streamlit as st
    if "SUPABASE_KEY" in st.secrets: 
        SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except: 
    pass

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    raise ValueError("Error crítico: No se encontró la SUPABASE_KEY en el entorno ni en Secrets.")

# =======================================================
# FUNCIÓN GLOBAL DE LIMPIEZA DE PRECIOS PERUANOS (BLINDADA)
# =======================================================
def limpiar_precio_pnp(texto_precio):
    if not texto_precio: 
        return 0.0
    try:
        texto = re.sub(r'[^\d.,]', '', texto_precio).strip()
        if not texto: 
            return 0.0
        
        if ',' in texto and '.' in texto:
            if texto.rfind('.') > texto.rfind(','): 
                texto = texto.replace(',', '')
            else: 
                texto = texto.replace('.', '').replace(',', '.')
        else:
            if ',' in texto and len(texto.split(',')[-1]) != 2:
                texto = texto.replace(',', '')
            elif '.' in texto and len(texto.split('.')[-1]) != 2:
                texto = texto.replace('.', '')
            elif ',' in texto: 
                texto = texto.replace(',', '.')
        
        match = re.findall(r'\d+\.\d+|\d+', texto)
        return float(match[0]) if match else 0.0
    except:
        return 0.0

# =======================================================
# NÚCLEO DE EXTRACCIÓN DE TIENDAS
# =======================================================
def escanear_tienda(url, limite):
    productos = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}
    url_low = url.lower()

    # -------------------------------------------------------
    # MOTOR 1: BELCORP (Cyzone, L'Bel, Ésika)
    # -------------------------------------------------------
    if any(k in url_low for k in ["tiendabelcorp", "cyzone", "lbel", "esika"]):
        marca = "cyzone" if "cyzone" in url_low else "lbel" if "lbel" in url_low else "esika"
        api_url = f"https://{marca}.tiendabelcorp.com.pe/api/catalog_system/pub/products/search"
        params = {"ft": "perfume", "_from": 0, "_to": 20, "O": "OrderByPriceASC"}
        try:
            resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False)
            for item in resp.json():
                item_comercial = item["items"][0]["sellers"][0]["commertialOffer"]
                precio_oferta = float(item_comercial["Price"])
                precio_regular = float(item_comercial.get("ListPrice", precio_oferta))
                if 0 < precio_oferta <= limite:
                    productos.append({
                        "nombre": f"{marca.upper()} - {item['productName'].upper()}", 
                        "precio": precio_oferta, "precio_regular": precio_regular,
                        "link": item["link"], "img": item["items"][0]["images"][0]["imageUrl"]
                    })
        except: pass

    # -------------------------------------------------------
    # MOTOR 2: CONECTA RETAIL (¡Efe y La Curacao!)
    # -------------------------------------------------------
    elif "efe.com.pe" in url_low or "lacuracao.pe" in url_low:
        tienda_tag = "EFE" if "efe.com.pe" in url_low else "CURACAO"
        try:
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                items = soup.select('.product-item') or soup.select('.product-item-info')
                
                for t in items:
                    try:
                        tit_el = t.select_one('a.product-item-link') or t.select_one('.product-item-name a')
                        if not tit_el: continue
                        nombre_prod = tit_el.text.strip().upper()
                        if len(nombre_prod) < 3: continue
                        
                        enlace_final = urljoin(url, tit_el['href'])
                        
                        oferta_el = t.select_one('[data-price-type="finalPrice"] .price') or t.select_one('.special-price .price') or t.select_one('.price-box .price')
                        regular_el = t.select_one('[data-price-type="oldPrice"] .price') or t.select_one('.old-price .price')
                        
                        if not oferta_el: continue
                        precio_oferta = limpiar_precio_pnp(oferta_el.text)
                        if not precio_oferta: continue
                        
                        precio_regular = limpiar_precio_pnp(regular_el.text) if regular_el else precio_oferta
                        if precio_regular < precio_oferta: precio_regular = precio_oferta
                        
                        img_el = t.select_one('.product-image-photo') or t.find('img')
                        img_final = ""
                        if img_el:
                            img_final = img_el.get('data-src') or img_el.get('src') or ''
                            if img_final.startswith('//'): img_final = 'https:' + img_final
                        
                        if 0 < precio_oferta <= limite:
                            productos.append({
                                "nombre": f"{tienda_tag} - {nombre_prod}",
                                "precio": precio_oferta,
                                "precio_regular": precio_regular,
                                "link": enlace_final,
                                "img": img_final
                            })
                    except: continue
        except: pass

    # -------------------------------------------------------
    # MOTOR 3: JBL (API interna)
    # -------------------------------------------------------
    elif "jbl.com.pe" in url_low:
        try:
            keyword = "barra" if "barra" in url_low else "wireless" if "wireless" in url_low else "parlante" if "parlante" in url_low else "audio"
            api_url = "https://www.jbl.com.pe/on/demandware.store/Sites-JB-PE-Site/es_PE/Search-UpdateGrid"
            params = {"q": keyword, "srule": "price-low-to-high", "sz": "24"}
            
            resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                items = soup.select('.product-tile') or soup.select('[class*="product-item"]')
                
                for t in items:
                    try:
                        tit_el = t.select_one('.pdp-link a') or t.select_one('.product-name')
                        if not tit_el: continue
                        nombre_prod = tit_el.text.strip().upper()
                        
                        reg_el = t.select_one('.price .list .value') or t.select_one('del')
                        precio_el = t.select_one('.price .sales .value') or t.select_one('.sales')
                        
                        txt_oferta = precio_el.text if precio_el else t.text
                        precio_oferta = limpiar_precio_pnp(txt_oferta)
                        if not precio_oferta: continue
                        
                        if 0 < precio_oferta < 10.0 and any(k in nombre_prod for k in ["BARRA", "TV", "PARLANTE", "CINEMA", "SOUNDBAR"]):
                            precio_oferta = precio_oferta * 1000
                            
                        precio_regular = precio_oferta
                        if reg_el:
                            precio_regular = limpiar_precio_pnp(reg_el.text)
                            if 0 < precio_regular < 10.0 and any(k in nombre_prod for k in ["BARRA", "TV", "PARLANTE", "CINEMA", "SOUNDBAR"]):
                                precio_regular = precio_regular * 1000
                        
                        if 0 < precio_oferta <= limite:
                            link_el = t.find('a', href=True)
                            enlace_final = urljoin(url, link_el['href']) if link_el else url
                            img_el = t.find('img')
                            img_final = ""
                            if img_el:
                                img_final = img_el.get('data-src') or img_el.get('src') or ''
                                if img_final.startswith('//'): img_final = 'https:' + img_final
                                
                            productos.append({
                                "nombre": f"JBL - {nombre_prod}", 
                                "precio": precio_oferta, "precio_regular": precio_regular, 
                                "link": enlace_final, "img": img_final
                            })
                    except: continue
        except: pass

    # -------------------------------------------------------
    # MOTOR 4: PLATANITOS Y TRADICIONALES
    # -------------------------------------------------------
    else:
        for pagina in range(1, 4):
            url_paginada = url
            if "platanitos.com" in url_low:
                conector = "&" if "?" in url else "?"
                url_paginada = f"{url}{conector}page={pagina}"
            try:
                resp = requests.get(url_paginada, headers=headers, timeout=15, verify=False)
                if resp.status_code not in [200, 206]: break
                soup = BeautifulSoup(resp.text, 'html.parser')
                items = soup.find_all(['div', 'article', 'li', 'a'], class_=lambda x: x and any(k in x.lower() for k in ['product', 'card', 'item', 'grid', 'element']))
                if not items: break
                
                for t in items:
                    try:
                        tit = t.find(['h3', 'h2', 'span', 'p', 'div', 'a'], class_=re.compile(r'(title|name|nombre|description)', re.I))
                        if not tit or len(tit.text.strip()) < 3: continue
                        
                        del_el = t.find(['del', 'span'], class_=re.compile(r'(regular|original|old)', re.I))
                        precios = re.
