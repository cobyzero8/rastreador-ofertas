import os
import re
import json
import time
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from utils import sanitizar_url, safe_log

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# -------------------------
# Configuración y Obtención de Claves
# -------------------------
def obtener_key_natura():
    """
    Obtiene la clave de ScraperAPI priorizando Streamlit secrets o variables de entorno.
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
    Garantiza que la URL incluya el parámetro pageSize=48.
    """
    parsed = urlparse(url_base)
    query_dict = parse_qs(parsed.query)
    if 'pageSize' not in query_dict:
        query_dict['pageSize'] = [str(page_size)]
    new_query = urlencode(query_dict, doseq=True)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

# -------------------------
# Descarga HTML (Directa o ScraperAPI)
# -------------------------
def descargar_html(url_destino, headers=None):
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": "https://www.natura.com.pe/"
        }

    # 1. Intento directo
    try:
        resp = requests.get(url_destino, headers=headers, timeout=12, verify=False)
        if resp.status_code == 200 and len(resp.text) > 1500:
            return resp.text
    except Exception:
        pass

    # 2. Respaldo ScraperAPI
    key = obtener_key_natura()
    if key:
        try:
            payload = {'api_key': key, 'url': url_destino, 'render': 'false'}
            resp_sc = requests.get('http://api.scraperapi.com', params=payload, headers=headers, timeout=30)
            if resp_sc.status_code == 200 and len(resp_sc.text) > 1000:
                return resp_sc.text
        except Exception:
            pass

    return None

# -------------------------
# Helpers de Procesamiento de Datos
# -------------------------
def limpiar_precio(texto):
    if not texto:
        return 0.0
    s = str(texto).replace('\xa0', ' ').replace('&nbsp;', ' ')
    s = re.sub(r'[^\d,.\s]', '', s).strip()
    m = re.search(r'\d+(?:[.,]\d+)?', s)
    if not m:
        return 0.0
    raw = m.group(0)
    if ',' in raw and '.' in raw:
        raw = raw.replace(',', '')
    elif ',' in raw and len(raw.split(',')[-1]) == 2:
        raw = raw.replace(',', '.')
    else:
        raw = raw.replace(',', '')
    try:
        return float(raw)
    except Exception:
        return 0.0

def limpiar_nombre(nombre_raw):
    if not nombre_raw:
        return ""
    clean = re.sub(r'\s+', ' ', str(nombre_raw).strip())
    up = clean.upper()
    if up.startswith("NATURA -"):
        clean = clean[8:].strip()
    elif up.startswith("NATURA"):
        clean = clean[6:].strip()
    clean = clean.lstrip('- ').strip()
    if not clean or len(clean) < 2 or clean.upper() in ['COMPRAR', 'VER MÁS', 'AGREGAR', 'AGREGAR A MI BOLSA']:
        return ""
    return f"NATURA - {clean}"

def extraer_volumen(texto):
    if not texto:
        return ""
    m = re.search(r'(\d+(?:[.,]\d+)?\s*(?:ML|ml|Ml|mL|G|g))', texto)
    return m.group(1).upper().replace(' ', '') if m else ""

def calcular_descuento(precio_oferta, precio_regular):
    try:
        if precio_regular and precio_regular > precio_oferta:
            pct = round((1 - (precio_oferta / precio_regular)) * 100, 2)
            return pct if pct > 0 else 0.0
    except Exception:
        pass
    return 0.0

# -------------------------
# Estrategia 1: Next.js Stream / JSON
# -------------------------
def extraer_desde_next_stream(html_text, productos_map, limite):
    clean_html = html_text.replace(r'\/', '/').replace(r'\"', '"').replace('&quot;', '"').replace('&amp;', '&')
    
    natper_matches = list(re.finditer(r'NATPER-\d+', clean_html, re.I))
    for m in natper_matches:
        start_pos = m.start()
        left = clean_html.rfind('{', max(0, start_pos - 700), start_pos)
        right = clean_html.find('}', start_pos, min(len(clean_html), start_pos + 700))

        if left != -1 and right != -1:
            json_chunk = clean_html[left : right + 1]
            try:
                data = json.loads(json_chunk)
                name = str(data.get('productName') or data.get('name') or data.get('title') or '').strip()
                link_rel = str(data.get('link') or data.get('slug') or data.get('url') or '').strip()

                if name and link_rel and '/p/' in link_rel.lower():
                    link_final = link_rel if link_rel.startswith('http') else f"https://www.natura.com.pe{link_rel}"
                    link_final = link_final.split('?')[0].split('#')[0]

                    price = float(data.get('spotPrice') or data.get('price') or data.get('spot_price') or 0.0)
                    list_price = float(data.get('listPrice') or data.get('list_price') or price)
                    img_url = str(data.get('imageUrl') or data.get('image') or '')

                    nombre_final = limpiar_nombre(name)
                    volumen = extraer_volumen(name + " " + str(data.get('description') or ''))
                    descuento_pct = calcular_descuento(price, list_price)

                    if price > 0 and price <= limite and nombre_final and link_final not in productos_map:
                        productos_map[link_final] = {
                            "nombre": nombre_final,
                            "precio": price,
                            "precio_regular": max(list_price, price),
                            "descuento_pct": descuento_pct,
                            "volumen": volumen,
                            "tags": [],
                            "link": link_final,
                            "img": img_url
                        }
            except Exception:
                pass

