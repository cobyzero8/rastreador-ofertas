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
# Descarga HTML con Diagnóstico Detallado de Logs
# -------------------------
def descargar_html(url_destino, headers=None):
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Sec-Ch-Ua": '"Not)A;Brand";v="99", "Google Chrome";v="127", "Chromium";v="127"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "Referer": "https://www.natura.com.pe/"
        }

    # 1. Intentar Petición Directa
    try:
        session = requests.Session()
        resp = session.get(url_destino, headers=headers, timeout=15, verify=False)
        if resp.status_code == 200 and len(resp.text) > 2000:
            safe_log(f"🌐 [NATURA] Petición directa exitosa ({len(resp.text)} bytes).", "info")
            return resp.text
        else:
            safe_log(f"⚠️ [NATURA] Petición directa devuelta con estado HTTP {resp.status_code} (Longitud: {len(resp.text)} bytes).", "warning")
    except Exception as e:
        safe_log(f"⚠️ [NATURA] Fallo en conexión directa: {str(e)}", "warning")

    # 2. Respaldo a ScraperAPI si la petición directa fue bloqueada
    key = obtener_key_natura()
    if not key:
        safe_log("🛑 [NATURA] La petición directa falló y no se encontró API Key de ScraperAPI configurada.", "error")
        return None

    safe_log("🔄 [NATURA] Intentando descarga a través de ScraperAPI...", "info")
    try:
        payload = {'api_key': key, 'url': url_destino, 'render': 'false'}
        resp_sc = requests.get('http://api.scraperapi.com', params=payload, headers=headers, timeout=25)
        if resp_sc.status_code == 200 and len(resp_sc.text) > 1000:
            safe_log(f"🌐 [NATURA] ScraperAPI respuesta exitosa ({len(resp_sc.text)} bytes).", "info")
            return resp_sc.text
        else:
            safe_log(f"🛑 [NATURA] ScraperAPI devolvió estado {resp_sc.status_code}.", "error")
    except Exception as e:
        safe_log(f"🛑 [NATURA] Error al conectar con ScraperAPI: {str(e)}", "error")

    return None

# -------------------------
# Utilidades de Limpieza
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

def extraer_producto_desde_dict(data):
    if not isinstance(data, dict):
        return None

    name = str(data.get('productName') or data.get('name') or data.get('title') or data.get('brand') or '').strip()
    link_rel = str(data.get('link') or data.get('slug') or data.get('url') or '').strip()
    pid = str(data.get('id') or data.get('productId') or '').strip()

    if not name and not pid:
        return None

    link_final = ""
    if link_rel and '/p/' in link_rel.lower():
        link_final = link_rel if link_rel.startswith('http') else f"https://www.natura.com.pe{link_rel}"
    elif pid:
        clean_pid = pid if 'NATPER-' in pid else f"NATPER-{pid}"
        link_final = f"https://www.natura.com.pe/p/producto/{clean_pid}"

    if not link_final:
        return None

    link_final = link_final.split('?')[0].split('#')[0]

    spot_price = 0.0
    list_price = 0.0

    price_obj = data.get('price')
    if isinstance(price_obj, dict):
        spot_price = float(price_obj.get('spotPrice') or price_obj.get('price') or price_obj.get('value') or 0.0)
        list_price = float(price_obj.get('listPrice') or price_obj.get('list') or price_obj.get('regularPrice') or spot_price)

    if spot_price <= 0:
        spot_price = float(data.get('spotPrice') or data.get('price') or data.get('spot_price') or data.get('value') or 0.0)

    if list_price <= 0:
        list_price = float(data.get('listPrice') or data.get('list_price') or data.get('regularPrice') or spot_price)

    items = data.get('items')
    img_url = str(data.get('imageUrl') or data.get('image') or '')

    if isinstance(items, list) and len(items) > 0:
        first_item = items[0]
        if not img_url:
            imgs = first_item.get('images', [])
            if isinstance(imgs, list) and len(imgs) > 0:
                img_url = str(imgs[0].get('imageUrl') or imgs[0].get('url') or '')
        sellers = first_item.get('sellers', [])
        if isinstance(sellers, list) and len(sellers) > 0:
            comm = sellers[0].get('commertialOffer') or sellers[0].get('commercialOffer') or {}
            if spot_price <= 0:
                spot_price = float(comm.get('Price') or comm.get('spotPrice') or 0.0)
            if list_price <= 0 or list_price == spot_price:
                list_price = float(comm.get('ListPrice') or spot_price)

    if spot_price > 0:
        clean_n = name.replace("NATURA -", "").replace("NATURA", "").strip("- ").upper()
        if not clean_n:
            m_slug = re.search(r'/p/([^/]+)/', link_final)
            if m_slug:
                clean_n = " ".join([w.capitalize() for w in m_slug.group(1).split('-') if not w.isdigit()]).upper()

        if clean_n and 'AGREGAR' not in clean_n:
            nombre_final = f"NATURA - {clean_n}"
            volumen = extraer_volumen(name)
            return {
                "nombre": nombre_final,
                "precio": spot_price,
                "precio_regular": max(list_price, spot_price),
                "descuento_pct": calcular_descuento(spot_price, max(list_price, spot_price)),
                "volumen": volumen,
                "tags": [],
                "link": link_final,
                "img": img_url
            }

    return None

