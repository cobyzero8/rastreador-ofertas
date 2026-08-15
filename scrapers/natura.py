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
    Garantiza que la URL contenga pageSize=48 desde la primera consulta.
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

def consultar_natura_con_cascada(url_destino):
    """
    Consulta rápida a Natura en 2 segundos (render=false) para obtener el HTML completo con __NEXT_DATA__.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Referer": "https://www.natura.com.pe/"
    }

    # 1. Intento directo
    try:
        resp = requests.get(url_destino, headers=headers, timeout=10, verify=False)
        if resp.status_code == 200 and len(resp.text) > 2000 and "desafortunadamente no encontramos" not in resp.text.lower():
            return resp.text
    except Exception:
        pass

    # 2. Respaldo ScraperAPI (Modo rápido render=false)
    key = obtener_key_natura()
    if not key:
        safe_log("🛑 [NATURA] No se encontró clave de ScraperAPI en los secretos.", "error")
        return None

    try:
        safe_log("🛡️ [NATURA] Consultando catálogo vía ScraperAPI (Modo rápido)...", "info")
        payload = {
            'api_key': key,
            'url': url_destino,
            'render': 'false'  # Rápido, 1 solo crédito
        }
        resp_sc = requests.get('http://api.scraperapi.com', params=payload, headers={"User-Agent": headers["User-Agent"]}, timeout=30)
        if resp_sc.status_code == 200 and len(resp_sc.text) > 1000:
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

def normalizar_url_imagen(url_raw):
    """
    Construye URLs completas del CDN de Demandware de Natura.
    """
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

def extraer_de_json_scripts(full_html, productos_map, limite):
    """
    Rastrea el script __NEXT_DATA__ para extraer los 28 productos de la grilla.
    """
    matches = re.findall(r'<script[^>]*>(.*?)</script>', full_html, re.DOTALL | re.IGNORECASE)
    for script_text in matches:
        script_clean = script_text.strip()
        if not script_clean or len(script_clean) < 30:
            continue
        if any(k in script_clean for k in ['NATPER', 'productName', 'spotPrice', 'commertialOffer', '/p/']):
            try:
                data = json.loads(script_clean)
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
                            walk(v)
                    elif isinstance(obj, list):
                        for elem in obj:
                            walk(elem)
                walk(data)
            except Exception:
                pass

def extraer_de_dom_html(soup, productos_map, limite, full_html):
    """
    Rastrea elementos del DOM HTML (<article>, tarjetas y enlaces /p/).
    """
    articulos = soup.find_all(['article', 'div'], attrs={'data-testid': re.compile(r'product-card', re.I)}) or \
                soup.find_all(['article', 'div'], attrs={'id': 'product-card'}) or \
                soup.find_all('a', href=lambda h: h and '/p/' in str(h).lower())

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

def motor_natura(url, limite=999999.0, headers=None):
    """
    Motor principal de Natura Perú.
    """
    productos_map = {}
    url_base = sanitizar_url(url)

    url_final = asegurar_pagesize(url_base, page_size=48)
    safe_log(f"🚀 [NATURA] Consultando catálogo completo: {url_final}", "info")

    html_content = consultar_natura_con_cascada(url_final)

    if not html_content:
        safe_log("⚠️ [NATURA] No se obtuvo respuesta válida de la tienda.", "warning")
        return []

    # 1. Extraer desde el estado JSON nativo __NEXT_DATA__
    extraer_de_json_scripts(html_content, productos_map, limite)

    # 2. Complementar con el DOM HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    extraer_de_dom_html(soup, productos_map, limite, html_content)

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [NATURA] ¡Éxito! Se indexaron un total de {len(productos_finales)} ofertas válidas.", "success")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
