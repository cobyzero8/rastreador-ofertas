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
# Estrategia 1: Next.js Stream / Regex Robusto
# -------------------------
def extraer_desde_next_stream(html_text, productos_map, limite):
    """
    Escanea las tramas Next.js App Router (self.__next_f.push) mediante
    expresiones regulares sin depender de json.loads().
    """
    clean_html = html_text.replace(r'\/', '/').replace(r'\"', '"').replace('\\"', '"').replace('&quot;', '"').replace('&amp;', '&')

    # Identificar todos los enlaces únicos /p/.../NATPER-XXXXX
    p_links = set(re.findall(r'/p/[a-zA-Z0-9\-_%]+/NATPER-\d+', clean_html, re.I))

    for rel_link in p_links:
        try:
            link_final = f"https://www.natura.com.pe{rel_link}"
            if link_final in productos_map and productos_map[link_final]["precio"] > 0 and productos_map[link_final]["img"]:
                continue

            match_id = re.search(r'NATPER-(\d+)', rel_link, re.I)
            if not match_id:
                continue
            natper_id = match_id.group(1)

            # Buscar la posición del ID en el texto
            pos = clean_html.find(f"NATPER-{natper_id}")
            if pos == -1:
                pos = clean_html.find(rel_link)

            # Crear una ventana de contexto de +- 500 caracteres alrededor del producto
            sub = clean_html[max(0, pos - 500): min(len(clean_html), pos + 500)] if pos != -1 else ""

            # Extraer Nombre
            m_name = re.search(r'(?:"productName"|"name"|"title"|"brand")\s*:\s*"([^"]{3,120})"', sub, re.I)
            nombre_raw = ""
            if m_name and 'NATPER' not in m_name.group(1) and 'AGREGAR' not in m_name.group(1).upper():
                nombre_raw = m_name.group(1)
            else:
                slug_part = rel_link.split('/p/')[1].split('/NATPER-')[0]
                words = [w.capitalize() for w in slug_part.split('-') if not w.isdigit()]
                nombre_raw = " ".join(words)

            nombre_final = limpiar_nombre(nombre_raw)
            if not nombre_final:
                continue

            # Extraer Precios
            p_o, p_r = 0.0, 0.0
            if sub:
                spot_matches = re.findall(r'(?:"spotPrice"|"price"|"Price"|"value"|"spot_price")\s*:\s*(\d+(?:\.\d+)?)', sub)
                list_matches = re.findall(r'(?:"listPrice"|"ListPrice"|"list_price")\s*:\s*(\d+(?:\.\d+)?)', sub)

                if spot_matches:
                    valid_spot = [float(x) for x in spot_matches if float(x) > 0]
                    if valid_spot:
                        p_o = valid_spot[0]

                if list_matches:
                    valid_list = [float(x) for x in list_matches if float(x) > 0]
                    if valid_list:
                        p_r = valid_list[0]

                if p_o <= 0:
                    txt_matches = re.findall(r'(?:S/\.?\s*|PEN\s*|S/)\s*([\d\.,]+)', sub)
                    valid_prices = [limpiar_precio(tp) for tp in txt_matches if limpiar_precio(tp) > 0]
                    if valid_prices:
                        p_o = min(valid_prices)
                        p_r = max(valid_prices)

            # Extraer Imagen CDN
            p_img = re.compile(rf'(https?://[^\s"\'>\\]+?NATPER-{natper_id}[^\s"\'>\\]*?\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'>\\]*)?)', re.I)
            m_img = p_img.search(clean_html)
            img_url = m_img.group(1) if m_img else ""

            volumen = extraer_volumen(nombre_raw)
            descuento_pct = calcular_descuento(p_o, p_r)

            if p_o > 0 and p_o <= limite:
                productos_map[link_final] = {
                    "nombre": nombre_final,
                    "precio": p_o,
                    "precio_regular": max(p_r, p_o),
                    "descuento_pct": descuento_pct,
                    "volumen": volumen,
                    "tags": [],
                    "link": link_final,
                    "img": img_url
                }
        except Exception:
            continue

# -------------------------
# Estrategia 2: Extracción del DOM HTML
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
# Motor Principal
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

    # 1. Extracción desde la trama Next.js
    extraer_desde_next_stream(html_content, productos_map, limite)

    # 2. Extracción desde el DOM HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    extraer_desde_dom_grid(soup, productos_map, limite)

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [NATURA] Se extrajeron un total de {len(productos_finales)} ofertas válidas de la grilla principal.", "success")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
