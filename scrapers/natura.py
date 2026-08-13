import os
import re
import json
import time
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from utils import sanitizar_url, safe_log

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def obtener_key_natura():
    """
    Obtiene la clave de ScraperAPI para Natura o la clave general.
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

def consultar_natura_con_cascada(url_destino):
    headers_directos = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Referer": "https://www.natura.com.pe/"
    }

    # 🟢 Paso 1: Intento directo gratis
    try:
        safe_log(f"📡 [NATURA] Intentando conexión directa...", "info")
        resp = requests.get(url_destino, headers=headers_directos, timeout=12, verify=False)
        if resp.status_code == 200 and len(resp.text) > 2000 and any(x in resp.text.lower() for x in ['natura', 'product', '__next_data__']):
            safe_log("✅ [NATURA] Conexión directa exitosa (0 créditos consumidos).", "success")
            return resp
        else:
            safe_log(f"⚠️ [NATURA] Conexión directa rebotó (HTTP {resp.status_code}). Activando ScraperAPI...", "warning")
    except Exception as ex:
        safe_log(f"⚠️ [NATURA] Error en conexión directa: {ex}", "warning")

    # 🛡️ Paso 2: Respaldo con ScraperAPI
    key = obtener_key_natura()
    if not key:
        safe_log("🛑 [NATURA] No se encontró clave de ScraperAPI en los secretos.", "error")
        return None

    try:
        safe_log(f"🛡️ [NATURA] Consultando vía ScraperAPI...", "info")
        payload = {
            'api_key': key,
            'url': url_destino,
            'country_code': 'us',
            'render': 'false'  # 1 solo crédito por consulta
        }
        resp_sc = requests.get('http://api.scraperapi.com', params=payload, headers=headers_directos, timeout=30)
        if resp_sc.status_code == 200 and len(resp_sc.text) > 1000:
            safe_log("✅ [NATURA] Petición exitosa usando ScraperAPI.", "success")
            return resp_sc
        else:
            safe_log(f"🛑 [NATURA] ScraperAPI devolvió HTTP {resp_sc.status_code}", "error")
    except Exception as e:
        safe_log(f"🚨 [NATURA] Error con ScraperAPI: {e}", "error")

    return None

def limpiar_precio_natura(texto):
    if not texto: return 0.0
    texto = str(texto).replace('&nbsp;', ' ').replace('\xa0', ' ')
    texto = texto.replace('S/.', '').replace('S/', '').replace('PEN', '').replace('S', '').strip()
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

def extraer_productos_json(data):
    prods = []
    def buscar(obj):
        if isinstance(obj, dict):
            # Criterio de objeto de producto Natura / VTEX
            if ('name' in obj or 'productName' in obj) and ('price' in obj or 'offers' in obj or 'spotPrice' in obj or 'link' in obj or 'url' in obj):
                prods.append(obj)
            for v in obj.values():
                buscar(v)
        elif isinstance(obj, list):
            for item in obj:
                buscar(item)
    buscar(data)
    return prods

def motor_natura(url, limite=999999.0, headers=None):
    """
    Motor extractor de productos para Natura Perú (natura.com.pe)
    """
    productos_map = {}
    url_base = sanitizar_url(url)

    resp = consultar_natura_con_cascada(url_base)
    if not resp or resp.status_code != 200 or not resp.text:
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')

    # ==============================================================================
    # CAPA 1: EXTRACCIÓN VÍA JSON NATIVO DE NEXT.JS / STATE
    # ==============================================================================
    script_next = soup.find('script', id='__NEXT_DATA__')
    if script_next and script_next.text:
        try:
            data_json = json.loads(script_next.text)
            catalog_products = extraer_productos_json(data_json)

            for p in catalog_products:
                if not isinstance(p, dict): continue

                raw_name = str(p.get('name') or p.get('productName') or p.get('title') or '').strip().upper()
                if not raw_name or len(raw_name) < 3: continue

                href = str(p.get('url') or p.get('link') or p.get('slug') or '').strip()
                if not href: continue
                if not href.startswith('/'): href = '/' + href

                link_final = urljoin("https://www.natura.com.pe", href).split('?')[0].split('#')[0]

                # Precios
                p_o = float(p.get('spotPrice') or p.get('price') or p.get('salesPrice') or 0.0)
                p_r = float(p.get('listPrice') or p.get('listPriceValue') or p_o)

                if p_o <= 0 and 'offers' in p and isinstance(p['offers'], dict):
                    p_o = float(p['offers'].get('price', 0.0))
                    p_r = max(p_r, p_o)

                # Imagen
                img_url = p.get('imageUrl') or p.get('image') or p.get('thumbnail') or ""
                if isinstance(img_url, list) and len(img_url) > 0:
                    img_url = img_url[0]
                if isinstance(img_url, dict):
                    img_url = img_url.get('url', '')

                if img_url and not img_url.startswith('http'):
                    img_url = urljoin("https:", img_url) if img_url.startswith('//') else urljoin("https://www.natura.com.pe", img_url)

                if 0 < p_o <= limite:
                    productos_map[link_final] = {
                        "nombre": f"NATURA - {raw_name}",
                        "precio": p_o,
                        "precio_regular": max(p_r, p_o),
                        "link": link_final,
                        "img": str(img_url)
                    }
        except Exception as ex_j:
            safe_log(f"⚠️ [NATURA] Error procesando JSON de Next.js: {ex_j}", "warning")

    # ==============================================================================
    # CAPA 2: ESCÁNER DE TARJETAS HTML (FALLBACK DE SEGURIDAD)
    # ==============================================================================
    if not productos_map:
        tarjetas = soup.find_all(['div', 'article', 'li'], class_=re.compile(r'(product|card|item|shelf)', re.I))

        for card in tarjetas:
            try:
                a_tag = card.find('a', href=True)
                if not a_tag: continue

                href = a_tag['href'].strip()
                if not href or any(x in href.lower() for x in ['/cart', '/checkout', '/login', '/mi-cuenta']):
                    continue

                link_final = urljoin("https://www.natura.com.pe", href).split('?')[0].split('#')[0]

                nombre_el = card.find(['h2', 'h3', 'h4', 'span', 'p'], class_=re.compile(r'(title|name|nombre)', re.I))
                if nombre_el:
                    nombre = nombre_el.get_text(strip=True).upper()
                else:
                    nombre = a_tag.get_text(strip=True).upper()

                nombre = re.sub(r'S/\.?\s*\d+[\d\.,]*', '', nombre)
                nombre = re.sub(r'\s+', ' ', nombre).strip()

                if not nombre or len(nombre) < 3 or nombre in ['COMPRAR', 'VER MÁS', 'AGREGAR']:
                    continue

                texto_card = card.get_text(separator=' ', strip=True)
                precios_encontrados = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_card)
                precios_numeros = [limpiar_precio_natura(p) for p in precios_encontrados if limpiar_precio_natura(p) > 0]

                if not precios_numeros: continue

                precios_unicos = sorted(list(set(precios_numeros)))
                p_o = precios_unicos[0]
                p_r = precios_unicos[-1] if len(precios_unicos) > 1 else p_o

                img_el = card.find('img')
                img_url = ""
                if img_el:
                    img_url = img_el.get('src') or img_el.get('data-src') or img_el.get('srcset') or ""

                if img_url:
                    if ',' in img_url: img_url = img_url.split(',')[0].split(' ')[0]
                    if img_url.startswith('//'): img_url = 'https:' + img_url
                    elif not img_url.startswith('http'): img_url = urljoin("https://www.natura.com.pe", img_url)

                if 'data:image' in img_url.lower(): img_url = ""

                if 0 < p_o <= limite:
                    productos_map[link_final] = {
                        "nombre": f"NATURA - {nombre}",
                        "precio": p_o,
                        "precio_regular": max(p_r, p_o),
                        "link": link_final,
                        "img": img_url
                    }
            except Exception:
                continue

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [NATURA] ¡Éxito! Se indexaron {len(productos_finales)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