# -------------------------
# Extracción desde Next.js Stream
# -------------------------
def extraer_desde_next_stream(html_text, productos_map, limite):
    clean_html = html_text.replace(r'\/', '/').replace(r'\"', '"').replace('&quot;', '"').replace('&amp;', '&')

    natper_indices = [m.start() for m in re.finditer(r'NATPER-\d+', clean_html, re.I)]

    for idx in natper_indices:
        win_start = max(0, idx - 800)
        win_end = min(len(clean_html), idx + 800)
        sub = clean_html[win_start:win_end]

        brace_starts = [i for i, ch in enumerate(sub) if ch == '{']
        for b_start in brace_starts:
            if b_start < (idx - win_start):
                depth = 0
                for i in range(b_start, len(sub)):
                    if sub[i] == '{': depth += 1
                    elif sub[i] == '}': depth -= 1
                    if depth == 0:
                        candidate = sub[b_start : i + 1]
                        if "NATPER-" in candidate:
                            try:
                                data = json.loads(candidate)
                                prod = extraer_producto_desde_dict(data)
                                if prod and prod['precio'] <= limite:
                                    link = prod['link']
                                    if link not in productos_map:
                                        productos_map[link] = prod
                                    else:
                                        if prod['precio_regular'] > productos_map[link]['precio_regular']:
                                            productos_map[link]['precio_regular'] = prod['precio_regular']
                                            productos_map[link]['descuento_pct'] = calcular_descuento(productos_map[link]['precio'], prod['precio_regular'])
                                        if not productos_map[link]['img'] and prod['img']:
                                            productos_map[link]['img'] = prod['img']
                            except Exception:
                                pass
                        break

# -------------------------
# Extracción DOM Exacta (IDs de DevTools)
# -------------------------
def extraer_desde_dom_grid(soup, productos_map, limite):
    cards = soup.find_all(['article', 'div'], attrs={'data-testid': re.compile(r'product-card', re.I)}) or \
            soup.find_all(['article', 'div'], attrs={'id': re.compile(r'product-card', re.I)}) or \
            soup.find_all('article', class_=re.compile(r'h-full', re.I))

    if not cards:
        cards = [c for c in soup.find_all(['div', 'article']) if c.find('a', href=lambda h: h and '/p/' in str(h).lower())]

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

            # 1. Precio "Por" (Oferta) -> span#product-price-por
            precio_oferta = 0.0
            el_por = card.find(attrs={'id': 'product-price-por'}) or \
                     card.find(attrs={'data-testid': 'product-price-por'}) or \
                     card.find(attrs={'aria-label': 'product-price-por'})
            if el_por:
                precio_oferta = limpiar_precio(el_por.get_text())

            # 2. Precio "De" (Regular) -> p#product-price-de
            precio_regular = 0.0
            el_de = card.find(attrs={'id': 'product-price-de'}) or \
                    card.find(attrs={'aria-label': 'product-price-de'}) or \
                    card.find(attrs={'data-testid': 'product-price-de'}) or \
                    card.find('p', class_=re.compile(r'line-through', re.I))
            if el_de:
                precio_regular = limpiar_precio(el_de.get_text())

            price_container = card.find(attrs={'id': re.compile(r'product-price', re.I)}) or card
            if precio_oferta <= 0 or precio_regular <= 0:
                texto_precio = price_container.get_text(separator=' ', strip=True)
                precios_found = re.findall(r'(?:S/\.?\s*|PEN\s*|S/)\s*([\d\.,]+)', texto_precio)
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
                if link_final not in productos_map:
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
                else:
                    productos_map[link_final]["precio"] = precio_oferta
                    productos_map[link_final]["precio_regular"] = max(precio_regular, precio_oferta)
                    productos_map[link_final]["descuento_pct"] = calcular_descuento(precio_oferta, productos_map[link_final]["precio_regular"])
                    if not productos_map[link_final]["img"] and img_src:
                        productos_map[link_final]["img"] = img_src
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

    # 1. Extracción desde la trama Next.js
    extraer_desde_next_stream(html_content, productos_map, limite)

    # 2. Extracción y sincronización exacta desde el DOM
    soup = BeautifulSoup(html_content, 'html.parser')
    extraer_desde_dom_grid(soup, productos_map, limite)

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [NATURA] Se extrajeron un total de {len(productos_finales)} ofertas válidas.", "success")
        for idx_p, p_item in enumerate(productos_finales[:5], 1):
            safe_log(f"   📌 #{idx_p}: {p_item['nombre']} -> Oferta: S/ {p_item['precio']:.2f} | Regular: S/ {p_item['precio_regular']:.2f}", "info")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
