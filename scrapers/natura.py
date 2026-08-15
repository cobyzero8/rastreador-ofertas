import os
import re
import json
import requests
import urllib3
import urllib.parse
from bs4 import BeautifulSoup
from urllib.parse import urljoin
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
    texto = str(texto).replace('&nbsp;', ' ').replace('\xa0', ' ').replace('S/.', '').replace('S/', '').replace('PEN', '').replace('S', '').strip()
    match = re.search(r'\d+(?:[.,]\d+)*', texto)
    if match:
        raw = match.group(0)
        if ',' in raw and '.' in raw:
            raw = raw.replace(',', '')
        elif ',' in raw and len(raw.split(',')[-1]) == 2:
            raw = raw.replace(',', '.')
        else:
            raw = raw.replace(',', '')
        try: return float(raw)
        except ValueError: return 0.0
    return 0.0

def normalizar_url_imagen(url_raw):
    if not url_raw or 'data:image' in str(url_raw).lower():
        return ""

    url_clean = str(url_raw).replace('\\/', '/').replace('&amp;', '&').strip()
    if ',' in url_clean:
        url_clean = url_clean.split(',')[0].strip().split(' ')[0]
    elif ' ' in url_clean.strip():
        url_clean = url_clean.split(' ')[0]

    if url_clean.startswith('//'):
        url_clean = 'https:' + url_clean
    elif url_clean.startswith('/'):
        if 'Sites-natura-pe-storefront-catalog' in url_clean or 'dw/image' in url_clean:
            url_clean = 'https://production.na01.natura.com' + url_clean
        else:
            url_clean = urljoin("https://www.natura.com.pe", url_clean)
    elif not url_clean.startswith('http'):
        url_clean = 'https://' + url_clean

    return url_clean

def procesar_producto_acumulativo(productos_map, link_final, nombre, p_o, p_r, img_url, limite):
    if not link_final or p_o <= 0 or p_o > limite:
        return

    nombre_clean = str(nombre).strip().upper()
    if nombre_clean.startswith("NATURA -"):
        nombre_clean = nombre_clean[8:].strip()
    elif nombre_clean.startswith("NATURA"):
        nombre_clean = nombre_clean[6:].strip()
    nombre_clean = nombre_clean.lstrip('-').strip()

    if not nombre_clean or len(nombre_clean) < 3 or nombre_clean in ['COMPRAR', 'VER MÁS', 'AGREGAR', 'AGREGAR A MI BOLSA']:
        return

    nombre_final = f"NATURA - {nombre_clean}"
    img_clean = normalizar_url_imagen(img_url)

    if link_final in productos_map:
        if not productos_map[link_final]["img"] and img_clean:
            productos_map[link_final]["img"] = img_clean
        if len(nombre_final) > len(productos_map[link_final]["nombre"]):
            productos_map[link_final]["nombre"] = nombre_final
        if productos_map[link_final]["precio"] <= 0 and p_o > 0:
            productos_map[link_final]["precio"] = p_o
            productos_map[link_final]["precio_regular"] = max(p_r, p_o)
    else:
        productos_map[link_final] = {
            "nombre": nombre_final,
            "precio": p_o,
            "precio_regular": max(p_r, p_o),
            "link": link_final,
            "img": img_clean
        }

def consultar_intelligent_search_api(cat_path, productos_map, limite):
    """
    Consulta la API VTEX Intelligent Search nativa de Natura Perú
    """
    clean_slug = cat_path.strip('/').replace('c/', '')
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://www.natura.com.pe/"
    }

    endpoints = [
        f"https://www.natura.com.pe/api/io/_v/api/intelligent-search/product_search/{clean_slug}?page=1&count=48",
        f"https://www.natura.com.pe/api/io/_v/api/intelligent-search/product_search?query={urllib.parse.quote(clean_slug.replace('-', ' '))}&page=1&count=48",
        f"https://www.natura.com.pe/api/catalog_system/pub/products/search/{clean_slug}?_from=0&_to=49"
    ]

    for api_url in endpoints:
        try:
            resp = requests.get(api_url, headers=headers, timeout=10, verify=False)
            if resp.status_code == 200:
                data = resp.json()
                items_list = data.get('products', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
                
                if items_list and isinstance(items_list, list):
                    for prod in items_list:
                        try:
                            raw_name = str(prod.get('productName') or prod.get('name') or '').strip()
                            link_rel = str(prod.get('link') or prod.get('url') or prod.get('linkText') or '').strip()
                            if not raw_name or not link_rel: continue

                            link_final = urljoin("https://www.natura.com.pe", link_rel).split('?')[0]
                            items = prod.get('items', [])
                            p_o, p_r, img_url = 0.0, 0.0, ""

                            if items and isinstance(items, list):
                                first_item = items[0]
                                imgs = first_item.get('images', [])
                                if imgs and isinstance(imgs, list) and len(imgs) > 0:
                                    img_url = imgs[0].get('imageUrl') or imgs[0].get('url') or ''

                                sellers = first_item.get('sellers', [])
                                if sellers and isinstance(sellers, list) and len(sellers) > 0:
                                    comm = sellers[0].get('commertialOffer', {}) or sellers[0].get('commercialOffer', {})
                                    p_o = float(comm.get('Price') or comm.get('spotPrice') or 0.0)
                                    p_r = float(comm.get('ListPrice') or p_o)

                            if p_o <= 0:
                                p_o = float(prod.get('spotPrice') or prod.get('price') or 0.0)
                                p_r = float(prod.get('listPrice') or p_o)

                            procesar_producto_acumulativo(productos_map, link_final, raw_name, p_o, p_r, img_url, limite)
                        except Exception:
                            continue

                    if len(productos_map) >= 12:
                        break
        except Exception:
            continue

def motor_natura(url, limite=999999.0, headers=None):
    """
    Motor extractor de productos para Natura Perú
    """
    productos_map = {}
    url_base = sanitizar_url(url)
    parsed = urllib.parse.urlparse(url_base)

    safe_log(f"🚀 [NATURA] Consultando API de Intelligent Search...", "info")

    # 1. Extracción desde la API de VTEX Intelligent Search
    consultar_intelligent_search_api(parsed.path, productos_map, limite)

    # 2. Respaldo HTML si la API responde vacía
    if not productos_map:
        safe_log("⚠️ [NATURA] Intentando extracción mediante escaneo HTML...", "warning")
        try:
            resp = requests.get(url_base, headers={"User-Agent": "Mozilla/5.0"}, timeout=10, verify=False)
            if resp.status_code == 200 and resp.text:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for a_tag in soup.find_all('a', href=lambda h: h and '/p/' in str(h).lower()):
                    href = a_tag['href'].strip()
                    link_final = urljoin("https://www.natura.com.pe", href).split('?')[0]
                    card = a_tag.find_parent(['div', 'article']) or a_tag
                    
                    texto = card.get_text(separator=' ', strip=True)
                    precios = [limpiar_precio_natura(p) for p in re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto) if limpiar_precio_natura(p) > 0]
                    if precios:
                        p_o = sorted(list(set(precios)))[0]
                        p_r = sorted(list(set(precios)))[-1]
                        
                        img_el = card.find('img')
                        nombre = img_el.get('alt', '').strip() if img_el and img_el.get('alt') else a_tag.get_text(strip=True)
                        img_src = img_el.get('src', '') if img_el else ''

                        procesar_producto_acumulativo(productos_map, link_final, nombre, p_o, p_r, img_src, limite)
        except Exception:
            pass

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [NATURA] ¡Éxito! Se indexaron un total de {len(productos_finales)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
