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

def obtener_keys_jbl():
    keys = []
    nombres_keys = ["SCRAPERAPI_JBL_KEY", "SCRAPERAPI_JBL_KEY_2", "SCRAPERAPI_JBL_KEY_3"]

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

def consultar_jbl_con_cascada(url_destino):
    session = requests.Session()
    headers_directos = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9",
        "Referer": "https://www.jbl.com.pe/"
    }

    try:
        safe_log(f"📡 [JBL] Intentando conexión directa gratis...", "info")
        r = session.get(url_destino, headers=headers_directos, timeout=12, verify=False)
        if r.status_code == 200 and len(r.text) > 1000:
            safe_log("✅ [JBL] Conexión directa exitosa (0 créditos consumidos).", "success")
            return r
        else:
            safe_log(f"⚠️ [JBL] Conexión directa rebotó con HTTP {r.status_code}.", "warning")
    except Exception as ex:
        safe_log(f"⚠️ [JBL] Error en conexión directa: {ex}", "warning")

    keys = obtener_keys_jbl()
    if not keys:
        safe_log("🛑 [JBL] No se encontraron claves SCRAPERAPI_JBL_KEY en los secretos.", "error")
        return None

    for idx, key in enumerate(keys, start=1):
        try:
            safe_log(f"🛡️ [JBL] Probando ScraperAPI Key JBL #{idx} ({key[:6]}...)", "info")
            payload = {'api_key': key, 'url': url_destino, 'render': 'false'}
            r_sc = session.get('http://api.scraperapi.com', params=payload, timeout=30)
            
            if r_sc.status_code == 200 and len(r_sc.text) > 1000:
                safe_log(f"✅ [JBL] Petición exitosa usando Key JBL #{idx}.", "success")
                return r_sc
            elif r_sc.status_code in [401, 403, 429]:
                safe_log(f"⚠️ [JBL] Key #{idx} sin créditos o bloqueada (HTTP {r_sc.status_code}). Saltando a la siguiente...", "warning")
            else:
                safe_log(f"⚠️ [JBL] Key #{idx} devolvió HTTP {r_sc.status_code}", "warning")
        except Exception as e:
            safe_log(f"⚠️ [JBL] Error con Key #{idx}: {e}", "warning")

    safe_log("🛑 [JBL] Se agotaron todas las claves de ScraperAPI registradas para JBL.", "error")
    return None

def limpiar_num_jbl(texto):
    if not texto: return 0.0
    texto = str(texto).replace('S/.', '').replace('S/', '').replace('PEN', '').replace('S', '').strip()
    
    match_miles = re.search(r'\b(\d{1,3})\.(\d{3})\b', texto)
    if match_miles:
        texto = texto.replace('.', '')

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

