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

def obtener_keys_ripley():
    """
    Obtiene las claves de ScraperAPI exclusivas para Ripley en orden secuencial.
    """
    keys = []
    nombres_keys = ["SCRAPERAPI_RIPLEY_KEY", "SCRAPERAPI_RIPLEY_KEY_2", "SCRAPERAPI_RIPLEY_KEY_3"]

    try:
        import streamlit as st
        for name in nombres_keys:
            if name in st.secrets and st.secrets[name]:
                val = str(st.secrets[name]).strip()
                if len(val) > 10 and "tu_clave" not in val:
                    keys.append(val)
    except Exception:
        pass

    if not keys:
        for name in nombres_keys:
            val = os.environ.get(name, "").strip()
            if val and len(val) > 10 and "tu_clave" not in val:
                keys.append(val)

    return keys

def consultar_ripley_con_cascada(url_destino):
    session = requests.Session()
    headers_directos = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9",
        "Referer": "https://simple.ripley.com.pe/"
    }

    try:
        safe_log(f"📡 [RIPLEY] Intentando conexión directa gratis...", "info")
        r = session.get(url_destino, headers=headers_directos, timeout=12, verify=False)
        if r.status_code == 200 and len(r.text) > 2000 and any(x in r.text.lower() for x in ['product-item', '__next_data__']):
            safe_log("✅ [RIPLEY] Conexión directa exitosa (0 créditos consumidos).", "success")
            return r
        else:
            safe_log(f"⚠️ [RIPLEY] Conexión directa rebotó o incompleta (HTTP {r.status_code}).", "warning")
    except Exception as ex:
        safe_log(f"⚠️ [RIPLEY] Error en conexión directa: {ex}", "warning")

    keys = obtener_keys_ripley()
    if not keys:
        safe_log("🛑 [RIPLEY] No se encontraron claves SCRAPERAPI_RIPLEY_KEY en los secretos.", "error")
        return None

    for idx, key in enumerate(keys, start=1):
        for intento in range(1, 3):
            try:
                safe_log(f"🛡️ [RIPLEY] Probando ScraperAPI Key Ripley #{idx} (Intento {intento})...", "info")
                payload = {
                    'api_key': key, 
                    'url': url_destino, 
                    'country_code': 'us',
                    'keep_headers': 'true'
                }
                r_sc = session.get('http://api.scraperapi.com', params=payload, headers=headers_directos, timeout=35)
                
                if r_sc.status_code == 200 and len(r_sc.text) > 1000:
                    safe_log(f"✅ [RIPLEY] Petición exitosa usando Key Ripley #{idx}.", "success")
                    return r_sc
                elif r_sc.status_code in [500, 502, 504]:
                    safe_log(f"⚠️ [RIPLEY] ScraperAPI devolvió HTTP {r_sc.status_code}. Reintentando...", "warning")
                    time.sleep(2)
                elif r_sc.status_code in [401, 403, 429]:
                    safe_log(f"⚠️ [RIPLEY] Key #{idx} sin créditos (HTTP {r_sc.status_code}). Saltando...", "warning")
                    break
                else:
                    safe_log(f"⚠️ [RIPLEY] Key #{idx} devolvió HTTP {r_sc.status_code}", "warning")
            except Exception as e:
                safe_log(f"⚠️ [RIPLEY] Error con Key #{idx}: {e}", "warning")
                time.sleep(1.5)

    safe_log("🛑 [RIPLEY] Se agotaron todas las claves de ScraperAPI registradas para Ripley.", "error")
    return None

def limpiar_num_ripley(texto):
    if not texto: return 0.0
    texto = str(texto).replace('\xa0', ' ').replace('S/.', '').replace('S/', '').replace('PEN', '').replace('S', '').strip()
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

def extraer_productos_de_json_recursivo(data):
    """
    Busca de forma recursiva objetos que tengan estructura de producto en JSON de Next.js
    """
    prods = []
    def buscar(obj):
        if isinstance(obj, dict):
            es_prod = ('name' in obj or 'fullTitle' in obj or 'partNumber' in obj) and \
                      ('prices' in obj or 'price' in obj or 'singleProductUrl' in obj or 'url' in obj)
            if es_prod:
                prods.append(obj)
            for v in obj.values():
                buscar(v)
        elif isinstance(obj, list):
            for item in obj:
                buscar(item)
    buscar(data)
    return prods

