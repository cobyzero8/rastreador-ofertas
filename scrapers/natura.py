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

            # 1. Extracción e inspección limpia de Imagen
            img_el = a_tag.find('img') or card.find('img')
            img_url = ""
            nombre_alt = ""

            if img_el:
                if img_el.get('alt') and len(img_el['alt'].strip()) > 3:
                    nombre_alt = img_el['alt'].strip()

                # Recorrer candidatos a URL de imagen evitando placeholders data:image
                for attr in ['src', 'data-src', 'data-lazy', 'srcset', 'data-srcset']:
                    val = img_el.get(attr, '')
                    if val and 'data:image' not in val.lower():
                        if ',' in val:
                            val = val.split(',')[0].strip().split(' ')[0]
                        if val.startswith('//'):
                            val = 'https:' + val
                        elif not val.startswith('http'):
                            val = urljoin("https://www.natura.com.pe", val)
                        img_url = val
                        break

            # 2. Extracción limpia de Nombre (excluyendo insignias de descuento)
            nombre = ""
            if nombre_alt and not any(x in nombre_alt.upper() for x in ['PROMO', 'ETIQUETA', 'PRECIO', '-']):
                nombre = nombre_alt.strip().upper()

            if not nombre or len(nombre) < 3:
                for tag in card.find_all(['h2', 'h3', 'h4', 'p', 'span', 'a']):
                    txt = tag.get_text(strip=True)
                    if not txt or 'S/' in txt or txt.upper() in ['AGREGAR', 'AGREGAR A MI BOLSA', 'COMPRAR', 'VER MÁS', 'PROMO FLASH', 'PRECIO FINAL']:
                        continue
                    if len(txt) > 3 and not re.search(r'-\d+%', txt) and 'ETIQUETA' not in txt.upper():
                        nombre = txt.strip().upper()
                        break

            # Limpieza quirúrgica del nombre
            nombre = re.sub(r'-\d+%', '', nombre)
            nombre = re.sub(r'ETIQUETA', '', nombre, flags=re.I)
            nombre = re.sub(r'S/\.?\s*\d+[\d\.,]*', '', nombre)
            nombre = re.sub(r'\s+', ' ', nombre).strip()

            if not nombre or len(nombre) < 3 or nombre in ['COMPRAR', 'VER MÁS', 'AGREGAR', 'AGREGAR A MI BOLSA']:
                continue

            # 3. Precios
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
