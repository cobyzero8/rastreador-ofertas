import re
import json
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from config import LISTA_USER_AGENTS
from utils import sanitizar_url, safe_log

def motor_jbl(url, limite=999999.0, headers=None):
    """
    Motor extractor de productos optimizado para JBL Perú (Salesforce Commerce Cloud)
    """
    productos_map = {}
    url_base = sanitizar_url(url)
    
    # Inyectar parámetro format=ajax si no existe para forzar la entrega del catálogo en HTML
    if "format=ajax" not in url_base:
        sep = "&" if "?" in url_base else "?"
        url_fetch = f"{url_base}{sep}format=ajax"
    else:
        url_fetch = url_base

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

    headers_base = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-PE,es-419;q=0.9,es;q=0.8",
        "Referer": "https://www.jbl.com.pe/",
        "X-Requested-With": "XMLHttpRequest"
    }
    if headers:
        headers_base.update(headers)

    session = requests.Session()
    resp = None

    # Probar con URL AJAX primero y luego con la URL normal si no responde
    for target_url in [url_fetch, url_base]:
        try:
            safe_log(f"📡 [JBL] Consultando catálogo desde: {target_url}", "info")
            r = session.get(target_url, headers=headers_base, timeout=20, verify=False)
            if r.status_code == 200 and len(r.text) > 1000:
                resp = r
                break
        except Exception as ex:
            safe_log(f"⚠️ [JBL] Error conectando a {target_url}: {ex}", "warning")

    if not resp or resp.status_code != 200:
        safe_log(f"🛑 [JBL] No se obtuvo respuesta válida (HTTP 200) de JBL.", "error")
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
    # CAPA 2: SCANNER HTML DE ENLACES .HTML DE PRODUCTO
    # ==============================================================================
    if not productos_map:
        for a in soup.find_all('a', href=True):
            try:
                href = a['href'].strip()
                if not href or not href.lower().endswith('.html'):
                    continue
                if any(x in href.lower() for x in ['/cart', '/checkout', '/account', '/servicio', '/ayuda', '/login', '/atencion']):
                    continue

                link_final = urljoin("https://www.jbl.com.pe", href).split('?')[0].split('#')[0]
                
                contenedor = a.parent
                encontrado = False
                for _ in range(6):
                    if not contenedor or contenedor.name in ['body', 'html']:
                        break
                    texto_cont = contenedor.get_text()
                    if ('S/' in texto_cont or 'PEN' in texto_cont or '$' in texto_cont) and re.search(r'\d+', texto_cont):
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
                    elif img_in and img_in.get('title'):
                        nombre = img_in['title'].strip().upper()

                if not nombre or len(nombre) < 3 or nombre in ['VER MÁS', 'COMPRAR', 'VER DETALLES', 'JBL']:
                    continue

                nombre = re.sub(r'\s+', ' ', nombre)

                texto_tarjeta = contenedor.get_text()
                precios_encontrados = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_tarjeta)
                
                precios_numeros = [limpiar_num_jbl(p) for p in precios_encontrados if limpiar_num_jbl(p) > 0]
                if not precios_numeros:
                    precios_encontrados = re.findall(r'\b\d{2,5}(?:\.\d{2})?\b', texto_tarjeta)
                    precios_numeros = [limpiar_num_jbl(p) for p in precios_encontrados if 10 <= limpiar_num_jbl(p) <= 20000]

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
