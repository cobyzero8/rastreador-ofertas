import requests
from urllib.parse import urlparse
from utils import sanitizar_url

def motor_belcorp(url, limite, headers):
    productos = []
    url = sanitizar_url(url)
    dominio = urlparse(url).netloc.lower()
    marca = "cyzone" if "cyzone" in dominio else "lbel" if "lbel" in dominio else "esika"
    try:
        resp = requests.get(
            f"https://{marca}.tiendabelcorp.com.pe/api/catalog_system/pub/products/search",
            headers=headers,
            params={"ft": "perfume", "_from": 0, "_to": 20, "O": "OrderByPriceASC"},
            timeout=15,
            verify=False
        )
        for item in resp.json():
            offer = item["items"][0]["sellers"][0]["commertialOffer"]
            if 0 < float(offer["Price"]) <= limite:
                productos.append({
                    "nombre": f"{marca.upper()} - {item['productName'].upper()}",
                    "precio": float(offer["Price"]),
                    "precio_regular": float(offer.get("ListPrice", offer["Price"])),
                    "link": item["link"],
                    "img": item["items"][0]["images"][0]["imageUrl"]
                })
    except Exception: pass
    return productos
