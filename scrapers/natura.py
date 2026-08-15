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

def limpiar_precio_natura(texto):
    if not texto: return 0.0
    texto = str(texto).replace('&nbsp;', ' ').replace('\xa0', ' ').replace('S/.', '').replace('S/', '').strip()
    match = re.search(r'\d+(?:[.,]\d+)*', texto)
    if match:
        raw = match.group(0).replace(',', '.') if ',' in match.group(0) and '.' not in match.group(0) else match.group(0).replace(',', '')
        try: return float(raw)
        except ValueError: return 0.0
    return 0.0

def consultar_vtex_api_natura(categoria_path, de=0, hasta=49):
    """
    Consulta la API interna de catálogo de VTEX Natura directamente en formato JSON.
    """
    clean_path = categoria_path.strip('/').replace('c/', '')
    api_url = f"https://www.natura.com.pe/api/catalog_system/pub/products/search/{clean_path}?_from={de}&_to={hasta}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.natura.com.pe/"
    }

    try:
        resp = requests.get(api_url, headers=headers, timeout=12, verify=False)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        safe_log(f"⚠️ [NATURA API] Falló conexión directa API: {e}", "warning")

    # Respaldo vía ScraperAPI si hay bloqueo de red
    key = obtener_key_natura()
    if key:
        try:
            payload = {'api_key': key, 'url': api_url, 'country_code': 'us'}
            resp_sc = requests.get('http://api.scraperapi.com', params=payload, timeout=25)
            if resp_sc.status_code == 200:
                return resp_sc.json()
        except Exception:
            pass
    return []

def motor_natura(url, limite=999999.0, headers=None):
    """
    Motor extractor de productos para Natura Perú vía VTEX API + Respaldo HTML
    """
    productos_map = {}
    url_clean = sanitizar_url(url)
    parsed_url = urllib.parse.urlparse(url_clean)
    cat_path = parsed_url.path

    safe_log(f"🚀 [NATURA] Consultando API de catálogo para: {cat_path}...", "info")

    # Consultar hasta 100 productos en 2 lotes de API
    for offset in [(0, 49), (50, 99)]:
        data_json = consultar_vtex_api_natura(cat_path, de=offset[0], hasta=offset[1])
        if not data_json or not isinstance(data_json, list):
            break

        for prod in data_json:
            try:
                raw_name = str(prod.get('productName') or prod.get('brand') or '').strip().upper()
                link_rel = prod.get('link') or ''
                if not raw_name or not link_rel: continue

                link_final = urllib.parse.urljoin("https://www.natura.com.pe", link_rel).split('?')[0]

                # Extraer Precios
                p_o, p_r = 0.0, 0.0
                items = prod.get('items', [])
                img_url = ""

                if items and isinstance(items, list):
                    first_item = items[0]
                    # Imagen
                    images = first_item.get('images', [])
                    if images and isinstance(images, list):
                        img_url = images[0].get('imageUrl', '')

                    # Vendedores y Precios
                    sellers = first_item.get('sellers', [])
                    if sellers and isinstance(sellers, list):
                        comm = sellers[0].get('commertialOffer', {}) or sellers[0].get('commercialOffer', {})
                        p_o = float(comm.get('Price') or comm.get('spotPrice') or 0.0)
                        p_r = float(comm.get('ListPrice') or p_o)

                # Nombre higienizado
                clean_name = raw_name.replace("NATURA -", "").replace("NATURA", "").strip("- ")
                nombre_final = f"NATURA - {clean_name}"

                if 0 < p_o <= limite:
                    productos_map[link_final] = {
                        "nombre": nombre_final,
                        "precio": p_o,
                        "precio_regular": max(p_r, p_o),
                        "link": link_final,
                        "img": img_url
                    }
            except Exception:
                continue

        if len(data_json) < 50:
            break

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [NATURA] ¡Éxito! Se indexaron {len(productos_finales)} ofertas vía API.", "success")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
