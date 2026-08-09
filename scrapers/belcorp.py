import random
import requests
from urllib.parse import urlparse
from utils import safe_log, safe_float
from config import LISTA_USER_AGENTS

def motor_belcorp(url, limite=999999.0, headers=None):
    """
    Extrae productos directamente desde la API VTEX de Belcorp (Cyzone, L'Bel, Esika).
    """
    productos = []
    if not url:
        return productos

    # 1. Si no vienen headers desde el enrutador, los generamos automáticamente
    if headers is None:
        headers = {
            "User-Agent": random.choice(LISTA_USER_AGENTS),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-PE,es;q=0.9"
        }

    # 2. Identificar la marca a través de la URL (cyzone, lbel, esika)
    dominio = urlparse(url).netloc.lower()
    marca = "cyzone" if "cyzone" in dominio else "lbel" if "lbel" in dominio else "esika"

    # 3. Detectar la categoría o palabra clave desde la URL (ej: /perfumes/c -> "perfume")
    path_parts = [p for p in urlparse(url).path.split('/') if p and p != 'c']
    termino_busqueda = path_parts[0] if path_parts else "perfume"

    api_url = f"https://{marca}.tiendabelcorp.com.pe/api/catalog_system/pub/products/search"
    params = {
        "ft": termino_busqueda,
        "_from": 0,
        "_to": 40,
        "O": "OrderByPriceASC"
    }

    try:
        resp = requests.get(api_url, headers=headers, params=params, timeout=15)
        if resp.status_code != 200:
            safe_log(f"⚠️ Belcorp ({marca}) API devolvió HTTP {resp.status_code}", "warning")
            return productos

        data = resp.json()
        if not isinstance(data, list):
            return productos

        for item in data:
            try:
                items_list = item.get("items", [])
                if not items_list:
                    continue
                
                sellers = items_list[0].get("sellers", [])
                if not sellers:
                    continue

                offer = sellers[0].get("commertialOffer", {})
                precio = safe_float(offer.get("Price"))
                precio_regular = safe_float(offer.get("ListPrice", precio))

                if 0 < precio <= limite:
                    nombre_prod = str(item.get("productName", "")).strip().upper()
                    link_prod = str(item.get("link", url))
                    
                    images = items_list[0].get("images", [])
                    img_url = str(images[0].get("imageUrl", "")) if images else ""

                    productos.append({
                        "nombre": f"{marca.upper()} - {nombre_prod}",
                        "precio": precio,
                        "precio_regular": max(precio_regular, precio),
                        "link": link_prod,
                        "img": img_url
                    })
            except Exception:
                continue

        safe_log(f"✅ [Belcorp - {marca.upper()}] Capturados {len(productos)} productos vía API VTEX.", "success")

    except Exception as e:
        safe_log(f"🚨 Error en motor Belcorp API ({marca}): {e}", "error")

    return productos
