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
    Garantiza que la URL contenga pageSize=48 para solicitar el catálogo completo.
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

def consultar_natura_html(url_destino):
    """
    Consulta rápida del HTML original de la página de Natura.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://www.natura.com.pe/"
    }

    # Intento 1: Conexión directa
    try:
        resp = requests.get(url_destino, headers=headers, timeout=10, verify=False)
        if resp.status_code == 200 and len(resp.text) > 2000:
            return resp.text
    except Exception:
        pass

    # Intento 2: Respaldo ScraperAPI (Modo rápido, 1 solo crédito)
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

def extraer_todos_los_productos_natura(raw_html, limite=500.0):
    """
    Sanea la transmisión Next.js RSC y extrae la totalidad de productos de la grilla principal.
    """
    productos_map = {}

    if not raw_html or len(raw_html) < 100:
        return []

    # PASO CLAVE: Desescapar la sintaxis de Next.js App Router (self.__next_f.push)
    clean_html = raw_html.replace(r'\/', '/').replace(r'\"', '"').replace('&quot;', '"').replace('&amp;', '&')

    # 1. Extracción de Objetos JSON estructurados en las tramas RSC
    natper_matches = list(re.finditer(r'NATPER-\d+', clean_html, re.I))
    for m in natper_matches:
        start_pos = m.start()
        left = clean_html.rfind('{', max(0, start_pos - 700), start_pos)
        right = clean_html.find('}', start_pos, min(len(clean_html), start_pos + 700))

        if left != -1 and right != -1:
            json_str = clean_html[left : right + 1]
            try:
                data = json.loads(json_str)
                name = str(data.get('productName') or data.get('name') or data.get('title') or '').strip()
                link_rel = str(data.get('link') or data.get('slug') or data.get('url') or '').strip()

                if name and link_rel and '/p/' in link_rel.lower():
                    link_final = link_rel if link_rel.startswith('http') else f"https://www.natura.com.pe{link_rel}"
                    link_final = link_final.split('?')[0].split('#')[0]

                    price = float(data.get('spotPrice') or data.get('price') or data.get('spot_price') or 0.0)
                    list_price = float(data.get('listPrice') or data.get('list_price') or price)
                    img_url = str(data.get('imageUrl') or data.get('image') or '')

                    clean_n = name.replace("NATURA -", "").replace("NATURA", "").strip("- ").upper()
                    if len(clean_n) >= 3 and 'AGREGAR' not in clean_n:
                        nombre_final = f"NATURA - {clean_n}"
                        if 0 < price <= limite and link_final not in productos_map:
                            productos_map[link_final] = {
                                "nombre": nombre_final,
                                "precio": price,
                                "precio_regular": max(list_price, price),
                                "link": link_final,
                                "img": img_url
                            }
            except Exception:
                pass

    # 2. Escaneo por Expresión Regular de Enlaces /p/.../NATPER-XXXXX
    p_links = set(re.findall(r'/p/[a-zA-Z0-9\-_%]+/NATPER-\d+', clean_html, re.I))

    for rel_link in p_links:
        try:
            link_final = f"https://www.natura.com.pe{rel_link}"
            if link_final in productos_map and productos_map[link_final]["precio"] > 0 and productos_map[link_final]["img"]:
                continue

            match_id = re.search(r'NATPER-(\d+)', rel_link, re.I)
            if not match_id: continue
            natper_id = match_id.group(1)

            pos = clean_html.find(f"NATPER-{natper_id}")
            if pos == -1: pos = clean_html.find(rel_link)

            sub = clean_html[max(0, pos - 400): min(len(clean_html), pos + 400)] if pos != -1 else ""

            # Nombre
            m_name = re.search(r'(?:"productName"|"name"|"title")\s*:\s*"([^"]{3,120})"', sub, re.I)
            nombre_raw = ""
            if m_name and 'NATPER' not in m_name.group(1) and 'AGREGAR' not in m_name.group(1).upper():
                nombre_raw = m_name.group(1)
            else:
                slug_part = rel_link.split('/p/')[1].split('/NATPER-')[0]
                words = [w.capitalize() for w in slug_part.split('-') if not w.isdigit()]
                nombre_raw = " ".join(words)

            clean_n = nombre_raw.replace("NATURA -", "").replace("NATURA", "").strip("- ").upper()
            if not clean_n or len(clean_n) < 3 or clean_n in ['COMPRAR', 'VER MÁS', 'AGREGAR', 'AGREGAR A MI BOLSA']:
                continue
            nombre_final = f"NATURA - {clean_n}"

            # Precios
            p_o = 0.0
            p_r = 0.0
            if sub:
                spot_matches = re.findall(r'(?:"spotPrice"|"price"|"Price"|"value")\s*:\s*(\d+(?:\.\d+)?)', sub)
                list_matches = re.findall(r'(?:"listPrice"|"ListPrice")\s*:\s*(\d+(?:\.\d+)?)', sub)

                if spot_matches:
                    valid_spot = [float(x) for x in spot_matches if float(x) > 0]
                    if valid_spot: p_o = valid_spot[0]

                if list_matches:
                    valid_list = [float(x) for x in list_matches if float(x) > 0]
                    if valid_list: p_r = valid_list[0]

                if p_o <= 0:
                    txt_matches = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d+[\d\.,]*)', sub)
                    valid_prices = []
                    for tm in txt_matches:
                        raw_num = tm.replace(',', '') if ',' in tm and '.' in tm else tm.replace(',', '.')
                        try:
                            val = float(raw_num)
                            if val > 0: valid_prices.append(val)
                        except ValueError: pass
                    if valid_prices:
                        p_o = min(valid_prices)
                        p_r = max(valid_prices)

            # Imagen
            p_img = re.compile(rf'(https?://[^\s"\'>\\]+?NATPER-{natper_id}[^\s"\'>\\]*?\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'>\\]*)?)', re.I)
            m_img = p_img.search(clean_html)
            img_url = m_img.group(1) if m_img else ""

            if p_o > 0 and p_o <= limite:
                if link_final not in productos_map:
                    productos_map[link_final] = {
                        "nombre": nombre_final,
                        "precio": p_o,
                        "precio_regular": max(p_r, p_o),
                        "link": link_final,
                        "img": img_url
                    }
                else:
                    if not productos_map[link_final]["img"] and img_url:
                        productos_map[link_final]["img"] = img_url
        except Exception:
            continue

    return list(productos_map.values())

def motor_natura(url, limite=999999.0, headers=None):
    """
    Motor principal de extracción para Natura Perú.
    """
    url_base = sanitizar_url(url)
    url_final = asegurar_pagesize(url_base, page_size=48)

    safe_log(f"🚀 [NATURA] Consultando catálogo completo: {url_final}", "info")

    html_content = consultar_natura_html(url_final)
    if not html_content:
        safe_log("🛑 [NATURA] No se obtuvo contenido HTML de la página.", "error")
        return []

    productos_finales = extraer_todos_los_productos_natura(html_content, limite)

    if productos_finales:
        safe_log(f"✅ [NATURA] ¡Éxito! Se indexaron {len(productos_finales)} ofertas reales de la grilla principal.", "success")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
