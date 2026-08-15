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
    Obtiene la clave de ScraperAPI desde secretos o entorno.
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
    Asegura que la URL contenga pageSize=48.
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

def obtener_html_renderizado(url_destino):
    """
    Ejecuta el JavaScript en ScraperAPI para montar en el DOM la grilla completa de 28 productos.
    Mantiene un timeout amplio de 80 segundos para evitar cortes de lectura.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Referer": "https://www.natura.com.pe/"
    }

    key = obtener_key_natura()
    if not key:
        safe_log("🛑 [NATURA] No se encontró clave de ScraperAPI en secretos.", "error")
        try:
            resp = requests.get(url_destino, headers=headers, timeout=12, verify=False)
            if resp.status_code == 200:
                return resp.text
        except Exception:
            pass
        return None

    # Renderizado explícito de JavaScript vía ScraperAPI
    try:
        safe_log("🚀 [NATURA] Renderizando JavaScript en ScraperAPI (cargando grilla completa)...", "info")
        payload = {
            'api_key': key,
            'url': url_destino,
            'render': 'true',
            'country_code': 'us'
        }
        # Timeout de 80s para dar tiempo a que Chrome Headless monte los 28 elementos
        resp_sc = requests.get('http://api.scraperapi.com', params=payload, headers=headers, timeout=80)
        if resp_sc.status_code == 200 and len(resp_sc.text) > 3000:
            safe_log("✅ [NATURA] Carga de JavaScript completada exitosamente.", "success")
            return resp_sc.text
        else:
            safe_log(f"⚠️ [NATURA] ScraperAPI devolvió HTTP {resp_sc.status_code}. Reintentando sin JS...", "warning")
    except Exception as e:
        safe_log(f"⚠️ [NATURA] Error en renderizado JS: {e}. Intentando modo rápido de respaldo...", "warning")

    # Respaldo rápido si falla el renderizado JS
    try:
        payload = {'api_key': key, 'url': url_destino, 'render': 'false'}
        resp_fast = requests.get('http://api.scraperapi.com', params=payload, headers=headers, timeout=30)
        if resp_fast.status_code == 200:
            return resp_fast.text
    except Exception:
        pass

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

def normalizar_url_imagen(url_raw):
    """
    Normaliza y construye la URL absoluta de la imagen del CDN.
    """
    if not url_raw or 'data:image' in str(url_raw).lower():
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

def motor_natura(url, limite=999999.0, headers=None):
    """
    Motor principal centrado únicamente en procesar el DOM renderizado de la URL ingresada.
    """
    productos_map = {}
    url_base = sanitizar_url(url)
    url_final = asegurar_pagesize(url_base, page_size=48)

    safe_log(f"🚀 [NATURA] Consultando URL: {url_final}", "info")

    html_content = obtener_html_renderizado(url_final)
    if not html_content:
        safe_log("🛑 [NATURA] No se pudo obtener respuesta de la tienda.", "error")
        return []

    soup = BeautifulSoup(html_content, 'html.parser')

    # Búsqueda directa de tarjetas en el DOM renderizado por JS
    articulos = soup.find_all(['article', 'div'], attrs={'data-testid': re.compile(r'product-card', re.I)}) or \
                soup.find_all(['article', 'div'], attrs={'id': 'product-card'}) or \
                soup.find_all('a', href=lambda h: h and '/p/' in str(h).lower())

    safe_log(f"🔍 [NATURA] Elementos detectados en el DOM: {len(articulos)}", "info")

    for art in articulos:
        try:
            a_tag = art if art.name == 'a' else art.find('a', href=lambda h: h and '/p/' in str(h).lower())
            if not a_tag or not a_tag.get('href'):
                continue

            href = a_tag['href'].strip()
            if any(x in href.lower() for x in ['/cart', '/checkout', '/login', '/mi-cuenta']):
                continue

            link_final = urljoin("https://www.natura.com.pe", href).split('?')[0].split('#')[0]

            img_el = art.find('img')
            nombre_raw = ""
            img_src = ""

            if img_el:
                nombre_raw = img_el.get('alt', '').strip()
                img_src = img_el.get('src', '') or img_el.get('data-src', '') or img_el.get('srcset', '')

            if not nombre_raw:
                nombre_raw = a_tag.get_text(strip=True) or art.get_text(strip=True)

            texto_card = art.get_text(separator=' ', strip=True)
            precios_found = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_card)
            precios_num = [limpiar_precio_natura(p) for p in precios_found if limpiar_precio_natura(p) > 0]

            p_o, p_r = 0.0, 0.0
            if precios_num:
                unicos = sorted(list(set(precios_num)))
                p_o = unicos[0]
                p_r = unicos[-1]

            nombre_final = limpiar_nombre_natura(nombre_raw)
            img_clean = normalizar_url_imagen(img_src)

            if link_final and p_o > 0 and p_o <= limite and nombre_final:
                if link_final not in productos_map:
                    productos_map[link_final] = {
                        "nombre": nombre_final,
                        "precio": p_o,
                        "precio_regular": max(p_r, p_o),
                        "link": link_final,
                        "img": img_clean
                    }
                else:
                    if not productos_map[link_final]["img"] and img_clean:
                        productos_map[link_final]["img"] = img_clean
        except Exception:
            continue

    # Respaldo: Si el selector de tarjetas no capturó la totalidad, escanear todos los enlaces /p/
    if len(productos_map) < 10:
        safe_log("🔄 [NATURA] Realizando barrido general de enlaces /p/...", "info")
        enlaces_p = soup.find_all('a', href=lambda h: h and '/p/' in str(h).lower())
        for a_tag in enlaces_p:
            try:
                href = a_tag['href'].strip()
                if any(x in href.lower() for x in ['/cart', '/checkout', '/login', '/mi-cuenta']):
                    continue

                link_final = urljoin("https://www.natura.com.pe", href).split('?')[0].split('#')[0]
                card = a_tag.find_parent(['div', 'article', 'li']) or a_tag

                texto_card = card.get_text(separator=' ', strip=True)
                precios_found = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_card)
                precios_num = [limpiar_precio_natura(p) for p in precios_found if limpiar_precio_natura(p) > 0]

                if not precios_num: continue

                p_o = sorted(list(set(precios_num)))[0]
                p_r = sorted(list(set(precios_num)))[-1]

                img_el = card.find('img')
                nombre_raw = img_el.get('alt', '').strip() if img_el and img_el.get('alt') else a_tag.get_text(strip=True)
                img_src = img_el.get('src', '') if img_el else ''

                nombre_final = limpiar_nombre_natura(nombre_raw)
                img_clean = normalizar_url_imagen(img_src)

                if link_final and p_o > 0 and p_o <= limite and nombre_final:
                    if link_final not in productos_map:
                        productos_map[link_final] = {
                            "nombre": nombre_final,
                            "precio": p_o,
                            "precio_regular": max(p_r, p_o),
                            "link": link_final,
                            "img": img_clean
                        }
            except Exception:
                continue

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [NATURA] ¡Éxito! Se indexaron un total de {len(productos_finales)} ofertas válidas de la grilla principal.", "success")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
