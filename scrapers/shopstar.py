import time
import json
import random
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from utils import sanitizar_url, safe_float, es_error_de_precio, safe_log
from config import LISTA_USER_AGENTS

def motor_shopstar(url, limite=999999.0, headers=None):
    """
    Scraper optimizado para Shopstar Perú (VTEX IO).
    Soporta tanto páginas de catálogo/categoría como enlaces directos de producto (PDP /p).
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
    es_pdp = '/p' in url.split('?')[0].lower()

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

        # ==========================================
        # CASO A: FICHA DIRECTA DE PRODUCTO (PDP /p)
        # ==========================================
        if es_pdp:
            nombre = ""
            precio_oferta = 0.0
            precio_regular = 0.0
            img_url = ""

            # 1. Metadatos OpenGraph / Titular H1 (Alta precisión en VTEX)
            meta_og_title = soup.find("meta", property="og:title") or soup.find("meta", attrs={"name": "title"})
            meta_og_img = soup.find("meta", property="og:image")
            
            if meta_og_title and meta_og_title.get("content"):
                nombre = meta_og_title["content"].strip().upper()
            
            if meta_og_img and meta_og_img.get("content"):
                img_url = meta_og_img["content"].strip()

            if not nombre:
                h1_el = soup.find("h1") or soup.select_one("span[class*='productBrand']")
                if h1_el:
                    nombre = h1_el.text.strip().upper()

            # 2. Extracción de Precios desde JSON-LD de Producto
            scripts_json = soup.find_all("script", type="application/ld+json")
            for script in scripts_json:
                if not script.string: continue
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get("@type") == "Product":
                        if not nombre:
                            nombre = str(data.get("name") or "").strip().upper()
                        
                        offers = data.get("offers", {})
                        if isinstance(offers, list) and offers:
                            offers = offers[0]
                        
                        if isinstance(offers, dict):
                            precio_oferta = safe_float(offers.get("price") or offers.get("lowPrice"))
                            precio_regular = safe_float(offers.get("highPrice") or precio_oferta)

                        img_raw = data.get("image")
                        if isinstance(img_raw, list) and img_raw: img_raw = img_raw[0]
                        if isinstance(img_raw, str) and not img_url: img_url = img_raw
                except Exception:
                    pass

            # 3. Fallback de Precios en HTML si falla el JSON
            if precio_oferta <= 0:
                price_spans = soup.select("span[class*='currencyInteger'], span[class*='sellingPrice'], span[class*='price']")
                valores = [safe_float(sp.text) for sp in price_spans if safe_float(sp.text) > 10.0]
                if valores:
                    precio_oferta = min(valores)
                    precio_regular = max(valores)

            if precio_regular <= 0:
                precio_regular = precio_oferta

            if img_url.startswith("//"):
                img_url = "https:" + img_url

            if nombre and len(nombre) >= 5 and precio_oferta >= 10.0 and precio_oferta <= limite:
                return [{
                    "nombre": f"SHOPSTAR - {nombre}",
                    "precio": precio_oferta,
                    "precio_regular": max(precio_regular, precio_oferta),
                    "link": url,
                    "img": img_url
                }]

        # ==========================================
        # CASO B: PÁGINAS DE LISTADO / CATEGORÍA
        # ==========================================
        scripts_json = soup.find_all("script", type=re.compile(r"json", re.I))
        for script in scripts_json:
            if not script.string: continue
            content = script.string.strip()

            # Descartar schemas de navegación (Evita capturar "FILTROS", "INICIO", etc.)
            if '"@type":"BreadcrumbList"' in content or '"@type": "BreadcrumbList"' in content:
                continue

            if '"@type":"Product"' in content or '"@type":"ItemList"' in content:
                try:
                    data = json.loads(content)
                    items_raw = []

                    if isinstance(data, dict):
                        if data.get("@type") == "ItemList":
                            items_raw = data.get("itemListElement", [])
                        elif data.get("@type") == "Product":
                            items_raw = [data]
                    elif isinstance(data, list):
                        items_raw = data

                    for item_wrap in items_raw:
                        item = item_wrap.get("item", item_wrap) if isinstance(item_wrap, dict) else {}
                        if not isinstance(item, dict) or item.get("@type") == "BreadcrumbList":
                            continue

                        link_rel = item.get("url") or item.get("@id") or ""
                        if not link_rel or ('/p' not in link_rel and '/product/' not in link_rel):
                            continue

                        link_final = urljoin("https://www.shopstar.pe", link_rel)
                        nombre_txt = str(item.get("name") or "").strip().upper()
                        
                        if len(nombre_txt) < 5 or nombre_txt in ["FILTROS", "INICIO", "COCINA", "HOME"]:
                            continue

                        offers = item.get("offers", {})
                        if isinstance(offers, list) and offers: offers = offers[0]

                        precio_oferta = safe_float(offers.get("price") or offers.get("lowPrice"))
                        precio_regular = safe_float(offers.get("highPrice") or precio_oferta)
                        if precio_regular <= 0: precio_regular = precio_oferta

                        if precio_oferta < 10.0 or es_error_de_precio(precio_oferta, precio_regular, precio_regular) or precio_oferta > limite:
                            continue

                        img_raw = item.get("image") or ""
                        if isinstance(img_raw, list) and img_raw: img_raw = img_raw[0]
                        elif isinstance(img_raw, dict): img_raw = img_raw.get("url") or ""

                        img_url = str(img_raw).strip()
                        if img_url.startswith("//"): img_url = "https:" + img_url

                        productos.append({
                            "nombre": f"SHOPSTAR - {nombre_txt}",
                            "precio": precio_oferta,
                            "precio_regular": max(precio_regular, precio_oferta),
                            "link": link_final,
                            "img": img_url
                        })
                except Exception:
                    pass

        # Fallback HTML para Tarjetas en Catálogo
        if not productos:
            items = soup.find_all(["div", "article"], class_=re.compile(r"(vtex-product-summary|productSummary|galleryItem)", re.I))
            for t in items:
                try:
                    a_el = t.find("a", href=True)
                    if not a_el or not a_el["href"] or '/p' not in a_el["href"]:
                        continue

                    link_final = urljoin("https://www.shopstar.pe", a_el["href"])

                    tit_el = t.find(["span", "h2", "h3", "p"], class_=re.compile(r"(productBrand|productName|brandName|title)", re.I))
                    nombre_txt = tit_el.text.strip().upper() if tit_el else ""
                    if len(nombre_txt) < 5 or nombre_txt in ["FILTROS", "INICIO", "COCINA"]:
                        continue

                    precios_texto = t.find_all(text=re.compile(r"S/\.?\s*\d+", re.I))
                    valores_encontrados = [safe_float(re.sub(r"[^\d.]", "", pt.replace(",", "."))) for pt in precios_texto]
                    valores_encontrados = [v for v in valores_encontrados if v > 10.0]

                    if not valores_encontrados: continue

                    precio_oferta = min(valores_encontrados)
                    precio_regular = max(valores_encontrados)

                    if precio_oferta < 10.0 or es_error_de_precio(precio_oferta, precio_regular, precio_regular) or precio_oferta > limite:
                        continue

                    img_el = t.find("img")
                    img_url = ""
                    if img_el:
                        for attr in ["src", "data-src", "srcset"]:
                            val = img_el.get(attr)
                            if val and "data:image" not in str(val):
                                img_url = str(val).split(" ")[0].strip()
                                break

                    if img_url.startswith("//"): img_url = "https:" + img_url

                    productos.append({
                        "nombre": f"SHOPSTAR - {nombre_txt}",
                        "precio": precio_oferta,
                        "precio_regular": max(precio_regular, precio_oferta),
                        "link": link_final,
                        "img": img_url
                    })
                except Exception:
                    continue

        # Deduplicar resultados por URL
        vistos = set()
        productos_unicos = []
        for p in productos:
            if p["link"] not in vistos:
                vistos.add(p["link"])
                productos_unicos.append(p)

        return productos_unicos

    except Exception as e:
        safe_log(f"🚨 Error en motor Shopstar: {e}", "error")

    return productos