def motor_jbl(url, limite=999999.0, headers=None):
    productos_map = {}
    url_base = sanitizar_url(url)

    resp = consultar_jbl_con_cascada(url_base)
    if not resp or resp.status_code != 200 or not resp.text:
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')

    # Eliminar etiquetas con texto accesible que ensucian el nombre
    for oculto in soup.find_all(class_=lambda c: c and any(x in str(c).lower() for x in ['sr-only', 'visually-hidden'])):
        oculto.decompose()

    # ==============================================================================
    # CAPA 1: DATOS ESTRUCTURADOS JSON-LD
    # ==============================================================================
    for s in soup.find_all('script', type='application/ld+json'):
        try:
            data = json.loads(s.text)
            items = []
            if isinstance(data, dict):
                if data.get('@type') == 'ItemList':
                    items = data.get('itemListElement', [])
                elif data.get('@type') == 'Product':
                    items = [data]
            elif isinstance(data, list):
                items = data

            for item in items:
                prod = item.get('item', item) if isinstance(item, dict) else item
                if isinstance(prod, dict) and prod.get('@type') == 'Product':
                    nombre = str(prod.get('name', '')).strip().upper()
                    if len(nombre) < 3: continue

                    link_rel = prod.get('url', url_base)
                    link_final = urljoin("https://www.jbl.com.pe", link_rel).split('?')[0].split('#')[0]

                    offers = prod.get('offers', {})
                    if isinstance(offers, list) and len(offers) > 0:
                        offers = offers[0]

                    p_o = float(offers.get('price', 0) or 0)
                    p_r = float(offers.get('highPrice', p_o) or p_o)

                    img_url = prod.get('image', '')
                    if isinstance(img_url, list) and len(img_url) > 0:
                        img_url = img_url[0]
                    
                    if img_url and not img_url.startswith('http'):
                        img_url = urljoin("https://www.jbl.com.pe", img_url)

                    if 0 < p_o <= limite:
                        productos_map[link_final] = {
                            "nombre": f"JBL - {nombre}",
                            "precio": p_o,
                            "precio_regular": max(p_r, p_o),
                            "link": link_final,
                            "img": str(img_url)
                        }
        except Exception: continue

    # ==============================================================================
    # CAPA 2: SCANNER HTML CONTENEDOR RAIZ (.product-tile)
    # ==============================================================================
    if not productos_map:
        # Priorizar la selección del contenedor principal product-tile
        tarjetas = soup.find_all(['div', 'article'], class_=lambda c: c and 'product-tile' in str(c).lower())
        if not tarjetas:
            tarjetas = soup.find_all(['div', 'article'], class_=lambda c: c and any(x in str(c).lower() for x in ['tile-body', 'grid-tile']))

        for card in tarjetas:
            try:
                # Subir al padre si se capturó únicamente tile-body
                if card.get('class') and 'tile-body' in card.get('class') and card.parent:
                    if card.parent.name in ['div', 'article']:
                        card = card.parent

                # 1. Enlace y Nombre Limpio
                pdp_link = card.find(class_=lambda c: c and 'pdp-link' in str(c).lower())
                a_tag = pdp_link.find('a', href=True) if pdp_link else card.find('a', href=True)
                if not a_tag: continue

                href = a_tag['href'].strip()
                if not href or any(x in href.lower() for x in ['/cart', '/checkout', '/account', '/servicio']):
                    continue

                link_final = urljoin("https://www.jbl.com.pe", href).split('?')[0].split('#')[0]

                if pdp_link:
                    nombre = pdp_link.get_text(strip=True).upper()
                else:
                    nombre = a_tag.get_text(strip=True).upper()

                nombre = re.sub(r'^/.*?\.(HTML|PHP)\s*', '', nombre, flags=re.IGNORECASE)
                nombre = re.sub(r'\s+', ' ', nombre).strip()

                if not nombre or len(nombre) < 3 or nombre in ['VER MÁS', 'COMPRAR', 'VER DETALLES']:
                    continue

                # 2. Extracción de Precios desde atributo content="799.00"
                p_o = 0.0
                p_r = 0.0

                spans_value = card.find_all('span', class_=lambda c: c and 'value' in str(c).lower())
                precios_attr = []
                for sp in spans_value:
                    if sp.get('content'):
                        val_num = limpiar_num_jbl(sp['content'])
                        if val_num > 0: precios_attr.append(val_num)

                if precios_attr:
                    precios_attr = sorted(list(set(precios_attr)))
                    p_o = precios_attr[0]
                    p_r = precios_attr[-1] if len(precios_attr) > 1 else p_o
                else:
                    texto_tarjeta = card.get_text()
                    precios_encontrados = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_tarjeta)
                    precios_numeros = [limpiar_num_jbl(p) for p in precios_encontrados if limpiar_num_jbl(p) > 0]
                    if precios_numeros:
                        precios_unicos = sorted(list(set(precios_numeros)))
                        p_o = precios_unicos[0]
                        p_r = precios_unicos[-1] if len(precios_unicos) > 1 else p_o

                if p_o <= 0: continue

                # 3. Extracción de Imagen desde image-container o etiqueta img.tile-image
                img_el = card.find('img', class_=lambda c: c and 'tile-image' in str(c).lower()) or card.find('img')
                img_url = ""
                if img_el:
                    img_url = img_el.get('src') or img_el.get('data-src') or img_el.get('srcset') or ""

                if img_url:
                    if ',' in img_url: img_url = img_url.split(',')[0].split(' ')[0]
                    if img_url.startswith('//'): img_url = 'https:' + img_url
                    elif not img_url.startswith('http'): img_url = urljoin("https://www.jbl.com.pe", img_url)

                if 'data:image' in img_url.lower() or 'pixel' in img_url.lower():
                    img_url = ""

                if 0 < p_o <= limite:
                    productos_map[link_final] = {
                        "nombre": f"JBL - {nombre}",
                        "precio": p_o,
                        "precio_regular": max(p_r, p_o),
                        "link": link_final,
                        "img": img_url
                    }
            except Exception: continue

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [JBL] ¡Éxito! Se indexaron {len(productos_finales)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [JBL] No se encontraron productos bajo el límite de S/. {limite:.2f}", "warning")

    return productos_finales
