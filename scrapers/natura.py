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
        if resp.status_code == 200 and len(resp.text) > 2000 and any(x in resp.text.lower() for x in ['product-price-por', '/p/', 'natura']):
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
            'render': 'false'  # 1 solo crédito por llamada
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

def extraer_nombre_limpio_natura(card, a_tag, href):
    """
    Extrae el nombre completo del producto probando atributos alt, slugs y texto del DOM.
    """
    # 1. Atributo ALT en imágenes dentro del enlace o tarjeta
    for img in a_tag.find_all('img') + card.find_all('img'):
        alt = img.get('alt', '').strip()
        if alt and len(alt) > 5 and not any(x in alt.upper() for x in ['LOGOTIPO', 'PROMO', 'ETIQUETA', 'AGREGAR']) and alt != '0':
            return alt.upper()

    # 2. Reconstrucción desde el Slug de la URL (/p/natura-homem-eau-de-parfum-masculino-coragio-100-ml/NATPER-186)
    match_slug = re.search(r'/p/([^/?#]+)', href)
    if match_slug:
        raw_slug = match_slug.group(1)
        slug_clean = re.sub(r'NATPER-[A-Z0-9_-]+$', '', raw_slug, flags=re.I).strip('-')
        parts = [p.capitalize() for p in slug_clean.split('-') if not p.isdigit() or len(p) <= 3]
        if len(parts) >= 2:
            txt_slug = " ".join(parts).upper()
            if len(txt_slug) > 5:
                return txt_slug

    # 3. Escaneo de etiquetas de texto
    candidatos = []
    for el in card.find_all(['p', 'span', 'h2', 'h3', 'h4', 'div']):
        txt = el.get_text(strip=True)
        if not txt or 'S/' in txt or any(b in txt.upper() for b in ['AGREGAR', 'BOLSA', 'COMPRAR', 'VER MÁS', 'PROMO', 'PRECIO']):
            continue
        if len(txt) > 3 and not re.search(r'-\d+%', txt) and 'ETIQUETA' not in txt.upper():
            candidatos.append(txt)

    if candidatos:
        candidatos.sort(key=len, reverse=True)
        return candidatos[0].upper()

    return ""

def normalizar_url_imagen(url_raw):
    """
    Limpia, des-escapa y convierte cualquier URL parcial en una URL absoluta válida HTTP(S).
    """
    if not url_raw or 'data:image' in str(url_raw).lower():
        return ""

    # Des-escapar barras de JSON (ej: https:\/\/ -> https://)
    url_clean = str(url_raw).replace('\\/', '/').replace('&amp;', '&').strip()

    # Si vienen múltiples imágenes separadas por coma (srcset)
    if ',' in url_clean:
        url_clean = url_clean.split(',')[0].strip().split(' ')[0]
    elif ' ' in url_clean:
        url_clean = url_clean.split(' ')[0]

    if url_clean.startswith('//'):
        url_clean = 'https:' + url_clean
    elif url_clean.startswith('/'):
        url_clean = urljoin("https://www.natura.com.pe", url_clean)
    elif not url_clean.startswith('http'):
        url_clean = 'https://' + url_clean

    return url_clean

def extraer_imagen_natura(card, a_tag):
    """
    Rastrea exhaustivamente las imágenes reales del CDN de Demandware/Natura.
    """
    card_html_raw = str(card).replace('\\/', '/')

    # Nivel 1: Inspección directa de etiquetas HTML <img>, <source>, etc.
    for tag in a_tag.find_all(['img', 'source']) + card.find_all(['img', 'source']):
        for attr in ['src', 'data-src', 'srcset', 'data-srcset', 'data-lazy', 'data-original']:
            val = tag.get(attr, '')
            url_norm = normalizar_url_imagen(val)
            if url_norm and any(ext in url_norm.lower() for ext in ['demandware', 'natura', 'products', 'produto', '.jpg', '.jpeg', '.png', '.webp']):
                return url_norm

    # Nivel 2: Expresión regular sobre la cadena HTML completa de la tarjeta
    # Coincidencia con CDN de Demandware (Natura)
    match_dw = re.search(r'(https?://[^\s"\'>\\]+?demandware[^\s"\'>\\]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'>\\]*)?)', card_html_raw, re.I)
    if match_dw:
        return normalizar_url_imagen(match_dw.group(1))

    # Nivel 3: Coincidencia con cualquier URL de imagen válida en la tarjeta
    match_gen = re.search(r'(https?://[^\s"\'>\\]+?\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'>\\]*)?)', card_html_raw, re.I)
    if match_gen and 'data:image' not in match_gen.group(1).lower():
        return normalizar_url_imagen(match_gen.group(1))

    return ""

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

    # Buscar enlaces directos a productos que contienen /p/
    enlaces_p = soup.find_all('a', href=lambda h: h and '/p/' in str(h).lower())

    for a_tag in enlaces_p:
        try:
            href = a_tag['href'].strip()
            if not href or any(x in href.lower() for x in ['/cart', '/checkout', '/login', '/mi-cuenta']):
                continue

            link_final = urljoin("https://www.natura.com.pe", href).split('?')[0].split('#')[0]
            card = a_tag.find_parent(['div', 'article', 'li']) or a_tag

            # 1. Extracción e Higienización del Nombre
            nombre_raw = extraer_nombre_limpio_natura(card, a_tag, href)
            
            nombre_clean = nombre_raw.strip().upper()
            if nombre_clean.startswith("NATURA -"):
                nombre_clean = nombre_clean[8:].strip()
            elif nombre_clean.startswith("NATURA"):
                nombre_clean = nombre_clean[6:].strip()

            nombre_clean = nombre_clean.lstrip('-').strip()

            if not nombre_clean or len(nombre_clean) < 3 or nombre_clean in ['COMPRAR', 'VER MÁS', 'AGREGAR', 'AGREGAR A MI BOLSA']:
                continue

            nombre_final = f"NATURA - {nombre_clean}"

            # 2. Extracción de Precios
            el_por = card.find(id=lambda i: i and 'product-price-por' in str(i).lower())
            el_de = card.find(id=lambda i: i and 'product-price-de' in str(i).lower())

            p_o = limpiar_precio_natura(el_por.get_text()) if el_por else 0.0
            p_r = limpiar_precio_natura(el_de.get_text()) if el_de else p_o

            if p_o <= 0:
                texto_card = card.get_text(separator=' ', strip=True)
                precios_encontrados = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_card)
                precios_numeros = [limpiar_precio_natura(p) for p in precios_encontrados if limpiar_precio_natura(p) > 0]

                if not precios_numeros: continue

                precios_unicos = sorted(list(set(precios_numeros)))
                p_o = precios_unicos[0]
                p_r = precios_unicos[-1] if len(precios_unicos) > 1 else p_o

            # 3. Extracción de Imagen legítima
            img_url = extraer_imagen_natura(card, a_tag)

            if 0 < p_o <= limite:
                productos_map[link_final] = {
                    "nombre": nombre_final,
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
