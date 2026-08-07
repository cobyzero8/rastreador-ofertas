import re
import json
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from config import LISTA_USER_AGENTS
from utils import sanitizar_url, safe_log

def motor_juntoz(url, limite, headers=None):
    productos_map = {}
    url = sanitizar_url(url)
    
    def limpiar_num_juntoz(texto):
        if not texto: return 0.0
        texto = str(texto).replace('S/.', '').replace('S/', '').strip()
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
            "Referer": "https://juntoz.com/"
        }

    try:
        safe_log(f"📡 [Juntoz] Descargando catálogo GRATIS por HTML...", "info")
        session = requests.Session()
        resp = session.get(url, headers=headers, timeout=20, verify=False)
        
        if resp.status_code != 200:
            safe_log(f"🛑 [Juntoz] Error de servidor. Código HTTP: {resp.status_code}", "error")
            return []

        texto_html = resp.text
        soup = BeautifulSoup(texto_html, 'html.parser')

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
                        link_final = urljoin("https://juntoz.com", link_rel)

                        offers = prod.get('offers', {})
                        if isinstance(offers, list) and len(offers) > 0:
                            offers = offers[0]

                        p_o = float(offers.get('price', 0) or 0)
                        p_r = float(offers.get('highPrice', p_o) or p_o)

                        img_url = prod.get('image', '')
                        if isinstance(img_url, list) and len(img_url) > 0:
                            img_url = img_url[0]

                        if 0 < p_o <= limite:
                            productos_map[link_final] = {
                                "nombre": f"Juntoz - {nombre}",
                                "precio": p_o,
                                "precio_regular": max(p_r, p_o),
                                "link": link_final,
                                "img": str(img_url)
                            }
            except Exception: continue

        if not productos_map:
            enlaces_productos = []
            for a in soup.find_all('a', href=True):
                href = a['href'].lower()
                if ('/p/' in href or '/producto/' in href or '-p' in href) and not any(x in href for x in ['/politica', '/ayuda', '/terminos', '/catalogo', '/tienda']):
                    enlaces_productos.append(a)

            for a_el in enlaces_productos:
                try:
                    href_rel = a_el['href']
                    link_final = urljoin("https://juntoz.com", href_rel)
                    
                    contenedor_tarjeta = None
                    ancestro_actual = a_el.parent
                    
                    for _ in range(6):
                        if not ancestro_actual or ancestro_actual.name in ['body', 'html']: break
                        texto_ancestro = ancestro_actual.get_text()
                        if 'S/.' in texto_ancestro or 'S/' in texto_ancestro:
                            contenedor_tarjeta = ancestro_actual
                            break
                        ancestro_actual = ancestro_actual.parent

                    if not contenedor_tarjeta: continue

                    nombre = a_el.get_text(separator=" ").strip().upper()
                    if not nombre or len(nombre) < 5:
                        for otro_a in contenedor_tarjeta.find_all('a', href=True):
                            if otro_a['href'] == href_rel:
                                nombre_otro = otro_a.get_text(separator=" ").strip().upper()
                                if nombre_otro and len(nombre_otro) >= 5:
                                    nombre = nombre_otro
                                    break

                    if not nombre or len(nombre) < 5:
                        img_el = contenedor_tarjeta.find('img')
                        if img_el and img_el.get('alt'):
                            nombre = img_el['alt'].strip().upper()

                    if not nombre or len(nombre) < 5: continue
                    nombre = nombre.replace("AGREGAR A CARRITO", "").replace("AGREGAR", "").strip()
                    nombre = re.sub(r'\s+', ' ', nombre)

                    texto_tarjeta = contenedor_tarjeta.get_text()
                    textos_precios = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', texto_tarjeta)
                    if not textos_precios: continue

                    precios_numeros = [limpiar_num_juntoz(p) for p in textos_precios if limpiar_num_juntoz(p) > 0]
                    if not precios_numeros: continue

                    precios_unicos = sorted(list(set(precios_numeros)))
                    p_o = precios_unicos[0]
                    p_r = precios_unicos[-1] if len(precios_unicos) > 1 else p_o

                    img_el = contenedor_tarjeta.find('img')
                    img_url = ""
                    if img_el:
                        img_url = img_el.get('data-src') or img_el.get('src') or img_el.get('data-lazy') or img_el.get('data-original') or ""
                    
                    if img_url.startswith('//'): img_url = 'https:' + img_url
                    elif img_url and not img_url.startswith('http'): img_url = urljoin("https://juntoz.com", img_url)

                    if 'data:image' in img_url.lower() or 'pixel' in img_url.lower(): img_url = ""

                    if 0 < p_o <= limite:
                        if link_final in productos_map:
                            prod_existente = productos_map[link_final]
                            if len(nombre) > len(prod_existente['nombre']) or (img_url and not prod_existente['img']):
                                productos_map[link_final] = {
                                    "nombre": f"Juntoz - {nombre}",
                                    "precio": p_o,
                                    "precio_regular": max(p_r, p_o),
                                    "link": link_final,
                                    "img": img_url or prod_existente['img']
                                }
                        else:
                            productos_map[link_final] = {
                                "nombre": f"Juntoz - {nombre}",
                                "precio": p_o,
                                "precio_regular": max(p_r, p_o),
                                "link": link_final,
                                "img": img_url
                            }
                except Exception: continue

    except Exception as e:
        safe_log(f"🛑 [Juntoz] Error crítico inesperado: {e}", "error")

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [Juntoz] ¡Éxito! Se indexaron {len(productos_finales)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [Juntoz] No se encontraron productos bajo el límite de S/. {limite:.2f}", "warning")

    return productos_finales
