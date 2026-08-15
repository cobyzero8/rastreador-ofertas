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

def consultar_natura_html(url_destino):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://www.natura.com.pe/"
    }

    # 1. Intento directo
    try:
        resp = requests.get(url_destino, headers=headers, timeout=10, verify=False)
        if resp.status_code == 200 and len(resp.text) > 2000:
            return resp.text
    except Exception:
        pass

    # 2. Respaldo ScraperAPI (render=false, rápido y seguro)
    key = obtener_key_natura()
    if not key:
        safe_log("🛑 [NATURA] No se encontró clave de ScraperAPI.", "error")
        return None

    try:
        payload = {
            'api_key': key,
            'url': url_destino,
            'render': 'false'
        }
        resp_sc = requests.get('http://api.scraperapi.com', params=payload, headers=headers, timeout=30)
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

def normalizar_url_imagen(url_raw, natper_id=""):
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

def extraer_de_next_stream_payloads(html_text, productos_map, limite):
    """
    Escanea las tramas de datos self.__next_f.push(...) y scripts JSON de Next.js
    que contienen las 28 fichas de la grilla principal.
    """
    # 1. Buscar todos los enlaces /p/slug/NATPER-ID en el texto completo del HTML
    enlaces_raw = set(re.findall(r'(/p/[a-zA-Z0-9\-_]+/NATPER-\d+)', html_text, re.I))

    for rel_link in enlaces_raw:
        try:
            link_final = f"https://www.natura.com.pe{rel_link}"
            natper_match = re.search(r'NATPER-(\d+)', rel_link, re.I)
            natper_id = natper_match.group(1) if natper_match else ""

            # Extraer slug para generar un nombre base
            slug_part = rel_link.split('/p/')[1].split('/NATPER-')[0]
            parts = [p.capitalize() for p in slug_part.split('-') if not p.isdigit()]
            nombre_base = " ".join(parts).upper()

            # Buscar imagen asociada a ese NATPER-ID en todo el HTML
            img_url = ""
            p_img = re.compile(rf'(https?://[^\s"\'>\\]+?NATPER-{natper_id}[^\s"\'>\\]*?\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'>\\]*)?)', re.I)
            m_img = p_img.search(html_text.replace('\\/', '/'))
            if m_img:
                img_url = m_img.group(1)

            # Buscar bloque de precio alrededor de esa ocurrencia en el HTML
            idx = html_text.find(rel_link)
            p_o, p_r = 0.0, 0.0
            if idx != -1:
                sub_text = html_text[max(0, idx - 500): min(len(html_text), idx + 800)]

                # Precios en JSON (spotPrice / price / Price)
                prices_found = re.findall(r'(?:"spotPrice"|"price"|"Price"|"listPrice"|"ListPrice")\s*:\s*(\d+(?:\.\d+)?)', sub_text)
                nums_json = [float(p) for p in prices_found if float(p) > 0]
                if nums_json:
                    p_o = min(nums_json)
                    p_r = max(nums_json)
                else:
                    # Precios en texto S/ XX.XX
                    precios_text = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', sub_text)
                    nums_text = [limpiar_precio_natura(p) for p in precios_text if limpiar_precio_natura(p) > 0]
                    if nums_text:
                        p_o = min(nums_text)
                        p_r = max(nums_text)

            if p_o > 0 and p_o <= limite:
                procesar_producto_acumulativo(productos_map, link_final, nombre_base, p_o, p_r, img_url, limite)
        except Exception:
            continue

    # 2. Escanear objetos JSON estructurales (scripts)
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', html_text, re.DOTALL | re.IGNORECASE)
    for s_text in scripts:
        if len(s_text) > 50 and any(k in s_text for k in ['NATPER', 'productName', 'spotPrice', '/p/']):
            try:
                # Tratar de parsear JSON directo si es un script estándar
                data = json.loads(s_text.strip())
                def walk(obj):
                    if isinstance(obj, dict):
                        name = str(obj.get('productName') or obj.get('name') or '').strip()
                        url_rel = str(obj.get('link') or obj.get('url') or obj.get('slug') or '').strip()

                        if name and url_rel and '/p/' in url_rel.lower():
                            link_final = urljoin("https://www.natura.com.pe", url_rel).split('?')[0].split('#')[0]
                            price = float(obj.get('spotPrice') or obj.get('price') or 0.0)
                            list_price = float(obj.get('listPrice') or price)
                            img_url = str(obj.get('imageUrl') or obj.get('image') or '')

                            if price > 0:
                                procesar_producto_acumulativo(productos_map, link_final, name, price, list_price, img_url, limite)

                        for v in obj.values():
                            if isinstance(v, (dict, list)): walk(v)
                    elif isinstance(obj, list):
                        for el in obj: walk(el)
                walk(data)
            except Exception:
                pass

def extraer_de_dom_bs4(soup, productos_map, limite, html_text):
    """
    Rastrea tarjetas renderizadas directamente en el DOM HTML (<article> / <a>).
    """
    articulos = soup.find_all(['article', 'div'], attrs={'data-testid': re.compile(r'product-card', re.I)}) or \
                soup.find_all(['article', 'div'], attrs={'id': 'product-card'}) or \
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

def motor_natura(url, limite=999999.0, headers=None):
    """
    Motor principal de extracción simplificado y desacoplado.
    """
    productos_map = {}
    url_base = sanitizar_url(url)
    url_final = asegurar_pagesize(url_base, page_size=48)

    safe_log(f"🚀 [NATURA] Consultando catálogo completo: {url_final}", "info")

    html_content = consultar_natura_html(url_final)

    if not html_content:
        safe_log("🛑 [NATURA] No se pudo obtener el contenido HTML de la página.", "error")
        return []

    # 1. Extracción desde las tramas de Next.js App Router (self.__next_f)
    extraer_de_next_stream_payloads(html_content, productos_map, limite)

    # 2. Extracción complementaria desde el DOM
    soup = BeautifulSoup(html_content, 'html.parser')
    extraer_de_dom_bs4(soup, productos_map, limite, html_content)

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [NATURA] ¡Éxito! Se indexaron un total de {len(productos_finales)} ofertas válidas de la grilla principal.", "success")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
