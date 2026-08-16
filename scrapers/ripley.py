import os
import re
import json
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse
from utils import sanitizar_url, safe_log

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# -------------------------
# Obtención de Claves
# -------------------------
def obtener_key_ripley():
    key = None
    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            key = st.secrets.get("SCRAPERAPI_RIPLEY_KEY") or st.secrets.get("SCRAPERAPI_KEY")
    except Exception:
        pass

    if not key:
        key = os.environ.get("SCRAPERAPI_RIPLEY_KEY") or os.environ.get("SCRAPERAPI_KEY")

    return key.strip() if key else None

# -------------------------
# Descarga HTML
# -------------------------
def descargar_html_ripley(url_destino, headers=None):
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Referer": "https://simple.ripley.com.pe/"
        }

    # 1. Petición directa
    try:
        session = requests.Session()
        resp = session.get(url_destino, headers=headers, timeout=12, verify=False)
        if resp.status_code == 200 and len(resp.text) > 3000:
            safe_log(f"🌐 [RIPLEY] Petición directa exitosa ({len(resp.text)} bytes).", "info")
            return resp.text
    except Exception:
        pass

    # 2. Respaldo ScraperAPI
    key = obtener_key_ripley()
    if key:
        safe_log("🔄 [RIPLEY] Consultando mediante ScraperAPI...", "info")
        try:
            payload = {'api_key': key, 'url': url_destino, 'render': 'false'}
            resp_sc = requests.get('http://api.scraperapi.com', params=payload, headers=headers, timeout=35)
            if resp_sc.status_code == 200 and len(resp_sc.text) > 1000:
                safe_log(f"🌐 [RIPLEY] ScraperAPI respuesta exitosa ({len(resp_sc.text)} bytes).", "info")
                return resp_sc.text
        except Exception as e:
            safe_log(f"🛑 [RIPLEY] Error ScraperAPI: {str(e)}", "error")

    return None

# -------------------------
# Utilidades de Limpieza
# -------------------------
def limpiar_precio(texto):
    if not texto:
        return 0.0
    if isinstance(texto, (int, float)):
        return float(texto)
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
    if up.startswith("RIPLEY -"):
        clean = clean[8:].strip()
    elif up.startswith("RIPLEY"):
        clean = clean[6:].strip()
    clean = clean.lstrip('- ').strip()
    if not clean or len(clean) < 2:
        return ""
    return f"RIPLEY - {clean}"

def calcular_descuento(precio_oferta, precio_regular):
    try:
        if precio_regular and precio_regular > precio_oferta:
            pct = round((1 - (precio_oferta / precio_regular)) * 100, 2)
            return pct if pct > 0 else 0.0
    except Exception:
        pass
    return 0.0

# -------------------------
# Estrategia 1: Extracción JSON (__NEXT_DATA__)
# -------------------------
def extraer_desde_next_data(soup, productos_map, limite):
    script_next = soup.find('script', id='__NEXT_DATA__')
    if not script_next or not script_next.string:
        return

    try:
        json_data = json.loads(script_next.string)

        def buscar_productos(obj):
            if isinstance(obj, dict):
                if 'products' in obj and isinstance(obj['products'], list):
                    return obj['products']
                for v in obj.values():
                    res = buscar_productos(v)
                    if res: return res
            elif isinstance(obj, list):
                for item in obj:
                    res = buscar_productos(item)
                    if res: return res
            return None

        productos_raw = buscar_productos(json_data.get('props', {})) or []

        for p in productos_raw:
            try:
                name = p.get('name') or p.get('fullTitle') or p.get('title') or ''
                rel_url = p.get('url') or p.get('fullUrl') or p.get('path') or ''
                if not name or not rel_url:
                    continue

                link_final = rel_url if rel_url.startswith('http') else f"https://simple.ripley.com.pe{rel_url}"
                link_final = link_final.split('?')[0].split('#')[0]

                prices = p.get('prices') or p.get('price') or {}
                p_tarjeta = 0.0
                p_venta = 0.0
                p_lista = 0.0

                if isinstance(prices, dict):
                    p_tarjeta = limpiar_precio(prices.get('cardPrice') or prices.get('formattedCardPrice'))
                    p_venta = limpiar_precio(prices.get('offerPrice') or prices.get('discountPrice') or prices.get('formattedOfferPrice'))
                    p_lista = limpiar_precio(prices.get('listPrice') or prices.get('normalPrice') or prices.get('formattedListPrice'))

                p_oferta = p_tarjeta if p_tarjeta > 0 else (p_venta if p_venta > 0 else p_lista)
                p_regular = p_lista if p_lista > 0 else max(p_venta, p_tarjeta)

                if p_regular < p_oferta or p_regular <= 0:
                    p_regular = p_oferta

                # Imagen CDN
                img_url = str(p.get('thumbnail') or p.get('fullImage') or p.get('image') or '').strip()
                if not img_url:
                    imgs = p.get('images')
                    if isinstance(imgs, list) and len(imgs) > 0:
                        first = imgs[0]
                        if isinstance(first, str):
                            img_url = first
                        elif isinstance(first, dict):
                            img_url = str(first.get('url') or first.get('fullImage') or first.get('src') or '').strip()

                if img_url.startswith('//'):
                    img_url = f"https:{img_url}"

                nombre_final = limpiar_nombre(name)
                descuento_pct = calcular_descuento(p_oferta, p_regular)

                if p_oferta > 0 and p_oferta <= limite and nombre_final:
                    productos_map[link_final] = {
                        "nombre": nombre_final,
                        "precio": p_oferta,
                        "precio_regular": p_regular,
                        "descuento_pct": descuento_pct,
                        "link": link_final,
                        "img": img_url
                    }
            except Exception:
                continue
    except Exception as e:
        safe_log(f"⚠️ [RIPLEY JSON] Error en __NEXT_DATA__: {str(e)}", "warning")

