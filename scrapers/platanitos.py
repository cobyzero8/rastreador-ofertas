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

try:
    from curl_cffi import requests as curl_requests
    CURL_DISPONIBLE = True
except ImportError:
    import requests as curl_requests
    CURL_DISPONIBLE = False

def obtener_keys_platanitos():
    """
    Obtiene las claves de ScraperAPI disponibles para Platanitos en orden secuencial.
    """
    keys = []
    nombres_keys = [
        "SCRAPERAPI_PLATANITOS_KEY", "SCRAPERAPI_KEY", 
        "SCRAPERAPI_RIPLEY_KEY", "SCRAPERAPI_RIPLEY_KEY_2"
    ]

    try:
        import streamlit as st
        for name in nombres_keys:
            if name in st.secrets and st.secrets[name]:
                val = str(st.secrets[name]).strip()
                if len(val) > 10 and "tu_clave" not in val and val not in keys:
                    keys.append(val)
    except Exception:
        pass

    if not keys:
        for name in nombres_keys:
            val = os.environ.get(name, "").strip()
            if val and len(val) > 10 and "tu_clave" not in val and val not in keys:
                keys.append(val)

    return keys

def consultar_platanitos_con_cascada(url_destino):
    """
    1. Intenta conexión directa gratis con curl_cffi.
    2. Si Cloudflare bloquea con HTTP 403, activa ScraperAPI en cascada.
    """
    headers_base = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-language": "es-PE,es-419;q=0.9,es;q=0.8,en;q=0.7",
        "cache-control": "no-cache",
        "pragma": "no-cache",
        "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    }

    # 🟢 Paso 1: Intento directo con curl_cffi
    try:
        safe_log(f"📡 [PLATANITOS] Intentando conexión directa...", "info")
        if CURL_DISPONIBLE:
            session = curl_requests.Session(impersonate="chrome120")
            r = session.get(url_destino, headers=headers_base, timeout=15)
        else:
            session = requests.Session()
            r = session.get(url_destino, headers=headers_base, timeout=15, verify=False)

        if r.status_code == 200 and len(r.text) > 1500 and any(x in r.text.lower() for x in ['/pe/producto/', 'product', 'platanitos']):
            safe_log("✅ [PLATANITOS] Conexión directa exitosa (0 créditos consumidos).", "success")
            return r
        else:
            safe_log(f"⚠️ [PLATANITOS] Conexión directa rebotó (HTTP {r.status_code}). Activando cascada...", "warning")
    except Exception as ex:
        safe_log(f"⚠️ [PLATANITOS] Error en conexión directa: {ex}", "warning")

    # 🛡️ Paso 2: Cascada con ScraperAPI
    keys = obtener_keys_platanitos()
    if not keys:
        safe_log("🛑 [PLATANITOS] No se encontraron claves ScraperAPI en los secretos para bypass.", "error")
        return None

    session_std = requests.Session()
    for idx, key in enumerate(keys, start=1):
        for intento in range(1, 3):
            try:
                safe_log(f"🛡️ [PLATANITOS] Probando ScraperAPI Key #{idx} (Intento {intento})...", "info")
                payload = {
                    'api_key': key,
                    'url': url_destino,
                    'country_code': 'us',
                    'keep_headers': 'true'
                }
                r_sc = session_std.get('http://api.scraperapi.com', params=payload, headers=headers_base, timeout=35)

                if r_sc.status_code == 200 and len(r_sc.text) > 1000:
                    safe_log(f"✅ [PLATANITOS] Petición exitosa usando ScraperAPI Key #{idx}.", "success")
                    return r_sc
                elif r_sc.status_code in [500, 502, 504]:
                    safe_log(f"⚠️ [PLATANITOS] ScraperAPI devolvió HTTP {r_sc.status_code}. Reintentando...", "warning")
                    time.sleep(2)
                elif r_sc.status_code in [401, 403, 429]:
                    safe_log(f"⚠️ [PLATANITOS] Key #{idx} sin créditos o bloqueada (HTTP {r_sc.status_code}). Saltando...", "warning")
                    break
            except Exception as e:
                safe_log(f"⚠️ [PLATANITOS] Error con Key #{idx}: {e}", "warning")
                time.sleep(1.5)

    safe_log("🛑 [PLATANITOS] Se agotaron las claves de ScraperAPI para Platanitos.", "error")
    return None

def limpiar_num_platanitos(texto):
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

def motor_platanitos(url, limite=999999.0, headers=None):
    """
    Motor extractor de productos para Platanitos Perú (platanitos.com)
    """
    productos_map = {}
    url_base = sanitizar_url(url)

    resp = consultar_platanitos_con_cascada(url_base)
    if not resp or resp.status_code != 200 or not resp.text:
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')

    # Buscar contenedores o enlaces de producto (/pe/producto/ o /producto/)
    enlaces_prod = soup.find_all('a', href=lambda h: h and ('/pe/producto/' in str(h).lower() or '/producto/' in str(h).lower()))

    for a_tag in enlaces_prod:
        try:
            href = a_tag['href'].strip()
            link_final = urljoin("https://platanitos.com", href).split('?')[0].split('#')[0]

            card = a_tag.find_parent(['div', 'article', 'li']) or a_tag
            texto_card = card.get_text(separator=' ', strip=True)

            # Nombre del producto
            nombre = ""
            nombre_el = card.find(['h2', 'h3', 'h4', 'p', 'span'], class_=lambda c: c and any(k in str(c).lower() for k in ['title', 'nombre', 'product', 'item']))
            if nombre_el:
                nombre = nombre_el.get_text(strip=True).upper()
            
            if not nombre or len(nombre) < 3:
                img_in_a = card.find('img', alt=True)
                if img_in_a and len(img_in_a['alt'].strip()) > 3:
                    nombre = img_in_a['alt'].strip().upper()
                else:
                    nombre = a_tag.get_text(strip=True).upper()

            nombre = re.sub(r'S/\.?\s*\d+[\d\.,]*', '', nombre)
            nombre = re.sub(r'\s+', ' ', nombre).strip()

            if not nombre or len(nombre) < 3 or nombre in ['VER MÁS', 'COMPRAR', 'NUEVO']: continue

            # Extracción de Precios
            precios_encontrados = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_card)
            precios_numeros = [limpiar_num_platanitos(p) for p in precios_encontrados if limpiar_num_platanitos(p) > 0]

            if not precios_numeros: continue

            precios_unicos = sorted(list(set(precios_numeros)))
            p_o = precios_unicos[0]
            p_r = precios_unicos[-1] if len(precios_unicos) > 1 else p_o

            # Imagen
            img_el = card.find('img')
            img_url = ""
            if img_el:
                img_url = img_el.get('src') or img_el.get('data-src') or img_el.get('data-lazy') or img_el.get('srcset') or ""

            if img_url:
                if ',' in img_url: img_url = img_url.split(',')[0].split(' ')[0]
                if img_url.startswith('//'): img_url = 'https:' + img_url
                elif not img_url.startswith('http'): img_url = urljoin("https://platanitos.com", img_url)

            if 'data:image' in img_url.lower() or 'pixel' in img_url.lower():
                img_url = ""

            if 0 < p_o <= limite:
                productos_map[link_final] = {
                    "nombre": f"PLATANITOS - {nombre}",
                    "precio": p_o,
                    "precio_regular": max(p_r, p_o),
                    "link": link_final,
                    "img": img_url
                }
        except Exception:
            continue

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [PLATANITOS] ¡Éxito! Se indexaron {len(productos_finales)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [PLATANITOS] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
