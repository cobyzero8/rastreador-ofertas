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

def limpiar_precio_natura(texto):
    if not texto: return 0.0
    texto = str(texto).replace('&nbsp;', ' ').replace('\xa0', ' ').replace('S/.', '').replace('S/', '').strip()
    match = re.search(r'\d+(?:[.,]\d+)*', texto)
    if match:
        raw = match.group(0).replace(',', '.') if ',' in match.group(0) and '.' not in match.group(0) else match.group(0).replace(',', '')
        try: return float(raw)
        except ValueError: return 0.0
    return 0.0

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

def consultar_vtex_api(search_term, de=0, hasta=49):
    """
    Consulta la API VTEX con parámetro ft (Free Text Search)
    """
    api_url = f"https://www.natura.com.pe/api/catalog_system/pub/products/search?ft={urllib.parse.quote(search_term)}&_from={de}&_to={hasta}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
        "Referer": "https://www.natura.com.pe/"
    }

    try:
        resp = requests.get(api_url, headers=headers, timeout=10, verify=False)
        if resp.status_code == 200 and len(resp.content) > 50:
            return resp.json()
    except Exception:
        pass
    return []

def consultar_natura_html(url_destino):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9",
        "Referer": "https://www.natura.com.pe/"
    }

    # Intentar directo gratis
    try:
        resp = requests.get(url_destino, headers=headers, timeout=10, verify=False)
        if resp.status_code == 200 and len(resp.text) > 2000:
            return resp
    except Exception:
        pass

    # Respaldo con ScraperAPI
    key = obtener_key_natura()
    if key:
        try:
            payload = {'api_key': key, 'url': url_destino, 'country_code': 'us', 'render': 'false'}
            resp_sc = requests.get('http://api.scraperapi.com', params=payload, headers=headers, timeout=30)
            if resp_sc.status_code == 200:
                return resp_sc
        except Exception:
            pass
    return None

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

def extraer_imagen_natura(card, a_tag, href, full_html):
    card_str = str(card).replace('\\/', '/')
    comb = card_str + " " + str(a_tag)

    match_id = re.search(r'NATPER-(\d+)', href + " " + comb, re.I)
    if match_id:
        natper_id = match_id.group(1)
        p1 = re.compile(rf'(https?://[^\s"\'>\\]+?NATPER-{natper_id}[^\s"\'>\\]*?\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'>\\]*)?)', re.I)
        m1 = p1.search(full_html)
        if m1: return normalizar_url_imagen(m1.group(1))

    match_dw = re.search(r'(https?://production\.na01\.natura\.com/dw/image/v2/[^\s"\'>\\]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'>\\]*)?)', comb, re.I)
    if match_dw: return normalizar_url_imagen(match_dw.group(1))

    return ""

def motor_natura(url, limite=999999.0, headers=None):
    """
    Motor híbrido: Intenta API VTEX -> Si falla, salta a Escáner HTML de Respaldo.
    """
    productos_map = {}
    url_clean = sanitizar_url(url)
    parsed = urllib.parse.urlparse(url_clean)
    cat_slug = parsed.path.strip('/').replace('c/', '').replace('-', ' ')

    safe_log(f"🚀 [NATURA] Intentando extraer vía API para término: '{cat_slug}'...", "info")

    # ==========================================
    # PASO 1: Intentar API VTEX
    # ==========================================
    data_json = consultar_vtex_api(cat_slug, de=0, hasta=49)
    if data_json and isinstance(data_json, list):
        for prod in data_json:
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
                    if images and isinstance(images, list):
                        img_url = images[0].get('imageUrl', '')

                    sellers = first_item.get('sellers', [])
                    if sellers and isinstance(sellers, list):
                        comm = sellers[0].get('commertialOffer', {}) or sellers[0].get('commercialOffer', {})
                        p_o = float(comm.get('Price') or comm.get('spotPrice') or 0.0)
                        p_r = float(comm.get('ListPrice') or p_o)

                if p_o > 0:
                    procesar_producto_acumulativo(productos_map, link_final, raw_name, p_o, p_r, img_url, limite)
            except Exception:
                continue

    # ==========================================
    # PASO 2: Respaldo Escáner HTML (Si la API devuelve vacíos)
    # ==========================================
    if not productos_map:
        safe_log("⚠️ [NATURA API] No se obtuvieron resultados de la API. Activando escáner HTML de respaldo...", "warning")
        resp = consultar_natura_html(url_clean)
        if resp and resp.text:
            full_html = resp.text
            soup = BeautifulSoup(full_html, 'html.parser')
            enlaces_p = soup.find_all('a', href=lambda h: h and '/p/' in str(h).lower())

            for a_tag in enlaces_p:
                try:
                    href = a_tag['href'].strip()
                    if not href or any(x in href.lower() for x in ['/cart', '/checkout', '/login', '/mi-cuenta']):
                        continue

                    link_final = urljoin("https://www.natura.com.pe", href).split('?')[0]
                    card = a_tag.find_parent(['div', 'article', 'li']) or a_tag

                    img_el = card.find('img')
                    nombre_raw = img_el.get('alt', '').strip() if img_el and img_el.get('alt') else a_tag.get_text(strip=True)

                    el_por = card.find(id=lambda i: i and 'product-price-por' in str(i).lower())
                    el_de = card.find(id=lambda i: i and 'product-price-de' in str(i).lower())

                    p_o = limpiar_precio_natura(el_por.get_text()) if el_por else 0.0
                    p_r = limpiar_precio_natura(el_de.get_text()) if el_de else p_o

                    if p_o <= 0:
                        texto_card = card.get_text(separator=' ', strip=True)
                        precios_num = [limpiar_precio_natura(p) for p in re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_card) if limpiar_precio_natura(p) > 0]
                        if precios_num:
                            p_o = sorted(list(set(precios_num)))[0]
                            p_r = sorted(list(set(precios_num)))[-1]

                    img_url = extraer_imagen_natura(card, a_tag, href, full_html)
                    procesar_producto_acumulativo(productos_map, link_final, nombre_raw, p_o, p_r, img_url, limite)
                except Exception:
                    continue

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [NATURA] ¡Éxito! Se indexaron {len(productos_finales)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
