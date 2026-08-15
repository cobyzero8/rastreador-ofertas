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

def consultar_via_scraperapi(url_destino, render_js=False):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json, text/html, */*",
        "Referer": "https://www.natura.com.pe/"
    }

    key = obtener_key_natura()
    if not key:
        safe_log("🛑 [NATURA] No se encontró clave de ScraperAPI.", "error")
        return None

    try:
        payload = {
            'api_key': key,
            'url': url_destino,
            'country_code': 'us',
            'render': 'true' if render_js else 'false'
        }
        timeout_val = 60 if render_js else 25
        resp = requests.get('http://api.scraperapi.com', params=payload, headers=headers, timeout=timeout_val)
        if resp.status_code == 200 and len(resp.text) > 100:
            return resp.text
    except Exception as e:
        safe_log(f"🚨 [NATURA] Error en ScraperAPI ({url_destino}): {e}", "error")

    return None

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
    elif url_clean.startswith('http'):
        pass
    else:
        path_clean = url_clean.lstrip('/')
        if 'Sites-natura-pe-storefront-catalog' in path_clean or 'dw/image' in path_clean:
            url_clean = 'https://production.na01.natura.com/' + path_clean
        else:
            url_clean = urljoin("https://www.natura.com.pe", path_clean)

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

def extraer_desde_api_vtex(cat_slug, productos_map, limite):
    """
    Consulta los endpoints REST / Intelligent Search de VTEX Natura en JSON.
    """
    clean = cat_slug.strip('/').replace('c/', '')
    endpoints = [
        f"https://www.natura.com.pe/api/io/_v/api/intelligent-search/product_search/{clean}?page=1&count=50",
        f"https://www.natura.com.pe/api/catalog_system/pub/products/search/{clean}?_from=0&_to=49",
        f"https://www.natura.com.pe/api/catalog_system/pub/products/search/{clean.replace('-', '/')}?_from=0&_to=49",
        f"https://www.natura.com.pe/api/catalog_system/pub/products/search?ft={urllib.parse.quote(clean.replace('-', ' '))}&_from=0&_to=49"
    ]

    for api_url in endpoints:
        safe_log(f"📡 [NATURA API] Consultando API VTEX...", "info")
        res_text = consultar_via_scraperapi(api_url, render_js=False)
        if not res_text or len(res_text) < 50:
            continue

        try:
            data = json.loads(res_text)
            items = data.get('products', []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
            
            if items and isinstance(items, list) and len(items) > 0:
                for prod in items:
                    try:
                        raw_name = str(prod.get('productName') or prod.get('name') or prod.get('brand') or '').strip()
                        link_rel = str(prod.get('link') or prod.get('url') or prod.get('linkText') or '').strip()
                        if not raw_name or not link_rel: continue

                        link_final = urljoin("https://www.natura.com.pe", link_rel).split('?')[0]
                        p_o, p_r, img_url = 0.0, 0.0, ""

                        prod_items = prod.get('items', [])
                        if prod_items and isinstance(prod_items, list) and len(prod_items) > 0:
                            first_item = prod_items[0]
                            imgs = first_item.get('images', [])
                            if imgs and isinstance(imgs, list) and len(imgs) > 0:
                                img_url = str(imgs[0].get('imageUrl') or imgs[0].get('url') or '')

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

                if len(productos_map) >= 15:
                    safe_log(f"✅ [NATURA API] Se obtuvieron {len(productos_map)} productos directamente vía API.", "success")
                    return True
        except Exception:
            continue

    return False

def motor_natura(url, limite=999999.0, headers=None):
    """
    Motor híbrido: API VTEX -> Respaldo HTML con Renderizado JS.
    """
    productos_map = {}
    url_base = sanitizar_url(url)
    parsed = urllib.parse.urlparse(url_base)

    safe_log(f"🚀 [NATURA] Iniciando escaneo de grilla completa...", "info")

    # 1. Intentar API VTEX nativa (rápida y sin renderizado JS)
    exito_api = extraer_desde_api_vtex(parsed.path, productos_map, limite)

    # 2. Respaldo: Renderizado JS completo para cargar div.flex-1.flex-wrap (plp-products-grid)
    if not exito_api or len(productos_map) < 15:
        safe_log("🛡️ [NATURA] Ejecutando escáner con renderizado JS para capturar la grilla completa...", "warning")
        url_target = f"{url_base}?pageSize=48" if 'pageSize' not in url_base else url_base
        html_js = consultar_via_scraperapi(url_target, render_js=True)

        if html_js:
            soup = BeautifulSoup(html_js, 'html.parser')
            # Buscar explícitamente las tarjetas dentro de la grilla principal
            articulos = soup.find_all(['article', 'div'], attrs={'data-testid': re.compile(r'product-card', re.I)}) or \
                        soup.find_all(['article', 'div'], attrs={'id': 'product-card'})

            if not articulos:
                articulos = soup.find_all('a', href=lambda h: h and '/p/' in str(h).lower())

            for art in articulos:
                try:
                    a_tag = art if art.name == 'a' else art.find('a', href=lambda h: h and '/p/' in str(h).lower())
                    if not a_tag or not a_tag.get('href'): continue

                    href = a_tag['href'].strip()
                    if any(x in href.lower() for x in ['/cart', '/checkout', '/login', '/mi-cuenta']):
                        continue

                    link_final = urljoin("https://www.natura.com.pe", href).split('?')[0].split('#')[0]

                    img_el = art.find('img')
                    nombre_raw = img_el.get('alt', '').strip() if img_el and img_el.get('alt') else a_tag.get_text(strip=True)

                    texto_card = art.get_text(separator=' ', strip=True)
                    precios_num = [limpiar_precio_natura(p) for p in re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_card) if limpiar_precio_natura(p) > 0]

                    p_o, p_r = 0.0, 0.0
                    if precios_num:
                        unicos = sorted(list(set(precios_num)))
                        p_o = unicos[0]
                        p_r = unicos[-1]

                    img_src = img_el.get('src', '') or img_el.get('data-src', '') if img_el else ''

                    procesar_producto_acumulativo(productos_map, link_final, nombre_raw, p_o, p_r, img_src, limite)
                except Exception:
                    continue

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [NATURA] ¡Éxito! Se indexaron {len(productos_finales)} ofertas de la grilla principal.", "success")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
