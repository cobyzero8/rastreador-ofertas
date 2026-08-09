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
    """
    Recopila las claves de ScraperAPI exclusivas para JBL en orden secuencial.
    """
    keys = []
    nombres_keys = ["SCRAPERAPI_JBL_KEY", "SCRAPERAPI_JBL_KEY_2", "SCRAPERAPI_JBL_KEY_3"]

    # 1. Buscar en Streamlit Secrets
    try:
        import streamlit as st
        for name in nombres_keys:
            if name in st.secrets and st.secrets[name]:
                val = str(st.secrets[name]).strip()
                if len(val) > 10 and "tu_clave" not in val:
                    keys.append(val)
    except Exception:
        pass

    # 2. Buscar en variables de entorno (GitHub Actions o servidor local)
    if not keys:
        for name in nombres_keys:
            val = os.environ.get(name, "").strip()
            if val and len(val) > 10 and "tu_clave" not in val:
                keys.append(val)

    return keys

def consultar_jbl_con_cascada(url_destino):
    """
    1. Intenta petición directa (0 créditos).
    2. Si falla (HTTP 403/401), usa SCRAPERAPI_JBL_KEY.
    3. Si la Key 1 se agota, pasa a SCRAPERAPI_JBL_KEY_2, luego a SCRAPERAPI_JBL_KEY_3.
    """
    session = requests.Session()
    headers_directos = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9",
        "Referer": "https://www.jbl.com.pe/"
    }

    # 🟢 PASO 1: Conexión directa gratuita
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

    # 🛡️ PASO 2: Cascada secuencial de Keys dedicadas para JBL
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

def motor_jbl(url, limite=999999.0, headers=None):
    """
    Motor extractor principal para la tienda JBL Perú
    """
    productos_map = {}
    url_base = sanitizar_url(url)

    def limpiar_num_jbl(texto):
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

    resp = consultar_jbl_con_cascada(url_base)

    if not resp or resp.status_code != 200 or not resp.text:
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')

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
    # CAPA 2: SCANNER HTML DE PRODUCTOS
    # ==============================================================================
    if not productos_map:
        for a in soup.find_all('a', href=True):
            try:
                href = a['href'].strip()
                if not href or not href.lower().endswith('.html'):
                    continue
                if any(x in href.lower() for x in ['/cart', '/checkout', '/account', '/servicio', '/ayuda', '/login']):
                    continue

                link_final = urljoin("https://www.jbl.com.pe", href).split('?')[0].split('#')[0]
                
                contenedor = a.parent
                encontrado = False
                for _ in range(6):
                    if not contenedor or contenedor.name in ['body', 'html']:
                        break
                    texto_cont = contenedor.get_text()
                    if ('S/' in texto_cont or 'PEN' in texto_cont) and re.search(r'\d+', texto_cont):
                        encontrado = True
                        break
                    contenedor = contenedor.parent

                if not encontrado or not contenedor:
                    continue

                nombre = a.get_text(strip=True).upper()
                if not nombre or len(nombre) < 3:
                    img_in = contenedor.find('img')
                    if img_in and img_in.get('alt'):
                        nombre = img_in['alt'].strip().upper()

                if not nombre or len(nombre) < 3 or nombre in ['VER MÁS', 'COMPRAR', 'VER DETALLES']:
                    continue

                nombre = re.sub(r'\s+', ' ', nombre)

                texto_tarjeta = contenedor.get_text()
                precios_encontrados = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_tarjeta)
                
                precios_numeros = [limpiar_num_jbl(p) for p in precios_encontrados if limpiar_num_jbl(p) > 0]
                if not precios_numeros: continue

                precios_unicos = sorted(list(set(precios_numeros)))
                p_o = precios_unicos[0]
                p_r = precios_unicos[-1] if len(precios_unicos) > 1 else p_o

                img_el = contenedor.find('img')
                img_url = ""
                if img_el:
                    img_url = img_el.get('data-src') or img_el.get('src') or img_el.get('data-srcset') or img_el.get('srcset') or ""

                if img_url:
                    if ',' in img_url: img_url = img_url.split(',')[0].split(' ')[0]
                    if img_url.startswith('//'): img_url = 'https:' + img_url
                    elif not img_url.startswith('http'): img_url = urljoin("https://www.jbl.com.pe", img_url)

                if 'data:image' in img_url.lower() or 'pixel' in img_url.lower():
                    img_url = ""

                if 0 < p_o <= limite:
                    if link_final in productos_map:
                        prod_exist = productos_map[link_final]
                        if len(nombre) > len(prod_exist['nombre']) or (img_url and not prod_exist['img']):
                            productos_map[link_final] = {
                                "nombre": f"JBL - {nombre}",
                                "precio": p_o,
                                "precio_regular": max(p_r, p_o),
                                "link": link_final,
                                "img": img_url or prod_exist['img']
                            }
                    else:
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
