import os
import re
import json
import requests
import urllib3
import urllib.parse
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from utils import sanitizar_url, safe_log

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def obtener_key_natura():
    """
    Obtiene la clave de ScraperAPI para Natura desde st.secrets o variables de entorno.
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

def construir_url_pagina(url_base, num_pagina=1, page_size=48):
    """
    Asegura que la URL siempre incluya ?pageSize=48 desde la primera petición.
    """
    parsed = urllib.parse.urlparse(url_base)
    query_dict = urllib.parse.parse_qs(parsed.query)
    query_dict['page'] = [str(num_pagina)]
    query_dict['pageSize'] = [str(page_size)]
    
    new_query = urllib.parse.urlencode(query_dict, doseq=True)
    return urllib.parse.urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))

def consultar_natura_con_cascada(url_destino):
    """
    Consulta la URL destino ruteando por ScraperAPI para evitar bloqueos WAF (HTTP 403).
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Referer": "https://www.natura.com.pe/"
    }

    # Intento directo inicial
    try:
        resp = requests.get(url_destino, headers=headers, timeout=8, verify=False)
        if resp.status_code == 200 and len(resp.text) > 2000 and "desafortunadamente no encontramos" not in resp.text.lower():
            return resp
    except Exception:
        pass

    # Respaldo con ScraperAPI
    key = obtener_key_natura()
    if not key:
        safe_log("🛑 [NATURA] No se encontró clave de ScraperAPI en los secretos.", "error")
        return None

    try:
        safe_log("🛡️ [NATURA] Consultando vía ScraperAPI...", "info")
        payload = {
            'api_key': key,
            'url': url_destino,
            'country_code': 'us',
            'render': 'false'
        }
        resp_sc = requests.get('http://api.scraperapi.com', params=payload, headers=headers, timeout=30)
        if resp_sc.status_code == 200 and len(resp_sc.text) > 1000:
            return resp_sc
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

