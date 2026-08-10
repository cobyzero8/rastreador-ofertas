import os
import re
import json
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from config import LISTA_USER_AGENTS
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
    """
    1. Intenta conexión directa.
    2. Si Ripley bloquea (HTTP 403 / 503 / Cloudflare), activa ScraperAPI en cascada.
    """
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
        if r.status_code == 200 and len(r.text) > 2000 and any(x in r.text.lower() for x in ['catalog-product-item', '__preloaded_state__']):
            safe_log("✅ [RIPLEY] Conexión directa exitosa (0 créditos consumidos).", "success")
            return r
        else:
            safe_log(f"⚠️ [RIPLEY] Conexión directa rebotó o incompleta (HTTP {r.status_code}).", "warning")
    except Exception as ex:
        safe_log(f"⚠️ [RIPLEY] Error en conexión directa: {ex}", "warning")

    keys = obtener_keys_ripley()
    if not keys:
        safe_log("🛑 [RIPLEY] No se encontraron claves SCRAPERAPI_RIPLEY_KEY configuradas.", "error")
        return None

    for idx, key in enumerate(keys, start=1):
        try:
            safe_log(f"🛡️ [RIPLEY] Probando ScraperAPI Key Ripley #{idx} ({key[:6]}...)", "info")
            payload = {'api_key': key, 'url': url_destino, 'render': 'false'}
            r_sc = session.get('http://api.scraperapi.com', params=payload, timeout=35)
            
            if r_sc.status_code == 200 and len(r_sc.text) > 1000:
                safe_log(f"✅ [RIPLEY] Petición exitosa usando Key Ripley #{idx}.", "success")
                return r_sc
            elif r_sc.status_code in [401, 403, 429]:
                safe_log(f"⚠️ [RIPLEY] Key #{idx} sin créditos o bloqueada (HTTP {r_sc.status_code}). Saltando...", "warning")
            else:
                safe_log(f"⚠️ [RIPLEY] Key #{idx} devolvió HTTP {r_sc.status_code}", "warning")
        except Exception as e:
            safe_log(f"⚠️ [RIPLEY] Error con Key #{idx}: {e}", "warning")

    safe_log("🛑 [RIPLEY] Se agotaron todas las claves de ScraperAPI para Ripley.", "error")
    return None

def limpiar_num_ripley(texto):
    if not texto: return 0.0
    texto = str(texto).replace('S/.', '').replace('S/', '').replace('PEN', '').replace('S', '').strip()
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
    # CAPA 1: EXTRACCIÓN VÍA ESTADO JSON PRECARGADO (window.__PRELOADED_STATE__)
    # ==============================================================================
    match_state = re.search(r'window\.__PRELOADED_STATE__\s*=\s*(\{.*?\});', texto_html, re.DOTALL)
    if match_state:
        try:
            data_json = json.loads(match_state.group(1))
            catalog_products = []

            # Extraer lista de productos del estado interno de Ripley
            if isinstance(data_json, dict):
                catalog_products = data_json.get('catalog', {}).get('products', []) or \
                                   data_json.get('products', []) or []

            for p in catalog_products:
                if not isinstance(p, dict): continue
                
                nombre = str(p.get('name') or p.get('fullTitle') or '').strip().upper()
                if not nombre or len(nombre) < 3: continue

                # Enlace del producto
                link_rel = p.get('url') or p.get('singleProductUrl') or ''
                if not link_rel and p.get('partNumber'):
                    link_rel = f"/p/{p.get('partNumber')}"

                if not link_rel: continue
                link_final = urljoin("https://simple.ripley.com.pe", link_rel).split('?')[0].split('#')[0]

                # Precios
                prices = p.get('prices', {}) or {}
                p_o = float(prices.get('offerPrice') or prices.get('cardPrice') or prices.get('salePrice') or 0.0)
                p_r = float(prices.get('listPrice') or prices.get('normalPrice') or p_o)

                if p_o <= 0:
                    p_o = float(p.get('price', 0.0))
                    p_r = max(p_r, p_o)

                # Imagen
                img_url = p.get('thumbnail') or p.get('fullImage') or p.get('images', [{}])[0] if isinstance(p.get('images'), list) and p.get('images') else ""
                if isinstance(img_url, dict):
                    img_url = img_url.get('url', '')

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
            safe_log(f"⚠️ [RIPLEY] Error parseando __PRELOADED_STATE__: {ex_json}", "warning")

    # ==============================================================================
    # CAPA 2: FALLBACK SCANNER HTML DE TARJETAS (.catalog-product-item)
    # ==============================================================================
    if not productos_map:
        tarjetas = soup.find_all(['a', 'div', 'article'], class_=lambda c: c and any(x in str(c).lower() for x in ['catalog-product-item', 'product-item', 'catalog-item']))

        for card in tarjetas:
            try:
                a_tag = card if card.name == 'a' and card.get('href') else card.find('a', href=True)
                if not a_tag: continue

                href = a_tag['href'].strip()
                if not href or any(x in href.lower() for x in ['/cart', '/checkout', '/account']):
                    continue

                link_final = urljoin("https://simple.ripley.com.pe", href).split('?')[0].split('#')[0]

                # Nombre
                nombre_el = card.find(class_=lambda c: c and any(x in str(c).lower() for x in ['catalog-product-details__name', 'product-title', 'name']))
                nombre = nombre_el.get_text(strip=True).upper() if nombre_el else a_tag.get_text(strip=True).upper()
                nombre = re.sub(r'\s+', ' ', nombre).strip()

                if not nombre or len(nombre) < 3 or nombre in ['VER MÁS', 'COMPRAR']: continue

                # Precios
                texto_card = card.get_text()
                precios_encontrados = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_card)
                precios_numeros = [limpiar_num_ripley(p) for p in precios_encontrados if limpiar_num_ripley(p) > 0]

                if not precios_numeros: continue

                precios_unicos = sorted(list(set(precios_numeros)))
                p_o = precios_unicos[0]
                p_r = precios_unicos[-1] if len(precios_unicos) > 1 else p_o

                # Imagen
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
        safe_log(f"⚠️ [RIPLEY] No se encontraron productos bajo el límite de S/. {limite:.2f}", "warning")

    return productos_finales
