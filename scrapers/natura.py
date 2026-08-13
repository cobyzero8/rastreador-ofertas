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
        if resp.status_code == 200 and len(resp.text) > 2000 and any(x in resp.text.lower() for x in ['natura', 'product', 'vtex', 'ld+json', '__next_data__']):
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
            'render': 'false'  # Mantiene el consumo en solo 1 crédito
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

def motor_natura(url, limite=999999.0, headers=None):
    """
    Motor extractor de productos para Natura Perú (natura.com.pe) - VTEX IO Compatible
    """
    productos_map = {}
    url_base = sanitizar_url(url)

    resp = consultar_natura_con_cascada(url_base)
    if not resp or resp.status_code != 200 or not resp.text:
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')

    # ==============================================================================
    # CAPA 1: PARSEO VÍA ESTRUCTURA JSON-LD (VTEX ItemList)
    # ==============================================================================
    scripts_ld = soup.find_all('script', type='application/ld+json')
    for script in scripts_ld:
        if not script.text: continue
        try:
            data_ld = json.loads(script.text)
            items_list = []
            
            if isinstance(data_ld, dict):
                if data_ld.get('@type') == 'ItemList':
                    items_list = data_ld.get('itemListElement', [])
                elif 'itemListElement' in data_ld:
                    items_list = data_ld.get('itemListElement', [])
            elif isinstance(data_ld, list):
                items_list = data_ld

            for elem in items_list:
                item = elem.get('item', {}) if isinstance(elem, dict) else elem
                if not isinstance(item, dict): continue

                nombre = str(item.get('name') or item.get('productName') or '').strip().upper()
                if not nombre or len(nombre) < 3: continue

                link_rel = item.get('url') or item.get('@id') or ''
                if not link_rel: continue
                link_final = urljoin("https://www.natura.com.pe", link_rel).split('?')[0].split('#')[0]

                offers = item.get('offers', {})
                p_o = 0.0
                p_r = 0.0

                if isinstance(offers, dict):
                    p_o = float(offers.get('price') or offers.get('lowPrice') or 0.0)
                    p_r = float(offers.get('highPrice') or p_o)
                elif isinstance(offers, list) and len(offers) > 0:
                    p_o = float(offers[0].get('price', 0.0))
                    p_r = p_o

                img_url = item.get('image') or ""
                if isinstance(img_url, list) and len(img_url) > 0: img_url = img_url[0]
                if isinstance(img_url, dict): img_url = img_url.get('url', '')

                if img_url and not img_url.startswith('http'):
                    img_url = urljoin("https:", img_url) if img_url.startswith('//') else urljoin("https://www.natura.com.pe", img_url)

                if 0 < p_o <= limite:
                    productos_map[link_final] = {
                        "nombre": f"NATURA - {nombre}",
                        "precio": p_o,
                        "precio_regular": max(p_r, p_o),
                        "link": link_final,
                        "img": str(img_url)
                    }
        except Exception:
            continue

    # ==============================================================================
    # CAPA 2: ESCÁNER VTEX IO DE ENLACES TERMINADOS EN /p
    # ==============================================================================
    if not productos_map:
        enlaces_p = soup.find_all('a', href=lambda h: h and ('/p' in str(h).lower() or '/producto' in str(h).lower()))

        for a_tag in enlaces_p:
            try:
                href = a_tag['href'].strip()
                if not href or any(x in href.lower() for x in ['/cart', '/checkout', '/login', '/mi-cuenta']):
                    continue

                link_final = urljoin("https://www.natura.com.pe", href).split('?')[0].split('#')[0]
                card = a_tag.find_parent(['div', 'article', 'li']) or a_tag

                # Extraer nombre
                nombre_el = card.find(['h2', 'h3', 'h4', 'span', 'p'], class_=re.compile(r'(title|name|nombre|product)', re.I))
                if nombre_el:
                    nombre = nombre_el.get_text(strip=True).upper()
                else:
                    nombre = a_tag.get_text(strip=True).upper()

                nombre = re.sub(r'S/\.?\s*\d+[\d\.,]*', '', nombre)
                nombre = re.sub(r'\s+', ' ', nombre).strip()

                if not nombre or len(nombre) < 3 or nombre in ['COMPRAR', 'VER MÁS', 'AGREGAR']:
                    continue

                # Extraer precios
                texto_card = card.get_text(separator=' ', strip=True)
                precios_encontrados = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_card)
                precios_numeros = [limpiar_precio_natura(p) for p in precios_encontrados if limpiar_precio_natura(p) > 0]

                if not precios_numeros: continue

                precios_unicos = sorted(list(set(precios_numeros)))
                p_o = precios_unicos[0]
                p_r = precios_unicos[-1] if len(precios_unicos) > 1 else p_o

                # Extraer imagen
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