def normalizar_url_imagen(url_raw):
    """
    Valida y construye la URL del CDN de Demandware sin generar rutas 404 falsas.
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
        if 'Sites-natura-pe-storefront-catalog' in path_clean or 'dw/image' in path_clean:
            url_clean = 'https://production.na01.natura.com/' + path_clean
        else:
            url_clean = urljoin("https://www.natura.com.pe", path_clean)

    return url_clean

def extraer_imagen_real_natura(card, a_tag, href, full_html):
    """
    Busca la imagen real asociada al código NATPER-ID en todo el código HTML de la página.
    """
    card_str = str(card).replace('\\/', '/')
    comb = card_str + " " + str(a_tag)

    # 1. Extraer ID del producto (NATPER-XXXXX)
    match_id = re.search(r'NATPER-(\d+)', href + " " + comb, re.I)
    if match_id:
        natper_id = match_id.group(1)
        html_clean = full_html.replace('\\/', '/')

        # Búsqueda por URL completa de la foto en el CDN
        p1 = re.compile(rf'(https?://[^\s"\'>\\]+?NATPER-{natper_id}[^\s"\'>\\]*?\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'>\\]*)?)', re.I)
        m1 = p1.search(html_clean)
        if m1:
            return normalizar_url_imagen(m1.group(1))

        # Búsqueda por ruta de Demandware
        p2 = re.compile(rf'([^\s"\'>\\]*?dw[a-f0-9]+[^\s"\'>\\]*?NATPER-{natper_id}[^\s"\'>\\]*?\.(?:jpg|jpeg|png|webp)(?:\?[^\s"\'>\\]*)?)', re.I)
        m2 = p2.search(html_clean)
        if m2:
            return normalizar_url_imagen(m2.group(1))

    # 2. Búsqueda directa en la etiqueta img del DOM
    if hasattr(a_tag, 'find_all') and hasattr(card, 'find_all'):
        for tag in a_tag.find_all(['img', 'source']) + card.find_all(['img', 'source']):
            for attr in ['src', 'data-src', 'srcset', 'data-srcset']:
                val = tag.get(attr, '')
                url_norm = normalizar_url_imagen(val)
                if url_norm and any(ext in url_norm.lower() for ext in ['demandware', 'natura', 'products', '.jpg', '.jpeg', '.png', '.webp']):
                    return url_norm

    return ""

def procesar_producto_acumulativo(productos_map, link_final, nombre, p_o, p_r, img_url, limite, full_html=""):
    if not link_final or p_o <= 0 or p_o > limite:
        return

    nombre_clean = str(nombre).strip().upper()
    if nombre_clean.startswith("NATURA -"):
        nombre_clean = nombre_clean[8:].strip()
    elif nombre_clean.startswith("NATURA"):
        nombre_clean = nombre_clean[6:].strip()
    nombre_clean = nombre_clean.lstrip('-').strip()

    if not nombre_clean or len(nombre_clean) < 3 or nombre_clean in ['COMPRAR', 'VER MÁS', 'AGREGAR', 'AGREGAR A MI BOLSA']:
        return

    nombre_final = f"NATURA - {nombre_clean}"

    # Extraer y verificar URL de la imagen
    img_clean = normalizar_url_imagen(img_url)
    if not img_clean and full_html:
        img_clean = extraer_imagen_real_natura(None, None, link_final, full_html)

    if link_final in productos_map:
        if not productos_map[link_final]["img"] and img_clean:
            productos_map[link_final]["img"] = img_clean
        if len(nombre_final) > len(productos_map[link_final]["nombre"]):
            productos_map[link_final]["nombre"] = nombre_final
        if productos_map[link_final]["precio"] <= 0 and p_o > 0:
            productos_map[link_final]["precio"] = p_o
            productos_map[link_final]["precio_regular"] = max(p_r, p_o)
    else:
        productos_map[link_final] = {
            "nombre": nombre_final,
            "precio": p_o,
            "precio_regular": max(p_r, p_o),
            "link": link_final,
            "img": img_clean
        }

def extraer_de_json_next_data(full_html, productos_map, limite):
    """
    Extrae todos los productos almacenados en el objeto JSON __NEXT_DATA__.
    """
    match_script = re.search(r'<script\s+id="__NEXT_DATA__"\s+type="application/json">\s*({.*?})\s*</script>', full_html, re.DOTALL)
    if not match_script:
        return

    try:
        data = json.loads(match_script.group(1))
        
        def walk(obj):
            if isinstance(obj, dict):
                name = str(obj.get('productName') or obj.get('name') or obj.get('title') or '').strip()
                url_rel = str(obj.get('link') or obj.get('url') or obj.get('slug') or '').strip()
                pid = str(obj.get('productId') or obj.get('id') or '').strip()

                if name and (url_rel or pid) and len(name) > 3:
                    link_final = ""
                    if url_rel:
                        link_final = urljoin("https://www.natura.com.pe", url_rel).split('?')[0].split('#')[0]
                    elif pid:
                        clean_pid = pid if 'NATPER-' in pid else f"NATPER-{pid}"
                        link_final = f"https://www.natura.com.pe/p/producto/{clean_pid}"

                    if link_final and ('/p/' in link_final.lower() or 'NATPER-' in link_final):
                        price, list_price, img_url = 0.0, 0.0, ""

                        items = obj.get('items')
                        if isinstance(items, list) and len(items) > 0:
                            first_item = items[0]
                            imgs = first_item.get('images', [])
                            if isinstance(imgs, list) and len(imgs) > 0:
                                img_url = str(imgs[0].get('imageUrl') or imgs[0].get('url') or '')

                            sellers = first_item.get('sellers', [])
                            if isinstance(sellers, list) and len(sellers) > 0:
                                comm = sellers[0].get('commertialOffer', {}) or sellers[0].get('commercialOffer', {})
                                price = float(comm.get('Price') or comm.get('spotPrice') or 0.0)
                                list_price = float(comm.get('ListPrice') or price)

                        if price <= 0:
                            price = float(obj.get('spotPrice') or obj.get('price') or obj.get('value') or 0.0)
                            list_price = float(obj.get('listPrice') or price)

                        if not img_url:
                            img_url = str(obj.get('imageUrl') or obj.get('image') or '')

                        procesar_producto_acumulativo(productos_map, link_final, name, price, list_price, img_url, limite, full_html)

                for v in obj.values(): walk(v)
            elif isinstance(obj, list):
                for elem in obj: walk(elem)

        walk(data)
    except Exception:
        pass

def motor_natura(url, limite=999999.0, headers=None, max_paginas=2):
    """
    Motor extractor de Natura Perú configurado con pageSize=48 por defecto.
    """
    productos_map = {}
    url_base = sanitizar_url(url)

    safe_log("🚀 [NATURA] Iniciando escaneo del catálogo completo...", "info")

    for pagina in range(1, max_paginas + 1):
        # Generar siempre con pageSize=48 desde la Página 1
        url_pagina = construir_url_pagina(url_base, num_pagina=pagina, page_size=48)
        safe_log(f"📡 [NATURA] Consultando página {pagina}: {url_pagina}", "info")
        
        resp = consultar_natura_con_cascada(url_pagina)

        if not resp or resp.status_code != 200 or not resp.text:
            safe_log(f"⚠️ [NATURA] No se obtuvo respuesta válida en la página {pagina}.", "warning")
            break

        full_html = resp.text
        if "desafortunadamente no encontramos ningún resultado" in full_html.lower():
            safe_log(f"🏁 [NATURA] Fin del catálogo alcanzado en la página {pagina}.", "success")
            break

        soup = BeautifulSoup(full_html, 'html.parser')
        conteo_previo = len(productos_map)

        # 1. Extracción profunda desde el JSON __NEXT_DATA__
        extraer_de_json_next_data(full_html, productos_map, limite)

        # 2. Escaneo complementario del DOM de la grilla principal
        enlaces = soup.find_all('a', href=lambda h: h and '/p/' in str(h).lower())
        for a_tag in enlaces:
            try:
                href = a_tag['href'].strip()
                if any(x in href.lower() for x in ['/cart', '/checkout', '/login', '/mi-cuenta']):
                    continue

                link_final = urljoin("https://www.natura.com.pe", href).split('?')[0].split('#')[0]
                card = a_tag.find_parent(['div', 'article']) or a_tag

                img_el = card.find('img')
                nombre_raw = img_el.get('alt', '').strip() if img_el and img_el.get('alt') else a_tag.get_text(strip=True)

                texto_card = card.get_text(separator=' ', strip=True)
                precios_found = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_card)
                precios_num = [limpiar_precio_natura(p) for p in precios_found if limpiar_precio_natura(p) > 0]

                p_o, p_r = 0.0, 0.0
                if precios_num:
                    unicos = sorted(list(set(precios_num)))
                    p_o = unicos[0]
                    p_r = unicos[-1]

                img_url = extraer_imagen_real_natura(card, a_tag, href, full_html)

                procesar_producto_acumulativo(productos_map, link_final, nombre_raw, p_o, p_r, img_url, limite, full_html)
            except Exception:
                continue

        nuevos = len(productos_map) - conteo_previo
        safe_log(f"📊 [NATURA] Página {pagina}: {nuevos} nuevas ofertas agregadas (Total acumulado: {len(productos_map)}).", "info")

        if nuevos == 0 and pagina > 1:
            break

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [NATURA] ¡Éxito! Se indexaron un total de {len(productos_finales)} ofertas válidas.", "success")
    else:
        safe_log(f"⚠️ [NATURA] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
