import os
import re
import json
import requests
import urllib3
import urllib.parse
from utils import sanitizar_url, safe_log

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def obtener_key_natura():
    key = None
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            key = st.secrets.get("SCRAPERAPI_NATURA_KEY") or st.secrets.get("SCRAPERAPI_KEY")
    except Exception:
        pass
    if not key:
        key = os.environ.get("SCRAPERAPI_NATURA_KEY") or os.environ.get("SCRAPERAPI_KEY")
    return key.strip() if key else None

def consultar_api_intelligent_search_natura(categoria_slug, limite=500.0):
    """
    Consulta directamente el endpoint JSON de VTEX Intelligent Search de Natura.
    """
    clean_cat = categoria_slug.strip('/').replace('c/', '')
    
    # Endpoint oficial de búsqueda de VTEX Intelligent Search
    api_url = f"https://www.natura.com.pe/api/io/_v/api/intelligent-search/product_search/{clean_cat}?page=1&count=50"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.natura.com.pe/"
    }

    key = obtener_key_natura()
    if not key:
        safe_log("🛑 [NATURA] No se encontró clave de ScraperAPI.", "error")
        return []

    try:
        safe_log(f"📡 [NATURA] Consultando API de VTEX Intelligent Search...", "info")
        payload = {
            'api_key': key,
            'url': api_url,
            'country_code': 'us',
            'premium': 'true'  # 👈 Utiliza IP residencial para evitar el bloqueo 403 de VTEX
        }
        resp = requests.get('http://api.scraperapi.com', params=payload, headers=headers, timeout=25)
        
        safe_log(f"🔍 [NATURA API] HTTP Status: {resp.status_code} | Longitud: {len(resp.text)} bytes", "info")

        if resp.status_code == 200:
            data = resp.json()
            productos_raw = data.get('products', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            
            productos_map = {}
            for prod in productos_raw:
                try:
                    nombre = str(prod.get('productName') or prod.get('name') or '').strip().upper()
                    link_rel = str(prod.get('link') or prod.get('url') or '').strip()
                    if not nombre or not link_rel: continue

                    link_final = urllib.parse.urljoin("https://www.natura.com.pe", link_rel).split('?')[0]
                    p_o, p_r, img_url = 0.0, 0.0, ""

                    items = prod.get('items', [])
                    if items and isinstance(items, list) and len(items) > 0:
                        first_item = items[0]
                        images = first_item.get('images', [])
                        if images and isinstance(images, list) and len(images) > 0:
                            img_url = str(images[0].get('imageUrl') or images[0].get('url') or '')

                        sellers = first_item.get('sellers', [])
                        if sellers and isinstance(sellers, list) and len(sellers) > 0:
                            comm = sellers[0].get('commertialOffer', {}) or sellers[0].get('commercialOffer', {})
                            p_o = float(comm.get('Price') or comm.get('spotPrice') or 0.0)
                            p_r = float(comm.get('ListPrice') or p_o)

                    if p_o <= 0:
                        p_o = float(prod.get('spotPrice') or prod.get('price') or 0.0)
                        p_r = float(prod.get('listPrice') or p_o)

                    clean_name = nombre.replace("NATURA -", "").replace("NATURA", "").strip("- ")
                    nombre_final = f"NATURA - {clean_name}"

                    if 0 < p_o <= limite and link_final not in productos_map:
                        productos_map[link_final] = {
                            "nombre": nombre_final,
                            "precio": p_o,
                            "precio_regular": max(p_r, p_o),
                            "link": link_final,
                            "img": img_url
                        }
                except Exception:
                    continue

            return list(productos_map.values())
    except Exception as e:
        safe_log(f"🚨 [NATURA API Error]: {e}", "error")

    return []

def motor_natura(url, limite=999999.0, headers=None):
    """
    Motor definitivo basado en la API JSON oficial de VTEX Natura.
    """
    url_clean = sanitizar_url(url)
    parsed = urllib.parse.urlparse(url_clean)

    safe_log(f"🚀 [NATURA] Iniciando extracción directa...", "info")

    productos = consultar_api_intelligent_search_natura(parsed.path, limite)

    if productos:
        safe_log(f"✅ [NATURA] ¡Éxito! Se indexaron un total de {len(productos)} ofertas reales de la grilla.", "success")
    else:
        safe_log(f"⚠️ [NATURA] No se obtuvieron resultados de la API.", "warning")

    return productos
