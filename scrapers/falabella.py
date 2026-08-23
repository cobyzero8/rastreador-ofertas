import time
import json
import random
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from utils import sanitizar_url, safe_float, es_error_de_precio, safe_log
from config import LISTA_USER_AGENTS

def normalizar_imagen_falabella(raw_img, link_final):
    """
    Limpia y construye una URL de imagen válida para Falabella
    compatible al 100% con la API de Telegram.
    """
    img_str = str(raw_img or "").strip()

    # Si no hay imagen o es un SVG/data-uri, extraer ID del producto como fallback
    if not img_str or len(img_str) < 10 or 'data:image' in img_str:
        clean_url = link_final.split('?')[0].split('#')[0]
        match_id = [t for t in clean_url.split('/') if t.isdigit() and len(t) >= 7]
        if match_id:
            return f"https://falabella.scene7.com/is/image/FalabellaPE/{match_id[-1]}_1?wid=800&hei=800&qlt=80"
        return ""

    # Limpiar comas y atributos de srcset
    img_str = img_str.split(' ')[0].strip().rstrip(',')

    # Corregir prefijos relativas (// o /)
    if img_str.startswith('//'):
        img_str = 'https:' + img_str
    elif img_str.startswith('/'):
        if '/is/image/' in img_str:
            img_str = 'https://falabella.scene7.com' + img_str
        else:
            img_str = 'https://www.falabella.com.pe' + img_str
    elif not img_str.startswith('http'):
        img_str = 'https://' + img_str

    # Optimizar Scene7 para Telegram
    if 'scene7.com' in img_str:
        base_img = img_str.split('?')[0]
        img_str = f"{base_img}?wid=800&hei=800&qlt=80"

    return img_str


