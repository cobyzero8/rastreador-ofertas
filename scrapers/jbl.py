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
    Motor extractor de productos para la tienda oficial de JBL Perú (jbl.com.pe)
    Soporta URLs de audífonos, parlantes portátiles, barras de sonido, etc.
    """
    productos_map = {}
    url = sanitizar_url(url)
    
    def limpiar_num_jbl(texto):
        if not texto: return 0.0
        texto = str(texto).replace('S/.', '').replace('S/', '').replace('PEN', '').strip()
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

    if not headers:
        headers = {
            "User-Agent": random.choice(LISTA_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
            "Referer": "https://www.jbl.com.pe/"
        }

    try:
        safe_log(f"📡 [JBL] Descargando catálogo por HTML...", "info")
        session = requests.Session()
        resp = session.get(url, headers=headers, timeout=20, verify=False)
        
        if resp.status_code != 200:
            safe_log(f"🛑 [JBL] Error de servidor. Código HTTP: {resp.status_code}", "error")
            return []

        texto_html = resp.text
        soup = BeautifulSoup(texto_html, 'html.parser')

        # ==============================================================================
        # CAPA 1: EXTRACCIÓN DE DATOS ESTRUCTURADOS JSON-LD
        # ==============================================================================
        scripts_json = soup.find_all('script', type='application/ld+json')
        for s in scripts_json:
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

                        link_rel = prod.get('url', url)
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
        # CAPA 2: FALLBACK HTML (PRODUCT TILES Y CONTENEDORES)
        # ==============================================================================
        if not productos_map:
            # Buscar contenedores de productos (módulos típicos de Salesforce Commerce Cloud / JBL)
            tarjetas = soup.find_all(['div', 'article'], class_=lambda c: c and any(
                x in c.lower() for x in ['product-tile', 'product', 'tile-body', 'grid-tile', 'product-grid-item']
            ))

            for card in tarjetas:
                try:
                    # 1. Obtener Enlace y Nombre
                    a_tag = card.find('a', href=True, class_=lambda cl: cl and 'pdp-link' in cl.lower()) or \
                            card.find('a', href=True)
                    if not a_tag: continue

                    href = a_tag['href']
                    if not href or any(x in href.lower() for x in ['javascript:', '#', '/cart', '/login']):
                        continue

                    link_final = urljoin("https://www.jbl.com.pe", href).split('?')[0].split('#')[0]

                    # Nombre del producto
                    nombre_el = card.find(['h2', 'h3', 'div', 'span', 'a'], class_=lambda cl: cl and any(
                        x in cl.lower() for x in ['name', 'title', 'pdp-link']
                    ))
                    nombre = nombre_el.get_text(strip=True).upper() if nombre_el else a_tag.get_text(strip=True).upper()
                    
                    if not nombre or len(nombre) < 3:
                        img_el_tmp = card.find('img')
                        if img_el_tmp and img_el_tmp.get('alt'):
                            nombre = img_el_tmp['alt'].strip().upper()

                    if not nombre or len(nombre) < 3: continue
                    nombre = re.sub(r'\s+', ' ', nombre)

                    # 2. Extraer Precios
                    texto_card = card.get_text()
                    precios_encontrados = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_card)
                    
                    precios_numeros = [limpiar_num_jbl(p) for p in precios_encontrados if limpiar_num_juntoz(p) > 0] if 'limpiar_num_juntoz' in locals() else [limpiar_num_jbl(p) for p in precios_encontrados if limpiar_num_jbl(p) > 0]
                    
                    if not precios_numeros: continue

                    precios_unicos = sorted(list(set(precios_numeros)))
                    p_o = precios_unicos[0]
                    p_r = precios_unicos[-1] if len(precios_unicos) > 1 else p_o

                    # 3. Extraer Imagen
                    img_el = card.find('img')
                    img_url = ""
                    if img_el:
                        img_url = img_el.get('src') or img_el.get('data-src') or img_el.get('data-srcset') or img_el.get('srcset') or ""
                    
                    if img_url:
                        if ',' in img_url: img_url = img_url.split(',')[0].split(' ')[0]
                        if img_url.startswith('//'): img_url = 'https:' + img_url
                        elif not img_url.startswith('http'): img_url = urljoin("https://www.jbl.com.pe", img_url)

                    if 'data:image' in img_url.lower() or 'placeholder' in img_url.lower():
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

    except Exception as e:
        safe_log(f"🛑 [JBL] Error crítico inesperado: {e}", "error")

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [JBL] ¡Éxito! Se indexaron {len(productos_finales)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [JBL] No se encontraron productos bajo el límite de S/. {limite:.2f}", "warning")

    return productos_finales
