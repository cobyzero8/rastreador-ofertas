import re
import json
import random
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from config import LISTA_USER_AGENTS
from utils import sanitizar_url, safe_log

# Desactivar advertencias de SSL deshabilitado
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def motor_jbl(url, limite=999999.0, headers=None):
    """
    Motor extractor para JBL Perú (jbl.com.pe) optimizado contra bloqueos Akamai/SFCC
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

    # Cabeceras completas de un navegador Chrome real para evitar HTTP 403
    headers_navegador = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "es-PE,es-419;q=0.9,es;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Referer": "https://www.jbl.com.pe/"
    }

    if headers:
        headers_navegador.update(headers)

    session = requests.Session()
    resp = None

    # Intento directo a la URL de catálogo
    try:
        safe_log(f"📡 [JBL] Consultando catálogo en directo...", "info")
        r = session.get(url_base, headers=headers_navegador, timeout=20, verify=False)
        
        if r.status_code == 200:
            resp = r
        else:
            safe_log(f"🛑 [JBL] El servidor respondió con HTTP {r.status_code}", "error")
            
            # Reintento alternativo con parámetro AJAX de Salesforce Commerce Cloud
            sep = "&" if "?" in url_base else "?"
            url_ajax = f"{url_base}{sep}format=ajax"
            headers_ajax = headers_navegador.copy()
            headers_ajax["X-Requested-With"] = "XMLHttpRequest"
            
            safe_log(f"🔄 [JBL] Reintentando vía endpoint AJAX...", "info")
            r_ajax = session.get(url_ajax, headers=headers_ajax, timeout=20, verify=False)
            if r_ajax.status_code == 200:
                resp = r_ajax
            else:
                safe_log(f"🛑 [JBL] Reintento AJAX falló con HTTP {r_ajax.status_code}", "error")

    except Exception as ex:
        safe_log(f"🚨 [JBL] Error de conexión: {ex}", "error")

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
    # CAPA 2: SCANNER HTML POR CONTENEDORES DE PRODUCTO
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
