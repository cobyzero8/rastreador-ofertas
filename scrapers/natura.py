import os
import re
import json
import requests
import urllib3
import urllib.parse
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from utils import sanitizar_url, safe_log

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def obtener_key_natura():
    """
    Obtiene la clave de ScraperAPI desde st.secrets o variables de entorno.
    """
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

def asegurar_pagesize(url_base, page_size=48):
    """
    Asegura que la URL contenga pageSize=48.
    """
    parsed = urlparse(url_base)
    query_dict = parse_qs(parsed.query)
    
    if 'pageSize' not in query_dict:
        query_dict['pageSize'] = [str(page_size)]
    
    new_query = urlencode(query_dict, doseq=True)
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))

def consultar_url_natura(url_destino, es_json=False):
    """
    Consulta URLs mediante conexión directa o ScraperAPI de respaldo.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json" if es_json else "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.natura.com.pe/"
    }

    # 1. Intento directo
    try:
        resp = requests.get(url_destino, headers=headers, timeout=8, verify=False)
        if resp.status_code == 200 and len(resp.text) > 500:
            return resp.text
    except Exception:
        pass

    # 2. Respaldo ScraperAPI
    key = obtener_key_natura()
    if not key:
        safe_log("🛑 [NATURA] No se encontró clave de ScraperAPI en los secretos.", "error")
        return None

    try:
        payload = {
            'api_key': key,
            'url': url_destino,
            'render': 'false'
        }
        resp_sc = requests.get('http://api.scraperapi.com', params=payload, headers=headers, timeout=25)
        if resp_sc.status_code == 200 and len(resp_sc.text) > 200:
            return resp_sc.text
    except Exception as e:
        safe_log(f"🚨 [NATURA] Error con ScraperAPI: {e}", "error")

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

def normalizar_url_imagen(url_raw, natper_id=""):
    """
    Sanea y construye URLs del CDN Demandware de Natura.
    """
    if not url_raw or 'data:image' in str(url_raw).lower():
        if natper_id:
            return f"https://production.na01.natura.com/dw/image/v2/BFKR_PRD/on/demandware.static/-/Sites-natura-pe-storefront-catalog/default/dw123456/products/NATPER-{natper_id}_1.jpg?sw=300&q=80"
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
        if 'Sites-natura-pe-storefront-catalog' in path_clean or 'dw/image' in path_clean or 'demandware' in path_clean:
            if 'http' in path_clean:
                url_clean = path_clean[path_clean.find('http'):]
            else:
                url_clean = 'https://production.na01.natura.com/' + path_clean
        elif path_clean.startswith('dw') or 'NATPER-' in path_clean:
            url_clean = 'https://production.na01.natura.com/dw/image/v2/BFKR_PRD/on/demandware.static/-/Sites-natura-pe-storefront-catalog/default/' + path_clean
        else:
            url_clean = urljoin("https://www.natura.com.pe", path_clean)

    return url_clean

def limpiar_nombre_natura(nombre):
    if not nombre: return ""
    clean = str(nombre).strip().upper()
    if clean.startswith("NATURA -"):
        clean = clean[8:].strip()
    elif clean.startswith("NATURA"):
        clean = clean[6:].strip()
    clean = clean.lstrip('- ').strip()

    if not clean or len(clean) < 3 or clean in ['COMPRAR', 'VER MÁS', 'AGREGAR', 'AGREGAR A MI BOLSA']:
        return ""

    return f"NATURA - {clean}"

def procesar_producto_acumulativo(productos_map, link_final, nombre, p_o, p_r, img_url, limite):
    if not link_final or p_o <= 0 or p_o > limite:
        return

    nombre_final = limpiar_nombre_natura(nombre)
    if not nombre_final:
        return

    natper_id = ""
    match_id = re.search(r'NATPER-(\d+)', link_final, re.I)
    if match_id:
        natper_id = match_id.group(1)

    img_clean = normalizar_url_imagen(img_url, natper_id)

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

def probar_apis_vtex(raw_path, productos_map, limite):
    """
    Prueba en secuencia las 4 rutas posibles de la API VTEX.
    """
    clean_path = raw_path.strip('/')
    cat_slug = clean_path[2:] if clean_path.startswith('c/') else clean_path
    full_cat = clean_path if clean_path.startswith('c/') else f"c/{clean_path}"
    term = urllib.parse.quote(cat_slug.replace('-', ' '))

    endpoints = [
        f"https://www.natura.com.pe/api/io/_v/api/intelligent-search/product_search/{full_cat}?page=1&count=50",
        f"https://www.natura.com.pe/api/io/_v/api/intelligent-search/product_search?query={term}&page=1&count=50",
        f"https://www.natura.com.pe/api/catalog_system/pub/products/search/{cat_slug}?_from=0&_to=49",
        f"https://www.natura.com.pe/api/catalog_system/pub/products/search?ft={term}&_from=0&_to=49"
    ]

    for api_url in endpoints:
        safe_log(f"📡 [NATURA API] Probando endpoint: {api_url}", "info")
        res_text = consultar_url_natura(api_url, es_json=True)
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

                        link_final = urljoin("https://www.natura.com.pe", link_rel).split('?')[0].split('#')[0]
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

                if len(productos_map) >= 12:
                    safe_log(f"✅ [NATURA API] Se obtuvieron {len(productos_map)} ofertas directamente de la API.", "success")
                    return True
        except Exception:
            continue

    return False

def extraer_de_json_ld(full_html, productos_map, limite):
    """
    Rastrea el script SEO ItemList (application/ld+json).
    """
    ld_matches = re.findall(r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', full_html, re.DOTALL | re.I)
    for ld_text in ld_matches:
        try:
            ld_json = json.loads(ld_text.strip())
            def parse_ld(obj):
                if isinstance(obj, dict):
                    if obj.get('@type') in ['ItemList', 'ListItem'] or 'itemListElement' in obj:
                        elems = obj.get('itemListElement', [])
                        if isinstance(elems, list):
                            for el in elems:
                                parse_ld(el)

                    item = obj.get('item') if isinstance(obj.get('item'), dict) else obj
                    name = str(item.get('name') or item.get('productName') or '').strip()
                    url_val = str(item.get('url') or item.get('link') or '').strip()

                    if name and url_val and ('/p/' in url_val or 'NATPER-' in url_val):
                        link_final = urljoin("https://www.natura.com.pe", url_val).split('?')[0].split('#')[0]
                        price = 0.0
                        offers = item.get('offers')
                        if isinstance(offers, dict):
                            price = float(offers.get('price') or offers.get('lowPrice') or 0.0)
                        elif isinstance(offers, list) and len(offers) > 0:
                            price = float(offers[0].get('price') or 0.0)

                        img_url = str(item.get('image') or '')
                        procesar_producto_acumulativo(productos_map, link_final, name, price, price, img_url, limite)

                    for k, v in obj.items():
                        if isinstance(v, (dict, list)): parse_ld(v)
                elif isinstance(obj, list):
                    for el in obj: parse_ld(el)

            parse_ld(ld_json)
        except Exception:
            pass

def extraer_de_json_scripts(full_html, productos_map, limite):
    """
    Rastrea __NEXT_DATA__ y scripts de la página.
    """
    matches = re.findall(r'<script[^>]*>(.*?)</script>', full_html, re.DOTALL | re.IGNORECASE)
    for script_text in matches:
        s_clean = script_text.strip()
        if len(s_clean) > 50 and any(k in s_clean for k in ['NATPER', 'productName', 'spotPrice', 'commertialOffer', '/p/']):
            try:
                data = json.loads(s_clean)
                def walk(obj):
                    if isinstance(obj, dict):
                        name = str(obj.get('productName') or obj.get('name') or obj.get('title') or '').strip()
                        url_rel = str(obj.get('link') or obj.get('url') or obj.get('slug') or '').strip()
                        pid = str(obj.get('productId') or obj.get('id') or '').strip()

                        if name and (url_rel or pid) and len(name) > 3:
                            link_final = ""
                            if url_rel:
                                link_final = urljoin("https://www.natura.com.pe", url_rel).split('?')[0].split('#')[0]
                            elif pid:
                                clean_pid = pid if 'NATPER-' in pid else f"NATPER-{pid}"
                                link_final = f"https://www.natura.com.pe/p/producto/{clean_pid}"

                            if link_final and ('/p/' in link_final.lower() or 'NATPER-' in link_final):
                                price, list_price, img_url = 0.0, 0.0, ""
                                items = obj.get('items')
                                if isinstance(items, list) and len(items) > 0:
                                    first = items[0]
                                    imgs = first.get('images', [])
                                    if isinstance(imgs, list) and len(imgs) > 0:
                                        img_url = str(imgs[0].get('imageUrl') or imgs[0].get('url') or '')
                                    sellers = first.get('sellers', [])
                                    if isinstance(sellers, list) and len(sellers) > 0:
                                        comm = sellers[0].get('commertialOffer') or sellers[0].get('commercialOffer') or {}
                                        price = float(comm.get('Price') or comm.get('spotPrice') or 0.0)
                                        list_price = float(comm.get('ListPrice') or price)

                                if price <= 0:
                                    price = float(obj.get('spotPrice') or obj.get('price') or obj.get('value') or 0.0)
                                    list_price = float(obj.get('listPrice') or price)

                                if not img_url:
                                    img_url = str(obj.get('imageUrl') or obj.get('image') or '')

                                procesar_producto_acumulativo(productos_map, link_final, name, price, list_price, img_url, limite)

                        for v in obj.values():
                            if isinstance(v, (dict, list)): walk(v)
                    elif isinstance(obj, list):
                        for elem in obj: walk(elem)
                walk(data)
            except Exception:
                pass

def motor_natura(url, limite=999999.0, headers=None):
    """
    Motor principal de extracción en multicapa.
    """
    productos_map = {}
    url_base = sanitizar_url(url)
    parsed = urlparse(url_base)

    safe_log(f"🚀 [NATURA] Iniciando escaneo del catálogo...", "info")

    # CAPA 1: Probar endpoints VTEX en secuencia
    exito_api = probar_apis_vtex(parsed.path, productos_map, limite)

    # CAPA 2: Respaldo HTML completo si las APIs no entregan los productos
    if not exito_api or len(productos_map) < 12:
        url_final = asegurar_pagesize(url_base, page_size=48)
        safe_log(f"🛡️ [NATURA] Ejecutando escáner HTML sobre: {url_final}", "warning")
        
        html_content = consultar_url_natura(url_final, es_json=False)
        if html_content:
            extraer_de_json_ld(html_content, productos_map, limite)
            extraer_de_json_scripts(html_content, productos_map, limite)

            # Rastrear elementos DOM en BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            articulos = soup.find_all(['article', 'div'], attrs={'data-testid': re.compile(r'product-card', re.I)}) or \
                        soup.find_all('a', href=lambda h: h and '/p/' in str(h).lower())

            for art in articulos:
                try:
                    a_tag = art if art.name == 'a' else art.find('a', href=lambda h: h and '/p/' in str(h).lower())
                    if not a_tag or not a_tag.get('href'): continue

                    href = a_tag['href'].strip()
                    if any(x in href.lower() for x in ['/cart', '/checkout', '/login', '/mi-cuenta']): continue

                    link_final = urljoin("https://www.natura.com.pe", href).split('?')[0].split('#')[0]
                    card = a_tag.find_parent(['div', 'article']) or a_tag

                    img_el = card.find('img')
                    nombre_raw = img_el.get('alt', '').strip() if img_el and img_el.get('alt') else a_tag.get_text(strip=True)

                    texto_card = card.get_text(separator=' ', strip=True)
                    precios_found = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_card)
                    precios_num = [limpiar_precio_natura(p) for p in precios_found if limpiar_precio_natura(p) > 0]

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
        safe_log(f"✅ [NATURA] ¡Éxito! Se indexaron un total de {len(productos_finales)} ofertas válidas de la grilla principal.", "success")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