def motor_falabella(url, limite=999999.0, headers=None):
    """
    Scraper optimizado para Falabella Perú.
    Extrae estrictamente tarjetas de productos evitando la lectura de filtros/facetas.
    """
    if headers is None:
        user_agent = random.choice(LISTA_USER_AGENTS) if 'LISTA_USER_AGENTS' in globals() else "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        }

    productos = []
    url = sanitizar_url(url)
    
    try:
        texto_html = ""
        status_code = 0
        for intento in range(1, 3):
            try:
                resp = requests.get(url, headers=headers, timeout=15, verify=False)
                texto_html = resp.text
                status_code = resp.status_code
            except Exception:
                pass
            if status_code == 200 and len(texto_html) > 5000:
                break
            else:
                time.sleep(random.uniform(1.0, 2.5))
        
        if status_code != 200 or len(texto_html) < 5000:
            return []
            
        soup = BeautifulSoup(texto_html, 'html.parser')
        
        # --- CAPA 1: EXTRACCIÓN VÍA NEXT_DATA (JSON) ---
        next_data_script = soup.find("script", id="__NEXT_DATA__")
        if next_data_script and next_data_script.string:
            try:
                data = json.loads(next_data_script.string)
                page_props = data.get("props", {}).get("pageProps", {})
                
                results = []
                if "searchResult" in page_props and isinstance(page_props["searchResult"], dict):
                    results = page_props["searchResult"].get("content", {}).get("results", [])
                
                if not results and "results" in page_props:
                    results = page_props.get("results", [])

                for item in results:
                    if not isinstance(item, dict):
                        continue
                    
                    # 1. Debe ser un producto real con enlace hacia /product/
                    link_rel = item.get('url') or item.get('link') or item.get('href') or ''
                    if not link_rel or '/product/' not in link_rel:
                        continue
                    
                    prod_id = item.get('productId') or item.get('skuId') or item.get('id')
                    if not prod_id:
                        continue

                    # 2. Validar Nombre Completo
                    nombre = str(item.get('displayName') or item.get('title') or item.get('productName') or '').strip().upper()
                    if len(nombre) < 8:
                        continue

                    link_final = urljoin("https://www.falabella.com.pe", link_rel)

                    # 3. Extracción de Precios desde la lista 'prices'
                    prices_list = item.get('prices') or []
                    if isinstance(prices_list, dict):
                        prices_list = [prices_list]

                    precio_oferta = 0.0
                    precio_regular = 0.0

                    if isinstance(prices_list, list):
                        for p in prices_list:
                            if not isinstance(p, dict):
                                continue
                            p_type = str(p.get("type", "")).lower()
                            raw_val = p.get("price") or p.get("value")
                            
                            if isinstance(raw_val, list) and len(raw_val) > 0:
                                raw_val = raw_val[0]
                            
                            val = safe_float(raw_val)
                            if val <= 0:
                                continue

                            if any(x in p_type for x in ["sale", "event", "oferta", "internet", "current", "cmr", "card", "eventprice"]):
                                precio_oferta = val if (precio_oferta == 0 or val < precio_oferta) else precio_oferta
                            elif any(x in p_type for x in ["list", "original", "regular", "normal", "normalprice"]):
                                precio_regular = val if (precio_regular == 0 or val > precio_regular) else precio_regular

                    if precio_oferta == 0.0 and prices_list:
                        valid_p = []
                        for p in prices_list:
                            if isinstance(p, dict):
                                rv = p.get("price") or p.get("value")
                                if isinstance(rv, list) and rv:
                                    rv = rv[0]
                                v = safe_float(rv)
                                if v > 0:
                                    valid_p.append(v)
                        if valid_p:
                            precio_oferta = min(valid_p)
                            precio_regular = max(valid_p)

                    if precio_regular == 0.0:
                        precio_regular = precio_oferta

                    if precio_oferta < 10.0 or es_error_de_precio(precio_oferta, precio_regular, precio_regular) or precio_oferta > limite:
                        continue

                    # 4. Extracción e higienizado de Imagen HD
                    raw_img = ""
                    media_list = item.get("mediaUrls") or item.get("media") or item.get("images") or item.get("multimedia") or []
                    if isinstance(media_list, list) and len(media_list) > 0:
                        first_m = media_list[0]
                        if isinstance(first_m, dict):
                            raw_img = first_m.get("url") or first_m.get("src") or ""
                        elif isinstance(first_m, str):
                            raw_img = first_m
                    elif isinstance(media_list, dict):
                        raw_img = media_list.get("url") or media_list.get("src") or ""

                    img_url = normalizar_imagen_falabella(raw_img, link_final)

                    productos.append({
                        "nombre": f"FALABELLA - {nombre}",
                        "precio": precio_oferta,
                        "precio_regular": max(precio_regular, precio_oferta),
                        "link": link_final,
                        "img": img_url
                    })
            except Exception as ex_json:
                safe_log(f"⚠️ Error procesando JSON Falabella: {ex_json}", "warning")

        # --- CAPA 2: FALLBACK HTML ---
        if not productos:
            items = soup.find_all(['div', 'li', 'article'], class_=re.compile(r'(pod|card|product-item)', re.I))
            for t in items:
                try:
                    a_el = t.find('a', href=True)
                    if not a_el or '/product/' not in a_el['href']:
                        continue

                    link_final = urljoin("https://www.falabella.com.pe", a_el['href'])

                    tit_el = t.find(['b', 'span', 'p', 'h3', 'h4'], class_=re.compile(r'(title|name|displayName)', re.I))
                    nombre_txt = tit_el.text.strip().upper() if tit_el else ""
                    if len(nombre_txt) < 8:
                        continue

                    el_event = t.find(attrs={"data-event-price": True}) or t.select_one('[data-event-price]')
                    precio_oferta = safe_float(el_event.get('data-event-price')) if el_event else 0.0

                    el_normal = t.find(attrs={"data-normal-price": True}) or t.select_one('[data-normal-price]')
                    precio_regular = safe_float(el_normal.get('data-normal-price')) if el_normal else precio_oferta

                    if precio_oferta < 10.0 or es_error_de_precio(precio_oferta, precio_regular, precio_regular) or precio_oferta > limite:
                        continue

                    img_el = t.select_one('img[id^="testId-pod-image-"]') or t.find('img')
                    raw_img = ""
                    if img_el:
                        for attr in ['data-srcset', 'srcset', 'data-src', 'src']:
                            val = img_el.get(attr)
                            if val and 'data:image' not in str(val) and len(str(val)) > 10:
                                raw_img = str(val).split(' ')[0].strip()
                                break

                    img_url = normalizar_imagen_falabella(raw_img, link_final)

                    productos.append({
                        "nombre": f"FALABELLA - {nombre_txt}",
                        "precio": precio_oferta,
                        "precio_regular": max(precio_regular, precio_oferta),
                        "link": link_final,
                        "img": img_url
                    })
                except Exception:
                    continue

        vistos = set()
        productos_unicos = []
        for p in productos:
            if p['link'] not in vistos:
                vistos.add(p['link'])
                productos_unicos.append(p)

        return productos_unicos

    except Exception as e:
        safe_log(f"🚨 Error en motor Falabella: {e}", "error")

    return productos
                                
