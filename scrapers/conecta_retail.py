import time
import re
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from utils import sanitizar_url, safe_float, es_error_de_precio, safe_log, limpiar_precio_pnp
from config import LISTA_USER_AGENTS

def motor_conecta_retail(url, limite=999999.0, headers=None):
    """
    Scraper optimizado para tiendas Conecta Retail (La Curacao y EFE - Magento 2).
    """
    if headers is None:
        user_agent = random.choice(LISTA_USER_AGENTS) if 'LISTA_USER_AGENTS' in globals() else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        headers = {
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }

    productos = []
    url = sanitizar_url(url)
    
    tienda_tag = "EFE" if "efe.com.pe" in url.lower() else "CURACAO"
    base_domain = "https://www.efe.com.pe" if tienda_tag == "EFE" else "https://www.lacuracao.pe"

    try:
        texto_html = ""
        status_code = 0
        for intento in range(1, 3):
            try:
                resp = requests.get(url, headers=headers, timeout=15, verify=False)
                status_code = resp.status_code
                texto_html = resp.text
            except Exception as ex_req:
                safe_log(f"⚠️ Error de conexión con {tienda_tag} (intento {intento}): {ex_req}", "warning")
            
            if status_code == 200 and len(texto_html) > 3000:
                break
            else:
                time.sleep(random.uniform(1.0, 2.5))

        if status_code != 200 or len(texto_html) < 3000:
            safe_log(f"⚠️ [{tienda_tag}] Respuesta HTML inusualmente corta o fallida (HTTP {status_code}, tamaño {len(texto_html)})", "warning")
            return []

        soup = BeautifulSoup(texto_html, 'html.parser')

        # Selectores de tarjetas de producto en Magento 2 (Conecta Retail)
        items = soup.select("li.product-item, div.product-item-info, div.product.item")
        if not items:
            items = soup.find_all(['li', 'div'], class_=re.compile(r'(product-item|product-info|product-card)', re.I))

        for t in items:
            try:
                # 1. Enlace y Título del Producto
                a_link = t.select_one("a.product-item-link") or t.find("a", href=True)
                if not a_link or not a_link.get("href"):
                    continue

                link_raw = a_link["href"].strip()
                link_final = urljoin(base_domain, link_raw)

                nombre_txt = a_link.get_text(strip=True).upper()
                if not nombre_txt or len(nombre_txt) < 5:
                    tit_el = t.select_one(".product-item-name, .product.name, strong.name")
                    if tit_el:
                        nombre_txt = tit_el.get_text(strip=True).upper()

                if not nombre_txt or len(nombre_txt) < 5:
                    continue

                # 2. Extracción de Precios (Atributos data-price-amount y CSS Magento)
                p_oferta = 0.0
                p_regular = 0.0

                price_amounts = t.select("[data-price-amount]")
                valid_amounts = []
                for pa in price_amounts:
                    val_attr = safe_float(pa.get("data-price-amount"))
                    if val_attr > 0:
                        valid_amounts.append(val_attr)

                el_special = t.select_one(".special-price .price, .price-final_price .price, [data-price-type='finalPrice'] .price")
                el_old = t.select_one(".old-price .price, [data-price-type='oldPrice'] .price")
                el_regular = t.select_one(".price-container .price, .normal-price .price")

                if el_special:
                    p_oferta = limpiar_precio_pnp(el_special.get_text())
                if el_old:
                    p_regular = limpiar_precio_pnp(el_old.get_text())

                if p_oferta == 0.0 and el_regular:
                    p_oferta = limpiar_precio_pnp(el_regular.get_text())

                if p_oferta == 0.0 and valid_amounts:
                    p_oferta = min(valid_amounts)
                    p_regular = max(valid_amounts)

                if p_regular == 0.0:
                    p_regular = p_oferta

                # Descartar precios incoherentes o superiores al tope
                if p_oferta <= 0 or es_error_de_precio(p_oferta) or p_oferta > limite:
                    continue

                # 3. Imagen del Producto
                img_el = t.select_one("img.product-image-photo") or t.find("img")
                img_url = ""
                if img_el:
                    for attr in ["data-src", "src", "data-amsrc", "srcset", "data-original"]:
                        val = img_el.get(attr)
                        if val and "data:image" not in str(val) and len(str(val)) > 10:
                            img_url = str(val).split(" ")[0].strip()
                            break

                if str(img_url).startswith("//"):
                    img_url = "https:" + str(img_url)

                productos.append({
                    "nombre": f"{tienda_tag} - {nombre_txt}",
                    "precio": p_oferta,
                    "precio_regular": max(p_regular, p_oferta),
                    "link": link_final,
                    "img": img_url
                })

            except Exception:
                continue

        # Filtrar duplicados por URL
        vistos = set()
        productos_unicos = []
        for p in productos:
            if p["link"] not in vistos:
                vistos.add(p["link"])
                productos_unicos.append(p)

        safe_log(f"✅ [{tienda_tag}] Extraídos {len(productos_unicos)} productos válidos.", "success")
        return productos_unicos

    except Exception as e:
        safe_log(f"🚨 Error en motor Conecta Retail ({tienda_tag}): {e}", "error")

    return []
