import re
import json
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, unquote, urljoin
from config import LISTA_USER_AGENTS
from utils import sanitizar_url, safe_log

def motor_estilos(url, limite):
    productos_map = {}
    url = sanitizar_url(url)
    headers = {
        "User-Agent": random.choice(LISTA_USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9",
        "Referer": "https://www.estilos.com.pe/"
    }

    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        raw_path = unquote(parsed_url.path.rstrip('/'))
        
        segmentos = [s for s in raw_path.split('/') if s and not re.match(r'^\d+[\-_.]\d+$', s)]
        path_limpio = '/' + '/'.join(segmentos) if segmentos else "/poleras-hombre"
        path_base = '/' + '/'.join(segmentos[-2:]) if len(segmentos) >= 2 else path_limpio

        urls_a_probar = []

        q_term = query_params.get('_q', query_params.get('ft', [None]))[0]
        if q_term:
            urls_a_probar.append((
                "https://www.estilos.com.pe/api/catalog_system/pub/products/search",
                {"ft": q_term, "O": "OrderByPriceASC", "_from": "0", "_to": "49"}
            ))

        urls_a_probar.append((
            f"https://www.estilos.com.pe/api/catalog_system/pub/products/search{path_limpio}",
            {"O": "OrderByPriceASC", "_from": "0", "_to": "49"}
        ))
        
        if path_base != path_limpio:
            urls_a_probar.append((
                f"https://www.estilos.com.pe/api/catalog_system/pub/products/search{path_base}",
                {"O": "OrderByPriceASC", "_from": "0", "_to": "49"}
            ))

        safe_log(f"📡 [Estilos API] Consultando catálogo VTEX de Estilos...", "info")

        for api_endpoint, params in urls_a_probar:
            try:
                api_endpoint = sanitizar_url(api_endpoint)
                resp = requests.get(api_endpoint, headers=headers, params=params, timeout=12, verify=False)
                if resp.status_code in [200, 206]:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        safe_log(f"🔍 [Estilos API] ¡Éxito! Se procesaron {len(data)} modelos desde VTEX.", "info")
                        for p in data:
                            try:
                                nombre_prod = p.get("productName", "").strip().upper()
                                link_rel = p.get("link", "")
                                link_final = urljoin("https://www.estilos.com.pe", link_rel) if link_rel else url
                                
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
                                        "nombre": f"ESTILOS - {nombre_prod}",
                                        "precio": p_o,
                                        "precio_regular": max(p_r, p_o),
                                        "link": link_final,
                                        "img": img_final
                                    }
                            except Exception: continue
                        
                        if len(productos_map) > 0: break
            except Exception: continue

    except Exception as e:
        safe_log(f"⚠️ [Estilos API] Error de consulta: {e}", "warning")

    if not productos_map:
        try:
            safe_log("🛡️ [Estilos HTML] Escaneando estructura de respaldo...", "info")
            html_headers = headers.copy()
            html_headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            resp = requests.get(url, headers=html_headers, timeout=15, verify=False)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for script in soup.find_all('script', type='application/ld+json'):
                    try:
                        if not script.string: continue
                        json_data = json.loads(script.string)
                        items = []
                        if isinstance(json_data, dict) and json_data.get('@type') == 'ItemList':
                            items = [x.get('item', {}) for x in json_data.get('itemListElement', [])]
                        elif isinstance(json_data, list):
                            items = json_data
                            
                        for item in items:
                            if not isinstance(item, dict): continue
                            nombre = str(item.get('name', '')).strip().upper()
                            link_f = urljoin("https://www.estilos.com.pe", item.get('url', ''))
                            offers = item.get('offers', {})
                            p_o = 0.0
                            if isinstance(offers, dict): p_o = float(offers.get('price', 0.0))
                            elif isinstance(offers, list) and offers: p_o = float(offers[0].get('price', 0.0))
                            img_f = item.get('image', '')
                            if isinstance(img_f, list) and img_f: img_f = img_f[0]
                            if str(img_f).startswith('//'): img_f = 'https:' + str(img_f)
                            
                            if 0 < p_o <= limite and nombre and link_f:
                                productos_map[link_f] = {
                                    "nombre": f"ESTILOS - {nombre}",
                                    "precio": p_o,
                                    "precio_regular": p_o,
                                    "link": link_f,
                                    "img": img_f
                                }
                    except Exception: continue
        except Exception as he:
            safe_log(f"🛑 [Estilos HTML] Error en contingencia HTML: {he}", "error")

    productos_list = list(productos_map.values())
    if productos_list:
        safe_log(f"✅ [Estilos] ¡Éxito! Se indexaron {len(productos_list)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [Estilos] No se encontraron ofertas por debajo de S/. {limite:.2f}", "warning")

    return productos_list
