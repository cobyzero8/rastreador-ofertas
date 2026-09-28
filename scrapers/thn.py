import re
import json
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from config import LISTA_USER_AGENTS
from utils import sanitizar_url, limpiar_precio_pnp, safe_log

def motor_thn(url, limite):
    productos = []
    url = sanitizar_url(url)
    try:
        headers = {
            "User-Agent": random.choice(LISTA_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-PE,es;q=0.9"
        }
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        if resp.status_code != 200:
            return []
        
        soup = BeautifulSoup(resp.text, 'html.parser')

        # 1. Extracción por datos estructurados JSON-LD de Shopify
        scripts_json = soup.find_all('script', type=re.compile(r'ld\+json', re.I))
        for script in scripts_json:
            try:
                data = json.loads(script.string or '{}')
                items = []
                if isinstance(data, dict):
                    if data.get('@type') in ['ItemList', 'Product']:
                        items = data.get('itemListElement', [data])
                elif isinstance(data, list):
                    items = data

                for item in items:
                    prod_obj = item.get('item', item) if isinstance(item, dict) else {}
                    if isinstance(prod_obj, dict) and prod_obj.get('@type') == 'Product':
                        nombre = str(prod_obj.get('name', '')).strip().upper()
                        link = prod_obj.get('url', url)
                        if not link.startswith('http'):
                            link = urljoin("https://www.thn.pe", link)

                        offers = prod_obj.get('offers', {})
                        if isinstance(offers, list) and len(offers) > 0:
                            offers = offers[0]

                        p_o = limpiar_precio_pnp(offers.get('price', 0))
                        img = prod_obj.get('image', '')
                        if isinstance(img, list) and len(img) > 0:
                            img = img[0]
                        elif isinstance(img, dict):
                            img = img.get('url', '')

                        if 0 < p_o <= limite and nombre:
                            productos.append({
                                "nombre": f"THN - {nombre}",
                                "precio": p_o,
                                "precio_regular": p_o,
                                "link": link.split('?')[0],
                                "img": str(img)
                            })
            except Exception:
                continue

        # 2. Extracción directa sobre el DOM de Shopify (tarjetas y enlaces /products/)
        tarjetas = soup.find_all(lambda tag: tag.name in ['div', 'article', 'li'] and tag.find('a', href=re.compile(r'/products/')))

        for t in tarjetas:
            try:
                a_el = t.find('a', href=re.compile(r'/products/'))
                if not a_el:
                    continue

                link_final = urljoin("https://www.thn.pe", a_el['href']).split('?')[0]

                # Título del producto
                tit_el = t.find(['h1', 'h2', 'h3', 'h4', 'span', 'p', 'div'], class_=re.compile(r'(title|name|card__heading|header)', re.I))
                nombre = tit_el.text.strip().upper() if tit_el else a_el.text.strip().upper()
                nombre = " ".join(nombre.split())

                if len(nombre) < 3 or "AÑADIR" in nombre or "S/." in nombre:
                    continue

                # Extracción de precios en el contenedor
                textos_precios = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', t.text)
                if not textos_precios:
                    continue

                nums = sorted(list(set([limpiar_precio_pnp(p) for p in textos_precios if limpiar_precio_pnp(p) > 0])))
                if not nums:
                    continue

                p_o = nums[0]
                p_r = nums[-1] if len(nums) > 1 else p_o

                if 0 < p_o <= limite:
                    img_tags = t.find_all('img')
                    img = ""
                    for img_el in img_tags:
                        src = img_el.get('data-src') or img_el.get('src') or img_el.get('srcset') or ""
                        if src and 'data:image' not in str(src).lower() and 'pixel' not in str(src).lower():
                            img = str(src).split('?')[0].split()[0]
                            break

                    if str(img).startswith('//'):
                        img = 'https:' + str(img)

                    productos.append({
                        "nombre": f"THN - {nombre}",
                        "precio": p_o,
                        "precio_regular": max(p_r, p_o),
                        "link": link_final,
                        "img": img
                    })
            except Exception:
                continue

    except Exception as e:
        safe_log(f"Aviso en motor THN: {e}", "caption")

    # Eliminación de duplicados por enlace
    vistos = set()
    productos_unicos = []
    for p in productos:
        if p['link'] not in vistos:
            vistos.add(p['link'])
            productos_unicos.append(p)

    return productos_unicos
