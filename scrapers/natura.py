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
    """
    Obtiene la clave de ScraperAPI para Natura o la clave general.
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

def consultar_natura_con_cascada(url_destino):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Referer": "https://www.natura.com.pe/"
    }

    # 🟢 Paso 1: Intento directo gratis
    try:
        resp = requests.get(url_destino, headers=headers, timeout=12, verify=False)
        if resp.status_code == 200 and len(resp.text) > 2000 and any(x in resp.text.lower() for x in ['/p/', 'natura', '__next_data__']):
            return resp
    except Exception:
        pass

    # 🛡️ Paso 2: Respaldo con ScraperAPI
    key = obtener_key_natura()
    if not key:
        safe_log("🛑 [NATURA] No se encontró clave de ScraperAPI en los secretos.", "error")
        return None

    try:
        safe_log(f"🛡️ [NATURA] Consultando vía ScraperAPI...", "info")
        payload = {
            'api_key': key,
            'url': url_destino,
            'country_code': 'us',
            'render': 'false'
        }
        resp_sc = requests.get('http://api.scraperapi.com', params=payload, headers=headers, timeout=30)
        if resp_sc.status_code == 200 and len(resp_sc.text) > 1000:
            return resp_sc
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

def extraer_precios_de_texto(texto):
    """
    Extrae oferta y precio regular analizando cualquier bloque de texto.
    """
    if not texto: return 0.0, 0.0
    encontrados = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', str(texto), re.I)
    validos = []
    for raw in encontrados:
        p = limpiar_precio_natura(raw)
        if p > 0: validos.append(p)
    if validos:
        unicos = sorted(list(set(validos)))
        p_o = unicos[0]
        p_r = unicos[-1] if len(unicos) > 1 else p_o
        return p_o, p_r
    return 0.0, 0.0

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

def extraer_imagen_natura(card, a_tag, href, full_html=""):
    comb = str(card).replace('\\/', '/') + " " + str(a_tag)
    
    match_id = re.search(r'NATPER-(\d+)', href + " " + comb, re.I)
    if match_id:
        natper_id = match_id.group(1)
        p1 = re.compile(rf'(https?://[^\s"\'>\\]+?NATPER-{natper_id}[^\s"\'>\\]*?\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'>\\]*)?)', re.I)
        m1 = p1.search(full_html.replace('\\/', '/'))
        if m1: return normalizar_url_imagen(m1.group(1))

        p2 = re.compile(rf'([^\s"\'>\\]*?dw[a-f0-9]+[^\s"\'>\\]*?NATPER-{natper_id}[^\s"\'>\\]*?\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'>\\]*)?)', re.I)
        m2 = p2.search(full_html.replace('\\/', '/'))
        if m2:
            path = m2.group(1).lstrip('/')
            if 'Sites-natura-pe-storefront-catalog' in path:
                return normalizar_url_imagen('https://production.na01.natura.com/' + path)
            else:
                return normalizar_url_imagen('https://production.na01.natura.com/dw/image/v2/BFKR_PRD/on/demandware.static/-/Sites-natura-pe-storefront-catalog/default/' + path)

    if hasattr(a_tag, 'find_all') and hasattr(card, 'find_all'):
        for tag in a_tag.find_all(['img', 'source']) + card.find_all(['img', 'source']):
            for attr in ['src', 'data-src', 'srcset', 'data-srcset']:
                val = tag.get(attr, '')
                url_norm = normalizar_url_imagen(val)
                if url_norm and any(ext in url_norm.lower() for ext in ['demandware', 'natura', 'products', '.jpg', '.jpeg', '.png', '.webp']):
                    return url_norm

    match_dw = re.search(r'(https?://production\.na01\.natura\.com/dw/image/v2/[^\s"\'>\\]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'>\\]*)?)', comb, re.I)
    if match_dw: return normalizar_url_imagen(match_dw.group(1))

    return ""

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

def extraer_de_next_data(html_text, productos_map, limite):
    """
    CAPA 1: Escanea recursivamente el script JSON de Next.js (__NEXT_DATA__)
    """
    match_script = re.search(r'<script\s+id="__NEXT_DATA__"\s+type="application/json">\s*({.*?})\s*</script>', html_text, re.DOTALL)
    if not match_script:
        return

    try:
        data = json.loads(match_script.group(1))
        
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
                        link_final = f"https://www.natura.com.pe/p/producto/NATPER-{pid}"

                    if link_final and '/p/' in link_final.lower():
                        price, list_price, img_url = 0.0, 0.0, ""

                        items = obj.get('items')
                        if isinstance(items, list) and len(items) > 0:
                            first_item = items[0]
                            imgs = first_item.get('images', [])
                            if imgs and isinstance(imgs, list) and len(imgs) > 0:
                                img_url = imgs[0].get('imageUrl') or imgs[0].get('url') or ''
                            
                            sellers = first_item.get('sellers', [])
                            if sellers and isinstance(sellers, list) and len(sellers) > 0:
                                comm = sellers[0].get('commertialOffer') or sellers[0].get('commercialOffer') or {}
                                price = float(comm.get('Price') or comm.get('spotPrice') or 0.0)
                                list_price = float(comm.get('ListPrice') or price)

                        if price <= 0:
                            price = float(obj.get('spotPrice') or obj.get('price') or obj.get('value') or 0.0)
                            list_price = float(obj.get('listPrice') or price)

                        if not img_url:
                            img_url = str(obj.get('imageUrl') or obj.get('image') or '')

                        procesar_producto_acumulativo(productos_map, link_final, name, price, list_price, img_url, limite)

                for v in obj.values(): walk(v)
            elif isinstance(obj, list):
                for elem in obj: walk(elem)

        walk(data)
    except Exception:
        pass

def consultar_vtex_api_rutas(cat_path, productos_map, limite):
    """
    CAPA 2: Consulta endpoints REST de VTEX para la categoría
    """
    clean_path = cat_path.strip('/').replace('c/', '')
    rutas_api = [
        f"https://www.natura.com.pe/api/catalog_system/pub/products/search/{clean_path}?_from=0&_to=49",
        f"https://www.natura.com.pe/api/catalog_system/pub/products/search/{clean_path.replace('-', '/')}?_from=0&_to=49",
        f"https://www.natura.com.pe/api/catalog_system/pub/products/search?ft={urllib.parse.quote(clean_path.replace('-', ' '))}&_from=0&_to=49"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://www.natura.com.pe/"
    }

    for api_url in rutas_api:
        try:
            resp = requests.get(api_url, headers=headers, timeout=8, verify=False)
            if resp.status_code == 200 and len(resp.content) > 50:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    for prod in data:
                        try:
                            raw_name = str(prod.get('productName') or '').strip()
                            link_rel = prod.get('link') or ''
                            if not raw_name or not link_rel: continue

                            link_final = urljoin("https://www.natura.com.pe", link_rel).split('?')[0]
                            items = prod.get('items', [])
                            p_o, p_r, img_url = 0.0, 0.0, ""

                            if items and isinstance(items, list):
                                first_item = items[0]
                                images = first_item.get('images', [])
                                if images and isinstance(images, list) and len(images) > 0:
                                    img_url = images[0].get('imageUrl', '')

                                sellers = first_item.get('sellers', [])
                                if sellers and isinstance(sellers, list) and len(sellers) > 0:
                                    comm = sellers[0].get('commertialOffer', {}) or sellers[0].get('commercialOffer', {})
                                    p_o = float(comm.get('Price') or comm.get('spotPrice') or 0.0)
                                    p_r = float(comm.get('ListPrice') or p_o)

                            if p_o > 0:
                                procesar_producto_acumulativo(productos_map, link_final, raw_name, p_o, p_r, img_url, limite)
                        except Exception:
                            continue
                    if len(productos_map) >= 12:
                        break
        except Exception:
            continue

def motor_natura(url, limite=999999.0, headers=None, max_paginas=3):
    """
    Motor extractor de productos para Natura Perú
    """
    productos_map = {}
    url_base = sanitizar_url(url)
    parsed = urllib.parse.urlparse(url_base)

    safe_log(f"🚀 [NATURA] Iniciando extracción inteligente...", "info")

    # 1. Probar API VTEX
    consultar_vtex_api_rutas(parsed.path, productos_map, limite)
    if productos_map:
        safe_log(f"⚡ [NATURA] Se recuperaron {len(productos_map)} productos directamente vía API.", "success")

    # 2. Escaneo HTML de la página (con __NEXT_DATA__ y DOM)
    for pagina in range(1, max_paginas + 1):
        url_pagina = f"{url_base}?page={pagina}&pageSize=48" if pagina > 1 else url_base
        resp = consultar_natura_con_cascada(url_pagina)

        if not resp or resp.status_code != 200 or not resp.text:
            break

        full_html = resp.text
        soup = BeautifulSoup(full_html, 'html.parser')
        conteo_previo = len(productos_map)

        # Extraer desde __NEXT_DATA__
        extraer_de_next_data(full_html, productos_map, limite)

        # Extraer desde elementos DOM <article> / <a>
        articulos = soup.find_all(['article', 'div'], attrs={'id': 'product-card'}) + soup.find_all(['article', 'div'], attrs={'data-testid': re.compile(r'product-card', re.I)})
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

                # Nombre
                img_el = art.find('img')
                nombre_raw = img_el.get('alt', '').strip() if img_el and img_el.get('alt') else a_tag.get_text(strip=True)

                # Precio
                p_o, p_r = extraer_precios_de_texto(art.get_text())

                # Imagen
                img_url = extraer_imagen_natura(art, a_tag, href, full_html)

                procesar_producto_acumulativo(productos_map, link_final, nombre_raw, p_o, p_r, img_url, limite)
            except Exception:
                continue

        nuevos = len(productos_map) - conteo_previo
        if nuevos == 0 and pagina > 1:
            break

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [NATURA] ¡Éxito! Se indexaron un total de {len(productos_finales)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
