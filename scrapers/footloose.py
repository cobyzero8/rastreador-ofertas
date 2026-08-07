import re
import random
import requests
from urllib.parse import urlparse, parse_qs, urljoin
from config import LISTA_USER_AGENTS
from utils import sanitizar_url, safe_log

def motor_footloose(url, limite):
    productos_map = {}
    url = sanitizar_url(url)
    headers = {
        "User-Agent": random.choice(LISTA_USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9",
        "Referer": "https://www.footloose.pe/"
    }

    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        raw_path = parsed_url.path.rstrip('/')
        if 'query' in query_params:
            q_val = query_params['query'][0]
            if q_val.startswith('/'):
                raw_path = q_val.rstrip('/')

        segmentos = [s for s in raw_path.split('/') if s and not re.match(r'^\d+[\-_.]\d+$', s)]
        path_limpio = '/' + '/'.join(segmentos) if segmentos else "/calzados"
        path_base = '/' + '/'.join(segmentos[:2]) if len(segmentos) >= 2 else path_limpio

        urls_a_probar = []

        if "map" in query_params:
            maps = query_params["map"][0].split(',')
            maps_validos = [m for m in maps if m in ['c', 'category-1', 'category-2', 'category-3', 'brand', 'b']]
            if maps_validos and len(maps_validos) == len(segmentos):
                urls_a_probar.append((f"https://www.footloose.pe/api/catalog_system/pub/products/search{path_limpio}", {"O": "OrderByPriceASC", "_from": "0", "_to": "49", "map": ",".join(maps_validos)}))

        urls_a_probar.append((f"https://www.footloose.pe/api/catalog_system/pub/products/search{path_limpio}", {"O": "OrderByPriceASC", "_from": "0", "_to": "49"}))
        
        if path_base != path_limpio:
            urls_a_probar.append((f"https://www.footloose.pe/api/catalog_system/pub/products/search{path_base}", {"O": "OrderByPriceASC", "_from": "0", "_to": "49"}))

        safe_log(f"📡 [Footloose API] Iniciando escaneo multinivel sobre `{path_limpio}`...", "info")

        for api_endpoint, params in urls_a_probar:
            try:
                api_endpoint = sanitizar_url(api_endpoint)
                resp = requests.get(api_endpoint, headers=headers, params=params, timeout=12, verify=False)
                if resp.status_code in [200, 206]:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        safe_log(f"🔍 [Footloose API] ¡Respuesta recibida! {len(data)} ítems evaluados.", "info")
                        for p in data:
                            try:
                                nombre_prod = p.get("productName", "").strip().upper()
                                link_rel = p.get("link", "")
                                link_final = urljoin("https://www.footloose.pe", link_rel) if link_rel else url
                                
                                items = p.get("items", [])
                                if not items: continue
                                
                                first_item = items[0]
                                images = first_item.get("images", [])
                                img_final = images[0].get("imageUrl", "") if images else ""
                                if img_final.startswith('//'): img_final = 'https:' + img_final
                                
                                sellers = first_item.get("sellers", [])
                                if not sellers: continue
                                    
                                offer = sellers[0].get("commertialOffer", {})
                                p_o = float(offer.get("Price", 0.0))
                                p_r = float(offer.get("ListPrice", p_o))
                                
                                if 0 < p_o <= limite:
                                    productos_map[link_final] = {
                                        "nombre": f"FOOTLOOSE - {nombre_prod}",
                                        "precio": p_o,
                                        "precio_regular": max(p_r, p_o),
                                        "link": link_final,
                                        "img": img_final
                                    }
                            except Exception: continue
                        
                        if len(productos_map) > 0: break
            except Exception: continue

    except Exception as e:
        safe_log(f"🛑 [Footloose API] Error de ejecución: {e}", "error")

    productos_list = list(productos_map.values())
    if productos_list:
        safe_log(f"✅ [Footloose] ¡Éxito! Se indexaron {len(productos_list)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [Footloose] No se encontraron ofertas por debajo de S/. {limite:.2f}", "warning")

    return productos_list
