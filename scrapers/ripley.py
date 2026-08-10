import re
import json
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from utils import sanitizar_url, safe_log

# Importación segura de curl_cffi para imitar la huella TLS de Google Chrome
try:
    from curl_cffi import requests as curl_requests
    CURL_DISPONIBLE = True
except ImportError:
    import requests as curl_requests
    CURL_DISPONIBLE = False

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
    Motor extractor directo y 100% gratuito para Ripley Perú (simple.ripley.com.pe)
    Utiliza impersonación de huella Chrome TLS vía curl_cffi para evitar HTTP 403.
    """
    productos_map = {}
    url_base = sanitizar_url(url)

    headers_directos = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "accept-language": "es-PE,es-419;q=0.9,es;q=0.8,en;q=0.7",
        "sec-ch-ua": '"Not/A)Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1"
    }

    try:
        safe_log(f"📡 [RIPLEY] Consultando con imitación TLS de Chrome...", "info")
        
        if CURL_DISPONIBLE:
            resp = curl_requests.get(url_base, headers=headers_directos, impersonate="chrome120", timeout=20)
        else:
            safe_log("⚠️ 'curl_cffi' no está instalado. Añádelo a requirements.txt", "warning")
            import requests
            resp = requests.get(url_base, headers=headers_directos, timeout=15)

        if resp.status_code != 200:
            safe_log(f"🛑 [RIPLEY] El servidor devolvió HTTP {resp.status_code}", "error")
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

                if isinstance(data_json, dict):
                    catalog_products = data_json.get('catalog', {}).get('products', []) or \
                                       data_json.get('products', []) or []

                for p in catalog_products:
                    if not isinstance(p, dict): continue
                    
                    nombre = str(p.get('name') or p.get('fullTitle') or '').strip().upper()
                    if not nombre or len(nombre) < 3: continue

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
                safe_log(f"⚠️ [RIPLEY] Error parseando datos precargados: {ex_json}", "warning")

        # ==============================================================================
        # CAPA 2: FALLBACK TARJETAS HTML (.catalog-product-item)
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

                    nombre_el = card.find(class_=lambda c: c and any(x in str(c).lower() for x in ['catalog-product-details__name', 'product-title', 'name']))
                    nombre = nombre_el.get_text(strip=True).upper() if nombre_el else a_tag.get_text(strip=True).upper()
                    nombre = re.sub(r'\s+', ' ', nombre).strip()

                    if not nombre or len(nombre) < 3 or nombre in ['VER MÁS', 'COMPRAR']: continue

                    texto_card = card.get_text()
                    precios_encontrados = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_card)
                    precios_numeros = [limpiar_num_ripley(p) for p in precios_encontrados if limpiar_num_ripley(p) > 0]

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

    except Exception as e:
        safe_log(f"🚨 [RIPLEY] Error en conexión: {e}", "error")

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [RIPLEY] ¡Éxito! Se indexaron {len(productos_finales)} ofertas de forma gratuita.", "success")
    else:
        safe_log(f"⚠️ [RIPLEY] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