# -------------------------
# Estrategia 2: Extracción DOM Exacta (DevTools IDs)
# -------------------------
def extraer_desde_dom_ripley(soup, productos_map, limite):
    cards = soup.find_all(['div', 'article', 'a'], class_=re.compile(r'catalog-product-item|product-item', re.I))

    for card in cards:
        try:
            a_tag = card if card.name == 'a' else card.find('a', href=True)
            if not a_tag or not a_tag.get('href'):
                continue

            href = a_tag['href'].strip()
            link_final = href if href.startswith('http') else f"https://simple.ripley.com.pe{href}"
            link_final = link_final.split('?')[0].split('#')[0]

            img_el = card.find('img')
            img_src = img_el.get('src') or img_el.get('data-src') or '' if img_el else ''
            if img_src.startswith('//'):
                img_src = f"https:{img_src}"

            nombre_el = card.find(class_=re.compile(r'product-item-name|catalog-product-details__name', re.I)) or card.find('p', title=True)
            nombre_raw = nombre_el.get_text(strip=True) if nombre_el else (img_el.get('alt') if img_el else '')

            nombre_final = limpiar_nombre(nombre_raw)
            if not nombre_final:
                continue

            # PRECIOS EXACTOS DEVTOOLS (IMÁGENES 2 Y 3)
            # 1. Precio Lista / Real
            el_lista = card.find(class_=re.compile(r'product-price-old-price-container|product-price-strikethrough', re.I))
            p_lista = limpiar_precio(el_lista.get_text()) if el_lista else 0.0

            # 2. Precio Venta / Oferta General
            el_venta = card.find(class_=re.compile(r'product-price-container', re.I))
            p_venta = limpiar_precio(el_venta.get_text()) if el_venta else 0.0

            # 3. Precio Tarjeta Ripley (Oferta Principal)
            el_ripley = card.find(class_=re.compile(r'product-price-ripley-price-container|product-price-color-red', re.I))
            p_ripley = limpiar_precio(el_ripley.get_text()) if el_ripley else 0.0

            # Fallback en caso de etiquetas dinámicas
            if p_ripley <= 0 and p_venta <= 0 and p_lista <= 0:
                texto_card = card.get_text(separator=' ', strip=True)
                precios_found = re.findall(r'(?:S/\.?\s*|PEN\s*|S/)\s*([\d\.,]+)', texto_card)
                precios_num = [limpiar_precio(p) for p in precios_found if limpiar_precio(p) > 0]
                if precios_num:
                    p_venta = min(precios_num)
                    p_lista = max(precios_num) if len(precios_num) > 1 else p_venta

            p_oferta = p_ripley if p_ripley > 0 else (p_venta if p_venta > 0 else p_lista)
            p_regular = p_lista if p_lista > 0 else max(p_venta, p_ripley, p_lista)

            if p_regular < p_oferta or p_regular <= 0:
                p_regular = p_oferta

            descuento_pct = calcular_descuento(p_oferta, p_regular)

            if p_oferta > 0 and p_oferta <= limite:
                if link_final not in productos_map:
                    productos_map[link_final] = {
                        "nombre": nombre_final,
                        "precio": p_oferta,
                        "precio_regular": p_regular,
                        "descuento_pct": descuento_pct,
                        "link": link_final,
                        "img": img_src
                    }
                else:
                    # Sincronización y actualización forzada con el valor DOM más preciso
                    productos_map[link_final]["precio"] = p_oferta
                    productos_map[link_final]["precio_regular"] = p_regular
                    productos_map[link_final]["descuento_pct"] = descuento_pct
                    if not productos_map[link_final]["img"] and img_src:
                        productos_map[link_final]["img"] = img_src
        except Exception:
            continue

# -------------------------
# Motor Principal
# -------------------------
def motor_ripley(url, limite=999999.0, headers=None):
    productos_map = {}
    url_final = sanitizar_url(url)

    safe_log(f"🚀 [RIPLEY] Escaneando catálogo: {url_final}", "info")

    html_content = descargar_html_ripley(url_final, headers=headers)
    if not html_content:
        safe_log("🛑 [RIPLEY] No se pudo obtener el contenido HTML de la página.", "error")
        return []

    soup = BeautifulSoup(html_content, 'html.parser')

    # 1. Extracción desde JSON
    extraer_desde_next_data(soup, productos_map, limite)

    # 2. Extracción y actualización exacta desde el DOM
    extraer_desde_dom_ripley(soup, productos_map, limite)

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [RIPLEY] ¡Éxito! Se indexaron un total de {len(productos_finales)} ofertas válidas.", "success")
        for idx_p, p_item in enumerate(productos_finales[:5], 1):
            safe_log(f"   📌 #{idx_p}: {p_item['nombre']} → Oferta: S/ {p_item['precio']:.2f} | Regular: S/ {p_item['precio_regular']:.2f}", "info")
    else:
        safe_log(f"⚠️ [RIPLEY] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