def motor_ripley(url, limite=999999.0, headers=None):
    """
    Motor extractor de productos para Ripley Perú (simple.ripley.com.pe)
    """
    productos_map = {}
    url_base = sanitizar_url(url)

    resp = consultar_ripley_con_cascada(url_base)
    if not resp or resp.status_code != 200 or not resp.text:
        return []

    texto_html = resp.text
    soup = BeautifulSoup(texto_html, 'html.parser')

    # ==============================================================================
    # CAPA 1: EXTRACCIÓN VÍA JSON DE NEXT.JS (__NEXT_DATA__) O STATE
    # ==============================================================================
    script_next = soup.find('script', id='__NEXT_DATA__')
    if script_next and script_next.text:
        try:
            data_json = json.loads(script_next.text)
            catalog_products = extraer_productos_de_json_recursivo(data_json)

            for p in catalog_products:
                if not isinstance(p, dict): continue
                
                nombre = str(p.get('name') or p.get('fullTitle') or p.get('shortDescription') or '').strip().upper()
                if not nombre or len(nombre) < 3: continue

                link_rel = p.get('url') or p.get('singleProductUrl') or ''
                if not link_rel and p.get('partNumber'):
                    link_rel = f"/p/{p.get('partNumber')}"

                if not link_rel: continue
                link_final = urljoin("https://simple.ripley.com.pe", link_rel).split('?')[0].split('#')[0]

                prices = p.get('prices', {}) or {}
                if isinstance(prices, dict):
                    p_o = float(prices.get('offerPrice') or prices.get('cardPrice') or prices.get('salePrice') or 0.0)
                    p_r = float(prices.get('listPrice') or prices.get('normalPrice') or p_o)
                else:
                    p_o = float(p.get('price', 0.0))
                    p_r = p_o

                if p_o <= 0:
                    p_o = float(p.get('price', 0.0))
                    p_r = max(p_r, p_o)

                img_url = p.get('thumbnail') or p.get('fullImage') or ""
                if not img_url and isinstance(p.get('images'), list) and len(p.get('images')) > 0:
                    img_first = p.get('images')[0]
                    img_url = img_first.get('url', '') if isinstance(img_first, dict) else str(img_first)

                if img_url and not img_url.startswith('http'):
                    img_url = urljoin("https:", img_url) if img_url.startswith('//') else urljoin("https://simple.ripley.com.pe", img_url)

                if 0 < p_o <= limite:
                    productos_map[link_final] = {
                        "nombre": f"RIPLEY - {nombre}",
                        "precio": p_o,
                        "precio_regular": max(p_r, p_o),
                        "link": link_final,
                        "img": str(img_url)
                    }
        except Exception as ex_json:
            safe_log(f"⚠️ [RIPLEY] Error parseando datos de __NEXT_DATA__: {ex_json}", "warning")

    # ==============================================================================
    # CAPA 2: SCANNER HTML BASADO EN EL DOM DE TU CAPTURA DE PANTALLA
    # ==============================================================================
    if not productos_map:
        # Buscar contenedores con clases product-item o catalog-product-item
        tarjetas = soup.find_all(['div', 'article', 'a'], class_=lambda c: c and any(x in str(c).lower() for x in ['product-item', 'catalog-product-item']))

        for card in tarjetas:
            try:
                a_tag = card if card.name == 'a' and card.get('href') else card.find('a', href=True)
                if not a_tag: continue

                href = a_tag['href'].strip()
                if not href or any(x in href.lower() for x in ['/cart', '/checkout', '/account', '/servicio']):
                    continue

                link_final = urljoin("https://simple.ripley.com.pe", href).split('?')[0].split('#')[0]

                # 1. Extraer nombre desde product-item-name o atributo title
                nombre_el = card.find(class_=lambda c: c and 'product-item-name' in str(c).lower()) or \
                            card.find(['p', 'span', 'div'], title=True)
                
                if nombre_el:
                    nombre = (nombre_el.get('title') or nombre_el.get_text(strip=True)).upper()
                else:
                    nombre = a_tag.get_text(strip=True).upper()

                nombre = re.sub(r'\s+', ' ', nombre).strip()
                if not nombre or len(nombre) < 3 or nombre in ['VER MÁS', 'COMPRAR']: continue

                # 2. Extraer precios desde product-price-wrapper
                texto_card = card.get_text()
                precios_encontrados = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_card)
                precios_numeros = [limpiar_num_ripley(p) for p in precios_encontrados if limpiar_num_ripley(p) > 0]

                if not precios_numeros: continue

                precios_unicos = sorted(list(set(precios_numeros)))
                p_o = precios_unicos[0]
                p_r = precios_unicos[-1] if len(precios_unicos) > 1 else p_o

                # 3. Extraer imagen
                img_el = card.find('img')
                img_url = ""
                if img_el:
                    img_url = img_el.get('src') or img_el.get('data-src') or img_el.get('srcset') or ""

                if img_url:
                    if ',' in img_url: img_url = img_url.split(',')[0].split(' ')[0]
                    if img_url.startswith('//'): img_url = 'https:' + img_url
                    elif not img_url.startswith('http'): img_url = urljoin("https://simple.ripley.com.pe", img_url)

                if 'data:image' in img_url.lower() or 'pixel' in img_url.lower():
                    img_url = ""

                if 0 < p_o <= limite:
                    productos_map[link_final] = {
                        "nombre": f"RIPLEY - {nombre}",
                        "precio": p_o,
                        "precio_regular": max(p_r, p_o),
                        "link": link_final,
                        "img": img_url
                    }
            except Exception: continue

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [RIPLEY] ¡Éxito! Se indexaron {len(productos_finales)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [RIPLEY] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
