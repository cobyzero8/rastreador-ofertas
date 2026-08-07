import requests
from urllib.parse import urlparse, parse_qs
from utils import sanitizar_url, safe_log

def motor_plazavea(url, limite, headers=None):
    productos = []
    url = sanitizar_url(url)
    if not headers:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.plazavea.com.pe/"
        }

    try:
        parsed_url = urlparse(url)
        category_path = parsed_url.path.rstrip('/')
        if category_path and not category_path.startswith('/'):
            category_path = '/' + category_path

        if "busca" in category_path:
            api_url = "https://www.plazavea.com.pe/api/catalog_system/pub/products/search"
        else:
            api_url = f"https://www.plazavea.com.pe/api/catalog_system/pub/products/search{category_path}"

        query_params = parse_qs(parsed_url.query)
        params = {
            "O": "OrderByPriceASC",
            "_from": "0",
            "_to": "49"
        }
        
        for k, v in query_params.items():
            params[k] = v if len(v) > 1 else v[0]

        api_url = sanitizar_url(api_url)
        safe_log(f"📡 [Plaza Vea API] Consultando VTEX con filtros avanzados...", "info")
        resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False)

        if resp.status_code in [200, 206]:
            data = resp.json()
            safe_log(f"🔍 [Plaza Vea API] Catálogo recibido. Procesando {len(data)} productos...", "info")
            vistos_links = set()

            for p in data:
                try:
                    nombre_prod = p.get("productName", "").strip().upper()
                    link_final = p.get("link", "")
                    
                    items = p.get("items", [])
                    if not items: continue
                    
                    first_item = items[0]
                    images = first_item.get("images", [])
                    img_final = images[0].get("imageUrl", "") if images else ""
                    
                    sellers = first_item.get("sellers", [])
                    if not sellers: continue
                        
                    offer = sellers[0].get("commertialOffer", {})
                    stock = offer.get("AvailableQuantity", 0)
                    if stock <= 0: continue  
                        
                    precio_oferta = float(offer.get("Price", 0))
                    precio_regular = float(offer.get("ListPrice", precio_oferta))
                    
                    if precio_oferta <= 0: continue

                    if precio_oferta <= limite:
                        if link_final in vistos_links: continue
                        vistos_links.add(link_final)

                        productos.append({
                            "nombre": f"Plaza Vea - {nombre_prod}",
                            "precio": precio_oferta,
                            "precio_regular": precio_regular,
                            "link": link_final,
                            "img": img_final
                        })
                except Exception: continue
        else:
            safe_log(f"🛑 [Plaza Vea API] Error de conexión con VTEX. Código HTTP: {resp.status_code}", "error")

    except Exception as e:
        safe_log(f"🛑 [Plaza Vea API] Error crítico inesperado: {e}", "error")

    if productos:
        safe_log(f"✅ [Plaza Vea API] ¡Éxito! Se indexaron {len(productos)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [Plaza Vea API] No se encontraron productos bajo el límite de S/. {limite:.2f}", "warning")

    return productos
