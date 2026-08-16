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
# Descarga HTML (Directa o ScraperAPI)
# -------------------------
def descargar_html(url_destino, headers=None):
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "Referer": "https://www.natura.com.pe/"
        }

    # 1. Petición directa
    try:
        session = requests.Session()
        resp = session.get(url_destino, headers=headers, timeout=12, verify=False)
        if resp.status_code == 200 and len(resp.text) > 2000:
            safe_log(f"🌐 [NATURA] Petición directa exitosa ({len(resp.text)} bytes).", "info")
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
                safe_log(f"🌐 [NATURA] ScraperAPI respuesta exitosa ({len(resp_sc.text)} bytes).", "info")
                return resp_sc.text
        except Exception as e:
            safe_log(f"🛑 [NATURA] Error ScraperAPI: {str(e)}", "error")

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

# -------------------------
# Escáner de Texto Completo (Garantiza los 28 productos)
# -------------------------
def extraer_todos_los_productos_del_html(html_text, productos_map, limite):
    """
    Escanea todo el HTML reconociendo los patrones de enlace /p/slug/NATPER-ID.
    """
    clean_html = html_text.replace(r'\/', '/').replace(r'\"', '"').replace('\\"', '"').replace('&quot;', '"').replace('&amp;', '&')

    # Extraer todos los enlaces de producto válidos
    enlaces_raw = set(re.findall(r'/p/[a-zA-Z0-9\-_%]+/NATPER-\d+', clean_html, re.I))
    safe_log(f"🔎 [NATURA] Se detectaron {len(enlaces_raw)} enlaces de producto NATPER en el código fuente.", "info")

    for rel_link in enlaces_raw:
        try:
            link_final = f"https://www.natura.com.pe{rel_link}"

            match_id = re.search(r'NATPER-(\d+)', rel_link, re.I)
            if not match_id:
                continue
            natper_id = match_id.group(1)

            pos = clean_html.find(f"NATPER-{natper_id}")
            if pos == -1:
                pos = clean_html.find(rel_link)

            # Ventana de contexto amplia (+- 800 caracteres)
            sub = clean_html[max(0, pos - 800): min(len(clean_html), pos + 800)] if pos != -1 else ""

            # 1. Nombre
            nombre_raw = ""
            m_name = re.search(r'(?:"productName"|"name"|"title"|"brand")\s*:\s*"([^"]{3,120})"', sub, re.I)
            if m_name and 'NATPER' not in m_name.group(1) and 'AGREGAR' not in m_name.group(1).upper():
                nombre_raw = m_name.group(1)
            else:
                slug_part = rel_link.split('/p/')[1].split('/NATPER-')[0]
                words = [w.capitalize() for w in slug_part.split('-') if not w.isdigit()]
                nombre_raw = " ".join(words)

            nombre_final = limpiar_nombre(nombre_raw)
            if not nombre_final:
                continue

            # 2. Precios
            p_o = 0.0
            p_r = 0.0

            spot_matches = re.findall(r'(?:"spotPrice"|"price"|"Price"|"value"|"spot_price")\s*:\s*(\d+(?:\.\d+)?)', sub)
            list_matches = re.findall(r'(?:"listPrice"|"ListPrice"|"list_price"|"regularPrice")\s*:\s*(\d+(?:\.\d+)?)', sub)

            if spot_matches:
                v_spot = [float(x) for x in spot_matches if float(x) > 0]
                if v_spot:
                    p_o = v_spot[0]

            if list_matches:
                v_list = [float(x) for x in list_matches if float(x) > 0]
                if v_list:
                    p_r = v_list[0]

            if p_o <= 0 or p_r <= 0:
                txt_matches = re.findall(r'(?:S/\.?\s*|PEN\s*|S/)\s*([\d\.,]+)', sub)
                v_txt = [limpiar_precio(tp) for tp in txt_matches if limpiar_precio(tp) > 0]
                if v_txt:
                    if p_o <= 0:
                        p_o = min(v_txt)
                    if p_r <= 0:
                        p_r = max(v_txt)

            if p_r < p_o or p_r <= 0:
                p_r = p_o

            # 3. Imagen CDN
            p_img = re.compile(rf'(https?://[^\s"\'>\\]+?NATPER-{natper_id}[^\s"\'>\\]*?\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'>\\]*)?)', re.I)
            m_img = p_img.search(clean_html)
            img_url = m_img.group(1) if m_img else ""

            volumen = extraer_volumen(nombre_raw)
            descuento_pct = calcular_descuento(p_o, p_r)

            if p_o > 0 and p_o <= limite:
                if link_final not in productos_map:
                    productos_map[link_final] = {
                        "nombre": nombre_final,
                        "precio": p_o,
                        "precio_regular": p_r,
                        "descuento_pct": descuento_pct,
                        "volumen": volumen,
                        "tags": [],
                        "link": link_final,
                        "img": img_url
                    }
                else:
                    if p_r > productos_map[link_final]["precio_regular"]:
                        productos_map[link_final]["precio_regular"] = p_r
                        productos_map[link_final]["descuento_pct"] = calcular_descuento(productos_map[link_final]["precio"], p_r)
                    if not productos_map[link_final]["img"] and img_url:
                        productos_map[link_final]["img"] = img_url
        except Exception:
            continue

# -------------------------
# Sincronización con el DOM
# -------------------------
def extraer_desde_dom_grid(soup, productos_map, limite):
    cards = soup.find_all(['article', 'div'], attrs={'data-testid': re.compile(r'product-card', re.I)}) or \
            soup.find_all(['article', 'div'], attrs={'id': re.compile(r'product-card', re.I)})

    for card in cards:
        try:
            a_tag = card.find('a', href=lambda h: h and '/p/' in str(h).lower()) or (card if card.name == 'a' else None)
            if not a_tag or not a_tag.get('href'):
                continue

            href = a_tag['href'].strip()
            link_final = urljoin("https://www.natura.com.pe", href).split('?')[0].split('#')[0]

            el_por = card.find(attrs={'id': 'product-price-por'}) or card.find(attrs={'data-testid': 'product-price-por'})
            el_de = card.find(attrs={'id': 'product-price-de'}) or card.find(attrs={'aria-label': 'product-price-de'}) or card.find('p', class_=re.compile(r'line-through', re.I))

            p_o = limpiar_precio(el_por.get_text()) if el_por else 0.0
            p_r = limpiar_precio(el_de.get_text()) if el_de else 0.0

            if link_final in productos_map:
                if p_o > 0:
                    productos_map[link_final]["precio"] = p_o
                if p_r > 0:
                    productos_map[link_final]["precio_regular"] = max(p_r, productos_map[link_final]["precio"])
                productos_map[link_final]["descuento_pct"] = calcular_descuento(productos_map[link_final]["precio"], productos_map[link_final]["precio_regular"])
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

    # 1. Escaneo completo de enlaces NATPER
    extraer_todos_los_productos_del_html(html_content, productos_map, limite)

    # 2. Refinamiento DOM
    soup = BeautifulSoup(html_content, 'html.parser')
    extraer_desde_dom_grid(soup, productos_map, limite)

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [NATURA] ¡Éxito! Se indexaron un total de {len(productos_finales)} ofertas de la grilla.", "success")
        for idx_p, p_item in enumerate(productos_finales[:5], 1):
            safe_log(f"   📌 #{idx_p}: {p_item['nombre']} → Oferta: S/ {p_item['precio']:.2f} | Regular: S/ {p_item['precio_regular']:.2f}", "info")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
