import time
import json
import random
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

from utils import sanitizar_url, safe_float, es_error_de_precio, safe_log
from config import LISTA_USER_AGENTS

# Palabras reservadas a descartar como títulos válidos
NOMBRES_INVALIDOS = {
    "FILTROS", "FILTRO", "INICIO", "HOME", "SHOPSTAR", "COCINA", 
    "ELECTROHOGAR", "CAMPANAS EXTRACTORAS", "CAMPANA EXTRACTORA", 
    "VER TODO", "CATALOGO", "ACCESORIOS", "PRODUCTOS"
}

def es_nombre_valido(nombre):
    if not nombre or len(nombre) < 5:
        return False
    n_clean = nombre.strip().upper()
    if n_clean in NOMBRES_INVALIDOS:
        return False
    palabras = n_clean.split()
    if len(palabras) == 1 and palabras[0] in NOMBRES_INVALIDOS:
        return False
    return True

def motor_shopstar(url, limite=999999.0, headers=None):
    """
    Scraper optimizado y robusto para Shopstar Perú (VTEX IO).
    Soporta catálogo por VTEX Search API, window.__STATE__, JSON-LD y fallback HTML.
    """
    if headers is None:
        user_agent = random.choice(LISTA_USER_AGENTS) if 'LISTA_USER_AGENTS' in globals() else "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        }

    url = sanitizar_url(url)
    parsed_url = urlparse(url)
    es_pdp = '/p' in parsed_url.path.lower()
    productos = []

    # =========================================================================
    # ESTRATEGIA 1: API OFICIAL VTEX CATALOG SEARCH (Para Categorías / Busquedas)
    # =========================================================================
    if not es_pdp:
        try:
            ruta_categoria = parsed_url.path.rstrip('/')
            api_url = f"https://www.shopstar.pe/api/catalog_system/pub/products/search{ruta_categoria}"
            
            resp_api = requests.get(api_url, headers=headers, timeout=10, verify=False)
            if resp_api.status_code == 200:
                data_api = resp_api.json()
                if isinstance(data_api, list) and data_api:
                    for item in data_api:
                        try:
                            p_name = str(item.get("productName") or "").strip().upper()
                            brand = str(item.get("brand") or "").strip().upper()

                            if isinstance(item.get("brand"), dict):
                                brand = str(item.get("brand", {}).get("name") or "").strip().upper()

                            full_title = f"{brand} {p_name}" if (brand and brand not in p_name) else p_name
                            full_title = re.sub(r"^SHOPSTAR\s*-\s*", "", full_title, flags=re.I).strip()

                            if not es_nombre_valido(full_title):
                                continue

                            link_rel = item.get("link") or item.get("linkText") or ""
                            if link_rel:
                                link_final = urljoin("https://www.shopstar.pe", link_rel)
                                if '/p' not in link_final.lower():
                                    link_final += '/p'
                            else:
                                continue

                            # Extraer Imagen
                            img_url = ""
                            items_sku = item.get("items") or []
                            for sku in items_sku:
                                images = sku.get("images") or []
                                if images and isinstance(images, list):
                                    img_url = images[0].get("imageUrl") or ""
                                    if img_url: break

                            if img_url.startswith("//"): img_url = "https:" + img_url

                            # Extraer Precios
                            p_off = 0.0
                            p_reg = 0.0
                            for sku in items_sku:
                                sellers = sku.get("sellers") or []
                                for seller in sellers:
                                    comm = seller.get("commertialOffer") or {}
                                    price = safe_float(comm.get("Price") or comm.get("spotPrice"))
                                    list_price = safe_float(comm.get("ListPrice") or price)
                                    
                                    if price > 5.0:
                                        if p_off == 0.0 or price < p_off: p_off = price
                                        if list_price > p_reg: p_reg = list_price

                            if p_off <= 0 or es_error_de_precio(p_off, p_reg, p_reg) or p_off > limite:
                                continue

                            productos.append({
                                "nombre": f"SHOPSTAR - {full_title}",
                                "precio": p_off,
                                "precio_regular": max(p_reg, p_off),
                                "link": link_final,
                                "img": img_url
                            })
                        except Exception:
                            continue

                    if productos:
                        return productos
        except Exception:
            pass

    # =========================================================================
    # OBTENER HTML DE LA PÁGINA (Para PDP o si la API no retornó)
    # =========================================================================
    try:
        texto_html = ""
        status_code = 0
        for intento in range(1, 3):
            try:
                resp = requests.get(url, headers=headers, timeout=12, verify=False)
                texto_html = resp.text
                status_code = resp.status_code
            except Exception:
                pass

            if status_code == 200 and len(texto_html) > 3000:
                break
            time.sleep(random.uniform(0.8, 1.5))

        if status_code != 200 or len(texto_html) < 3000:
            return []

        soup = BeautifulSoup(texto_html, 'html.parser')

        # =========================================================================
        # ESTRATEGIA 2: EXTRAER DESDE window.__STATE__ (VTEX IO React Context)
        # =========================================================================
        try:
            match_state = re.search(r'window\.__STATE__\s*=\s*(\{.*?\});?\s*(?:</script>|\n)', texto_html, re.DOTALL)
            if match_state:
                state_data = json.loads(match_state.group(1))
                for key, val in state_data.items():
                    if isinstance(val, dict) and 'productName' in val:
                        p_name = str(val.get('productName') or '').strip().upper()
                        brand = str(val.get('brand') or '').strip().upper()
                        link_text = str(val.get('linkText') or val.get('link') or '').strip()

                        full_title = f"{brand} {p_name}" if (brand and brand not in p_name) else p_name
                        full_title = re.sub(r"^SHOPSTAR\s*-\s*", "", full_title, flags=re.I).strip()

                        if not es_nombre_valido(full_title):
                            continue

                        if link_text:
                            if not link_text.startswith('http'):
                                link_text = '/' + link_text.lstrip('/')
                                if '/p' not in link_text.lower():
                                    link_text += '/p'
                                link_final = urljoin("https://www.shopstar.pe", link_text)
                            else:
                                link_final = link_text
                        else:
                            link_final = url

                        p_off = 0.0
                        p_reg = 0.0
                        img_url = ""

                        items = val.get('items') or []
                        for item_ref in items:
                            item_obj = item_ref
                            if isinstance(item_ref, dict) and 'id' in item_ref:
                                item_key = f"Item:{item_ref['id']}"
                                item_obj = state_data.get(item_key, item_ref)

                            if isinstance(item_obj, dict):
                                images = item_obj.get('images') or []
                                if images and isinstance(images, list) and not img_url:
                                    img_first = images[0]
                                    if isinstance(img_first, dict):
                                        img_url = img_first.get('imageUrl') or ""

                                sellers = item_obj.get('sellers') or []
                                for seller in sellers:
                                    if isinstance(seller, dict):
                                        comm = seller.get('commertialOffer') or {}
                                        price = safe_float(comm.get('Price') or comm.get('spotPrice'))
                                        l_price = safe_float(comm.get('ListPrice') or price)
                                        if price > 5.0:
                                            if p_off == 0.0 or price < p_off: p_off = price
                                            if l_price > p_reg: p_reg = l_price

                        if p_off > 0 and p_off <= limite and not es_error_de_precio(p_off, p_reg, p_reg):
                            if p_reg <= 0: p_reg = p_off
                            if img_url.startswith("//"): img_url = "https:" + img_url

                            productos.append({
                                "nombre": f"SHOPSTAR - {full_title}",
                                "precio": p_off,
                                "precio_regular": max(p_reg, p_off),
                                "link": link_final,
                                "img": img_url
                            })
        except Exception:
            pass

        if productos:
            vistos = set()
            unicos = []
            for p in productos:
                if p["link"] not in vistos:
                    vistos.add(p["link"])
                    unicos.append(p)
            return unicos

        # =========================================================================
        # ESTRATEGIA 3: JSON-LD OFICIAL (Para PDP / Fichas Individuales)
        # =========================================================================
        scripts_json = soup.find_all("script", type="application/ld+json")
        for script in scripts_json:
            if not script.string: continue
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get("@type") == "Product":
                    p_name = str(data.get("name") or "").strip().upper()
                    brand_data = data.get("brand") or {}
                    brand_name = str(brand_data.get("name") if isinstance(brand_data, dict) else brand_data).strip().upper()

                    full_title = f"{brand_name} {p_name}" if (brand_name and brand_name not in p_name) else p_name
                    full_title = re.sub(r"^SHOPSTAR\s*-\s*", "", full_title, flags=re.I).strip()

                    if es_nombre_valido(full_title):
                        offers = data.get("offers", {})
                        if isinstance(offers, list) and offers: offers = offers[0]

                        if isinstance(offers, dict):
                            p_off = safe_float(offers.get("price") or offers.get("lowPrice"))
                            p_reg = safe_float(offers.get("highPrice") or p_off)

                            img_raw = data.get("image")
                            if isinstance(img_raw, list) and img_raw: img_raw = img_raw[0]
                            img_url = str(img_raw).strip() if isinstance(img_raw, str) else ""
                            if img_url.startswith("//"): img_url = "https:" + img_url

                            if p_off >= 10.0 and p_off <= limite and not es_error_de_precio(p_off, p_reg, p_reg):
                                return [{
                                    "nombre": f"SHOPSTAR - {full_title}",
                                    "precio": p_off,
                                    "precio_regular": max(p_reg, p_off),
                                    "link": url,
                                    "img": img_url
                                }]
            except Exception:
                pass

    except Exception as e:
        safe_log(f"🚨 Error en motor Shopstar: {e}", "error")

    return productos
                                    
