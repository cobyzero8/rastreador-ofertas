import os
import re
import json
import logging
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

# Silenciar advertencias de Streamlit en CLI
os.environ["STREAMLIT_LOG_LEVEL"] = "error"
logging.getLogger("streamlit").setLevel(logging.ERROR)
logging.getLogger("streamlit.runtime.scriptrunner.script_runner").setLevel(logging.ERROR)

from utils import sanitizar_url, safe_log

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def obtener_key_ripley():
    key = os.environ.get("SCRAPERAPI_RIPLEY_KEY") or os.environ.get("SCRAPERAPI_KEY")
    if not key:
        try:
            from streamlit.runtime.scriptrunner import get_script_run_ctx
            if get_script_run_ctx() is not None:
                import streamlit as st
                if hasattr(st, "secrets"):
                    key = st.secrets.get("SCRAPERAPI_RIPLEY_KEY") or st.secrets.get("SCRAPERAPI_KEY")
        except Exception:
            pass
    return key.strip() if key else None

# -------------------------
# Descarga HTML con Retry y Timeout Extendido
# -------------------------
def descargar_html_ripley(url_destino, headers=None):
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Referer": "https://simple.ripley.com.pe/"
        }

    # 1. Petición directa (Rápida)
    try:
        session = requests.Session()
        resp = session.get(url_destino, headers=headers, timeout=10, verify=False)
        if resp.status_code == 200 and len(resp.text) > 3000:
            safe_log(f"🌐 [RIPLEY] Petición directa exitosa ({len(resp.text)} bytes).", "info")
            return resp.text
    except Exception:
        pass

    # 2. Respaldo ScraperAPI con 2 reintentos y timeout de 60s
    key = obtener_key_ripley()
    if key:
        safe_log("🔄 [RIPLEY] Consultando mediante ScraperAPI (timeout: 60s)...", "info")
        payload = {'api_key': key, 'url': url_destino, 'render': 'false'}
        
        for intento in range(1, 3):
            try:
                resp_sc = requests.get('https://api.scraperapi.com', params=payload, headers=headers, timeout=60)
                if resp_sc.status_code == 200 and len(resp_sc.text) > 1000:
                    safe_log(f"🌐 [RIPLEY] ScraperAPI respuesta exitosa ({len(resp_sc.text)} bytes).", "info")
                    return resp_sc.text
                else:
                    safe_log(f"⚠️ [RIPLEY] ScraperAPI intento {intento} devolvió estado {resp_sc.status_code}.", "warning")
            except requests.exceptions.Timeout:
                safe_log(f"⚠️ [RIPLEY] Timeout en intento {intento}/2 de ScraperAPI.", "warning")
            except Exception as e:
                safe_log(f"🛑 [RIPLEY] Error en intento {intento}: {str(e)}", "error")

    return None

# -------------------------
# Utilidades
# -------------------------
def extraer_monto_num(texto):
    if not texto:
        return 0.0
    if isinstance(texto, (int, float)):
        return float(texto)
    m = re.search(r'(?:S/\.?\s*|PEN\s*|S/)?\s*(\d+(?:[.,]\d+)?)', str(texto))
    if not m:
        return 0.0
    raw = m.group(1)
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