# -------------------------
# Estrategia 2: Extracción del DOM
# -------------------------
def extraer_desde_dom_grid(soup, productos_map, limite):
    grid = soup.find(attrs={'data-testid': 'plp-products-grid'}) or soup
    cards = grid.find_all(['article', 'div'], attrs={'data-testid': re.compile(r'product-card', re.I)}) \
            or grid.find_all(['article', 'div'], attrs={'id': re.compile(r'product-card', re.I)})

    if not cards:
        cards = [c for c in grid.find_all(['div', 'article']) if c.find('a', href=lambda h: h and '/p/' in h.lower())]

    for card in cards:
        try:
            a_tag = card.find('a', href=lambda h: h and '/p/' in h.lower())
            if not a_tag:
                a_tag = card.find('a', href=True)
            if not a_tag or not a_tag.get('href'):
                continue

            href = a_tag['href'].strip()
            link_final = urljoin("https://www.natura.com.pe", href).split('?')[0].split('#')[0]

            img_el = card.find('img')
            img_src = ''
            if img_el:
                img_src = img_el.get('data-src') or img_el.get('src') or img_el.get('data-lazy-src') or ''

            nombre_raw = ''
            if img_el and img_el.get('alt'):
                nombre_raw = img_el.get('alt')
            else:
                title_el = card.find(['h2', 'h3', 'h4', 'span'], text=True)
                nombre_raw = title_el.get_text(strip=True) if title_el else a_tag.get_text(strip=True)

            texto_card = card.get_text(separator=' ', strip=True)
            precios_found = re.findall(r'(?:S/\.?\s*|PEN\s*|S/)\s*([\d\.,]+)', texto_card)
            precios_num = [limpiar_precio(p) for p in precios_found if limpiar_precio(p) > 0]

            if not precios_num:
                price_spans = card.find_all(attrs={'class': re.compile(r'price', re.I)})
                for ps in price_spans:
                    pval = limpiar_precio(ps.get_text())
                    if pval > 0:
                        precios_num.append(pval)

            if not precios_num:
                continue

            precio_oferta = min(precios_num)
            precio_regular = max(precios_num) if len(precios_num) > 1 else precio_oferta

            nombre_final = limpiar_nombre(nombre_raw)
            volumen = extraer_volumen(texto_card)
            tags = []
            tag_els = card.find_all(attrs={'class': re.compile(r'(badge|tag|label)', re.I)})
            for t in tag_els:
                txt = t.get_text(strip=True)
                if txt:
                    tags.append(txt.upper())

            descuento_pct = calcular_descuento(precio_oferta, precio_regular)

            if precio_oferta > 0 and precio_oferta <= limite and nombre_final:
                productos_map[link_final] = {
                    "nombre": nombre_final,
                    "precio": precio_oferta,
                    "precio_regular": max(precio_regular, precio_oferta),
                    "descuento_pct": descuento_pct,
                    "volumen": volumen,
                    "tags": list(dict.fromkeys(tags)),
                    "link": link_final,
                    "img": img_src
                }
        except Exception:
            continue

# -------------------------
# Motor Principal Integrado
# -------------------------
def motor_natura(url, limite=999999.0, headers=None):
    """
    Función principal llamada por el enrutador del proyecto.
    """
    productos_map = {}
    url_base = sanitizar_url(url)
    url_final = asegurar_pagesize(url_base, page_size=48)
    
    safe_log(f"🚀 [NATURA] Escaneando catálogo: {url_final}", "info")

    html_content = descargar_html(url_final, headers=headers)
    if not html_content:
        safe_log("🛑 [NATURA] No se pudo obtener el contenido HTML de la página.", "error")
        return []

    # 1. Extracción de tramas Next.js
    extraer_desde_next_stream(html_content, productos_map, limite)

    # 2. Extracción DOM HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    extraer_desde_dom_grid(soup, productos_map, limite)

    # 3. Paginación secuencial
    next_links = []
    try:
        rel_next = soup.find('link', rel='next')
        if rel_next and rel_next.get('href'):
            next_links.append(urljoin(url_final, rel_next['href']))
        pag_links = soup.find_all('a', href=True, text=re.compile(r'^\s*\d+\s*$'))
        for pl in pag_links:
            href = urljoin(url_final, pl['href'])
            if href not in next_links:
                next_links.append(href)
    except Exception:
        pass

    visited = set()
    pages = 0
    for nl in next_links:
        if pages >= 4:
            break
        if nl in visited:
            continue
        visited.add(nl)
        time.sleep(0.5)
        safe_log(f"🔄 [NATURA] Siguiendo paginación: {nl}", "info")
        html2 = descargar_html(asegurar_pagesize(nl), headers=headers)
        if not html2:
            continue
        extraer_desde_next_stream(html2, productos_map, limite)
        soup2 = BeautifulSoup(html2, 'html.parser')
        extraer_desde_dom_grid(soup2, productos_map, limite)
        pages += 1

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [NATURA] Se extrajeron un total de {len(productos_finales)} ofertas válidas.", "success")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
