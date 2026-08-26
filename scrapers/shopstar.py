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
    Scraper optimizado para Shopstar Perú (Plataforma VTEX).
    Extrae productos tanto desde estado JSON interno (VTEX __STATE__) como por Fallback HTML.
    """
    if headers is None:
        user_agent = (
            random.choice(LISTA_USER_AGENTS)
            if "LISTA_USER_AGENTS" in globals()
            else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
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

        soup = BeautifulSoup(texto_html, "html.parser")

        # --- CAPA 1: EXTRACCIÓN VÍA ESTADO VTEX / JSON-LD ---
        scripts_json = soup.find_all("script", type=re.compile(r"json", re.I))
        for script in scripts_json:
            if not script.string:
                continue

            content = script.string.strip()

            # Búsqueda de JSON-LD con esquema de producto o lista
            if '"@type":"Product"' in content or '"@type": "Product"' in content or '"@type":"ItemList"' in content:
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
                        if not isinstance(item, dict):
                            continue

                        link_rel = item.get("url") or item.get("@id") or ""
                        if not link_rel:
                            continue

                        link_final = urljoin("https://www.shopstar.pe", link_rel)
                        nombre_txt = str(item.get("name") or "").strip().upper()
                        if len(nombre_txt) < 5:
                            continue

                        # Extracción de precios
                        offers = item.get("offers", {})
                        if isinstance(offers, list) and offers:
                            offers = offers[0]

                        precio_oferta = safe_float(offers.get("price") or offers.get("lowPrice"))
                        precio_regular = safe_float(offers.get("highPrice") or precio_oferta)

                        if precio_regular <= 0:
                            precio_regular = precio_oferta

                        if (
                            precio_oferta < 10.0
                            or es_error_de_precio(precio_oferta, precio_regular, precio_regular)
                            or precio_oferta > limite
                        ):
                            continue

                        # Extracción de imagen
                        img_raw = item.get("image") or ""
                        if isinstance(img_raw, list) and img_raw:
                            img_raw = img_raw[0]
                        elif isinstance(img_raw, dict):
                            img_raw = img_raw.get("url") or img_raw.get("contentUrl") or ""

                        img_url = str(img_raw).strip()
                        if img_url.startswith("//"):
                            img_url = "https:" + img_url

                        productos.append({
                            "nombre": f"SHOPSTAR - {nombre_txt}",
                            "precio": precio_oferta,
                            "precio_regular": max(precio_regular, precio_oferta),
                            "link": link_final,
                            "img": img_url,
                        })
                except Exception:
                    pass

        # --- CAPA 2: FALLBACK HTML (Estructura VTEX / Shopstar Cards) ---
        if not productos:
            items = soup.find_all(
                ["div", "article", "section"],
                class_=re.compile(r"(vtex-product-summary|productSummary|galleryItem|podCard)", re.I),
            )

            for t in items:
                try:
                    a_el = t.find("a", href=True)
                    if not a_el or not a_el["href"]:
                        continue

                    link_final = urljoin("https://www.shopstar.pe", a_el["href"])

                    # Nombre del producto
                    tit_el = t.find(
                        ["span", "h2", "h3", "p"],
                        class_=re.compile(r"(productBrand|productName|brandName|title)", re.I),
                    )
                    nombre_txt = tit_el.text.strip().upper() if tit_el else ""
                    if len(nombre_txt) < 5:
                        continue

                    # Búsqueda de precios en etiquetas de texto/clases VTEX
                    precios_texto = t.find_all(text=re.compile(r"S/\.?\s*\d+", re.I))
                    valores_encontrados = []
                    for pt in precios_texto:
                        val = safe_float(re.sub(r"[^\d.]", "", pt.replace(",", ".")))
                        if val > 0:
                            valores_encontrados.append(val)

                    if not valores_encontrados:
                        continue

                    precio_oferta = min(valores_encontrados)
                    precio_regular = max(valores_encontrados)

                    if (
                        precio_oferta < 10.0
                        or es_error_de_precio(precio_oferta, precio_regular, precio_regular)
                        or precio_oferta > limite
                    ):
                        continue

                    # Imagen del producto
                    img_el = t.find("img")
                    img_url = ""
                    if img_el:
                        for attr in ["src", "data-src", "srcset"]:
                            val = img_el.get(attr)
                            if val and "data:image" not in str(val):
                                img_url = str(val).split(" ")[0].strip()
                                break

                    if img_url.startswith("//"):
                        img_url = "https:" + img_url

                    productos.append({
                        "nombre": f"SHOPSTAR - {nombre_txt}",
                        "precio": precio_oferta,
                        "precio_regular": max(precio_regular, precio_oferta),
                        "link": link_final,
                        "img": img_url,
                    })
                except Exception:
                    continue

        # Deduplicar por URL
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