def sanitizar_imagen_ripley(img_raw):
    if not img_raw:
        return ""
    img_str = str(img_raw).strip()
    if ' ' in img_str:
        img_str = img_str.split(' ')[0].strip()
    if img_str.startswith('//'):
        img_str = f"https:{img_str}"
    elif img_str.startswith('/'):
        img_str = f"https://simple.ripley.com.pe{img_str}"
    return img_str

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
    if not clean or len(clean) < 2 or clean.upper() in ['BÚSQUEDA', 'CALZADO', 'DEPORTE']:
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
# Extracción JSON y DOM
# -------------------------
def buscar_arreglo_productos_json(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ['products', 'results', 'items'] and isinstance(v, list) and len(v) > 0:
                primer_elem = v[0]
                if isinstance(primer_elem, dict) and any(x in primer_elem for x in ['name', 'fullTitle', 'uniqueID', 'partNumber', 'sKU']):
                    return v
            res = buscar_arreglo_productos_json(v)
            if res:
                return res
    elif isinstance(obj, list):
        for item in obj:
            res = buscar_arreglo_productos_json(item)
            if res:
                return res
    return []

def extraer_precios_json(p_dict):
    prices = p_dict.get('prices') or p_dict.get('price') or {}
    candidatos = []

    if isinstance(prices, dict):
        for k in ['cardPrice', 'offerPrice', 'discountPrice', 'ripleyPrice', 'salePrice', 'lowPrice', 'minPrice', 'listPrice', 'normalPrice', 'maxPrice', 'price']:
            val = extraer_monto_num(prices.get(k))
            if val > 0:
                candidatos.append(val)
        if not candidatos:
            for v in prices.values():
                val = extraer_monto_num(v)
                if val > 0:
                    candidatos.append(val)
    elif isinstance(prices, (int, float)):
        val = float(prices)
        if val > 0:
            candidatos.append(val)

    if candidatos:
        return min(candidatos), max(candidatos)
    return 0.0, 0.0

def extraer_desde_next_data(soup, productos_map, limite):
    script_next = soup.find('script', id='__NEXT_DATA__')
    if not script_next or not script_next.string:
        return

    try:
        json_data = json.loads(script_next.string)
        productos_raw = buscar_arreglo_productos_json(json_data.get('props', {}))
        safe_log(f"📦 [RIPLEY JSON] Se aislaron {len(productos_raw)} productos en __NEXT_DATA__.", "info")

        for idx, p in enumerate(productos_raw, 1):
            try:
                name = p.get('name') or p.get('fullTitle') or p.get('title') or ''
                rel_url = p.get('url') or p.get('fullUrl') or p.get('path') or ''
                unique_id = str(p.get('uniqueID') or p.get('partNumber') or p.get('sKU') or idx).strip()

                if rel_url and ('/p/' in rel_url.lower() or '-p' in rel_url.lower()):
                    link_final = rel_url if rel_url.startswith('http') else f"https://simple.ripley.com.pe{rel_url}"
                elif rel_url and rel_url.startswith('/'):
                    link_final = f"https://simple.ripley.com.pe{rel_url}"
                else:
                    link_final = f"https://simple.ripley.com.pe/p/{unique_id}"

                link_final = link_final.split('?')[0].split('#')[0]

                p_oferta, p_regular = extraer_precios_json(p)
                if p_regular < p_oferta or p_regular <= 0:
                    p_regular = p_oferta

                img_url = p.get('fullImage') or p.get('thumbnail') or p.get('image') or ''
                if not img_url:
                    imgs = p.get('images')
                    if isinstance(imgs, list) and len(imgs) > 0:
                        first = imgs[0]
                        if isinstance(first, str):
                            img_url = first
                        elif isinstance(first, dict):
                            img_url = first.get('url') or first.get('fullImage') or first.get('src') or ''

                img_final = sanitizar_imagen_ripley(img_url)
                nombre_final = limpiar_nombre(name)
                descuento_pct = calcular_descuento(p_oferta, p_regular)

                if p_oferta > 0 and nombre_final:
                    productos_map[link_final] = {
                        "nombre": nombre_final,
                        "precio": p_oferta,
                        "precio_regular": p_regular,
                        "descuento_pct": descuento_pct,
                        "link": link_final,
                        "img": img_final
                    }
            except Exception:
                continue
    except Exception as e:
        safe_log(f"⚠️ [RIPLEY JSON] Error en __NEXT_DATA__: {str(e)}", "warning")

def extraer_desde_dom_ripley(soup, productos_map, limite):
    cards = soup.find_all(['div', 'article'], class_=re.compile(r'\bcatalog-product-item\b|product-item', re.I))
    if not cards:
        cards = [a.parent for a in soup.find_all('a', href=re.compile(r'/pmp|-p|/zapatillas', re.I)) if a.parent]

    safe_log(f"🔎 [RIPLEY DOM] Tarjetas de producto procesadas: {len(cards)}", "info")

    for card in cards:
        try:
            a_tag = card if card.name == 'a' else card.find('a', href=True)
            if not a_tag or not a_tag.get('href'):
                continue

            href = a_tag['href'].strip()
            link_final = href if href.startswith('http') else f"https://simple.ripley.com.pe{href}"
            link_final = link_final.split('?')[0].split('#')[0]

            img_el = card.find('img', class_=re.compile(r'product-image-img|product-image', re.I)) or card.find('img')
            img_src = ''
            if img_el:
                img_src = img_el.get('src') or img_el.get('srcset') or img_el.get('data-src') or ''
            img_final = sanitizar_imagen_ripley(img_src)

            nombre_el = card.find(class_=re.compile(r'product-item-name|catalog-product-details__name', re.I)) or card.find('p', title=True)
            nombre_raw = nombre_el.get_text(strip=True) if nombre_el else (img_el.get('alt') if img_el else '')
            nombre_final = limpiar_nombre(nombre_raw)

            if not nombre_final:
                continue

            texto_card = card.get_text(separator=' ', strip=True)
            precios_encontrados = re.findall(r'(?:S/\.?\s*|PEN\s*|S/)\s*([\d\.,]+)', texto_card)
            precios_num = [extraer_monto_num(p) for p in precios_encontrados if extraer_monto_num(p) > 0]

            if not precios_num:
                continue

            p_oferta = min(precios_num)
            p_regular = max(precios_num)
            descuento_pct = calcular_descuento(p_oferta, p_regular)

            if p_oferta > 0:
                if link_final in productos_map:
                    if p_oferta < productos_map[link_final]["precio"]:
                        productos_map[link_final]["precio"] = p_oferta
                        productos_map[link_final]["precio_regular"] = p_regular
                        productos_map[link_final]["descuento_pct"] = descuento_pct
                    if img_final and not productos_map[link_final]["img"]:
                        productos_map[link_final]["img"] = img_final
                else:
                    productos_map[link_final] = {
                        "nombre": nombre_final,
                        "precio": p_oferta,
                        "precio_regular": p_regular,
                        "descuento_pct": descuento_pct,
                        "link": link_final,
                        "img": img_final
                    }
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

    extraer_desde_next_data(soup, productos_map, limite)
    extraer_desde_dom_ripley(soup, productos_map, limite)

    productos_finales = [
        p for p in productos_map.values()
        if 0 < p['precio'] <= limite
    ]

    if productos_finales:
        safe_log(f"✅ [RIPLEY] ¡Éxito! Se indexaron un total de {len(productos_finales)} ofertas válidas bajo S/. {limite:.2f}.", "success")
        for idx_p, p_item in enumerate(productos_finales[:5], 1):
            safe_log(f"   📌 #{idx_p}: {p_item['nombre']} → Oferta: S/ {p_item['precio']:.2f} | Regular: S/ {p_item['precio_regular']:.2f}", "info")
    else:
        safe_log(f"⚠️ [RIPLEY] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
