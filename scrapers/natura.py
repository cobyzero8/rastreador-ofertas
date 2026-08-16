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
# Configuración de Claves y URLs
# -------------------------
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
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

# -------------------------
# Descarga HTML con Renderizado JS
# -------------------------
def descargar_html(url_destino, headers=None):
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Referer": "https://www.natura.com.pe/"
        }

    # 1. Intentar Petición Directa
    try:
        session = requests.Session()
        resp = session.get(url_destino, headers=headers, timeout=12, verify=False)
        if resp.status_code == 200 and len(resp.text) > 2000 and "product-card" in resp.text:
            safe_log(f"🌐 [NATURA] Petición directa exitosa ({len(resp.text)} bytes).", "info")
            return resp.text
    except Exception:
        pass

    # 2. Respaldo a ScraperAPI con JS Rendering y Selector de Espera
    key = obtener_key_natura()
    if not key:
        safe_log("🛑 [NATURA] Petición directa bloqueada y no se encontró API Key de ScraperAPI.", "error")
        return None

    safe_log("🔄 [NATURA] Solicitando renderizado dinámico con ScraperAPI...", "info")
    try:
        payload = {
            'api_key': key,
            'url': url_destino,
            'render': 'true',
            'wait_for_selector': '[data-testid="plp-products-grid"]'
        }
        resp_sc = requests.get('http://api.scraperapi.com', params=payload, headers=headers, timeout=45)
        if resp_sc.status_code == 200 and len(resp_sc.text) > 1000:
            safe_log(f"🌐 [NATURA] ScraperAPI renderizado exitoso ({len(resp_sc.text)} bytes).", "info")
            return resp_sc.text
        else:
            safe_log(f"🛑 [NATURA] ScraperAPI devolvió estado {resp_sc.status_code}.", "error")
    except Exception as e:
        safe_log(f"🛑 [NATURA] Error al conectar con ScraperAPI: {str(e)}", "error")

    return None

# -------------------------
# Utilidades de Limpieza de Precios
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
# Extracción Exclusiva de Grilla DOM (28 Productos)
# -------------------------
def extraer_desde_dom_grid(soup, productos_map, limite):
    # Aislar contenedor de la grilla principal
    grid_container = soup.find(attrs={'data-testid': 'plp-products-grid'}) or \
                     soup.find(attrs={'data-testid': 'lazy-load-wrapper'}) or \
                     soup

    cards = grid_container.find_all(['article', 'div'], attrs={'data-testid': re.compile(r'product-card', re.I)}) or \
            grid_container.find_all(['article', 'div'], attrs={'id': re.compile(r'product-card', re.I)}) or \
            grid_container.find_all('article', class_=re.compile(r'h-full', re.I))

    safe_log(f"🔎 [NATURA DOM] Tarjetas detectadas en la grilla principal: {len(cards)}", "info")

    for card in cards:
        try:
            a_tag = card.find('a', href=lambda h: h and '/p/' in str(h).lower()) or (card if card.name == 'a' else None)
            if not a_tag or not a_tag.get('href'):
                continue

            href = a_tag['href'].strip()
            if any(x in href.lower() for x in ['/cart', '/checkout', '/login', '/mi-cuenta']):
                continue

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

            nombre_final = limpiar_nombre(nombre_raw)
            if not nombre_final:
                continue

            # Extracción explícita de precios por ID / atributos de DevTools
            # 1. Precio "Por" (Oferta)
            precio_oferta = 0.0
            el_por = card.find(attrs={'id': 'product-price-por'}) or \
                     card.find(attrs={'data-testid': 'product-price-por'}) or \
                     card.find(attrs={'aria-label': 'product-price-por'})
            if el_por:
                precio_oferta = limpiar_precio(el_por.get_text())

            # 2. Precio "De" (Regular)
            precio_regular = 0.0
            el_de = card.find(attrs={'id': 'product-price-de'}) or \
                    card.find(attrs={'aria-label': 'product-price-de'}) or \
                    card.find(attrs={'data-testid': 'product-price-de'}) or \
                    card.find('p', class_=re.compile(r'line-through', re.I))
            if el_de:
                precio_regular = limpiar_precio(el_de.get_text())

            # Fallback en contenedor
            if precio_oferta <= 0 or precio_regular <= 0:
                texto_card = card.get_text(separator=' ', strip=True)
                precios_found = re.findall(r'(?:S/\.?\s*|PEN\s*|S/)\s*([\d\.,]+)', texto_card)
                precios_num = [limpiar_precio(p) for p in precios_found if limpiar_precio(p) > 0]

                if precios_num:
                    if precio_oferta <= 0:
                        precio_oferta = min(precios_num)
                    if precio_regular <= 0:
                        precio_regular = max(precios_num) if len(precios_num) > 1 else precio_oferta

            if precio_regular < precio_oferta or precio_regular <= 0:
                precio_regular = precio_oferta

            volumen = extraer_volumen(nombre_raw)
            descuento_pct = calcular_descuento(precio_oferta, precio_regular)

            if precio_oferta > 0 and precio_oferta <= limite:
                productos_map[link_final] = {
                    "nombre": nombre_final,
                    "precio": precio_oferta,
                    "precio_regular": precio_regular,
                    "descuento_pct": descuento_pct,
                    "volumen": volumen,
                    "tags": [],
                    "link": link_final,
                    "img": img_src
                }
        except Exception:
            continue

# -------------------------
# Motor Principal
# -------------------------
def motor_natura(url, limite=999999.0, headers=None):
    productos_map = {}
    url_base = sanitizar_url(url)
    url_final = asegurar_pagesize(url_base, page_size=48)

    safe_log(f"🚀 [NATURA] Escaneando catálogo: {url_final}", "info")

    html_content = descargar_html(url_final, headers=headers)
    if not html_content:
        safe_log("🛑 [NATURA] No se pudo obtener el contenido HTML de la página.", "error")
        return []

    # Extraer directamente del DOM hidratado
    soup = BeautifulSoup(html_content, 'html.parser')
    extraer_desde_dom_grid(soup, productos_map, limite)

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [NATURA] ¡Éxito! Se indexaron un total de {len(productos_finales)} ofertas de la grilla principal.", "success")
        for idx_p, p_item in enumerate(productos_finales[:5], 1):
            safe_log(f"   📌 #{idx_p}: {p_item['nombre']} → Oferta: S/ {p_item['precio']:.2f} | Regular: S/ {p_item['precio_regular']:.2f}", "info")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
