import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from utils import sanitizar_url, safe_log

def motor_oechsle(url, limite):
    productos = []
    url = sanitizar_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    try:
        safe_log("📡 [Oechsle] Analizando estructura del radar...", "info")
        
        parsed_url = urlparse(url)
        raw_query = parsed_url.query
        
        if 'query=' in raw_query:
            raw_query = raw_query.replace('query=', 'ft=')
        
        has_category_filter = 'fq=C:' in raw_query or 'fq=C%3A' in raw_query
        base_api = "https://www.oechsle.pe/api/catalog_system/pub/products/search"
        
        if has_category_filter:
            api_url = f"{base_api}?{raw_query}"
        else:
            category_path = parsed_url.path.rstrip('/')
            if category_path and not category_path.startswith('/'):
                category_path = '/' + category_path
            api_url = f"{base_api}{category_path}?{raw_query}"
            
        if '_from=' not in api_url:
            api_url += "&_from=0&_to=49"
            
        api_url = sanitizar_url(api_url)
        
        safe_log(f"📡 [Oechsle] Conectando con la base de datos oficial...", "info")
        resp = requests.get(api_url, headers=headers, timeout=15, verify=False)
        
        if resp.status_code in [200, 206]:
            data = resp.json()
            safe_log(f"🔍 [Oechsle] Base de datos leída con éxito. Se procesaron {len(data)} productos.", "info")
            
            for item in data:
                try:
                    nombre = item.get('productName', '').upper()
                    link_final = item.get('link', url)
                    
                    items_list = item.get('items', [])
                    if not items_list: continue
                    first_item = items_list[0]
                    
                    sellers = first_item.get('sellers', [])
                    if not sellers: continue
                    offer = sellers[0].get('commertialOffer', {})
                    
                    p_o = float(offer.get('Price', 0.0))
                    p_r = float(offer.get('ListPrice', p_o))
                    
                    images = first_item.get('images', [])
                    img_url = images[0].get('imageUrl', '') if images else ""
                    if img_url.startswith('//'): img_url = 'https:' + img_url
                    
                    if 0 < p_o <= limite:
                        productos.append({
                            "nombre": f"OECHSLE - {nombre}",
                            "precio": p_o,
                            "precio_regular": max(p_r, p_o),
                            "link": link_final,
                            "img": img_url
                        })
                except Exception: continue
        else:
            safe_log(f"⚠️ [Oechsle API] Código {resp.status_code} recibido. Activando contingencia...", "warning")
            
    except Exception as e:
        safe_log(f"⚠️ [Oechsle API] Error durante la consulta directa: {e}. Activando contingencia...", "warning")
        
    if not productos:
        safe_log("🛡️ [Oechsle] Activando plan de contingencia HTML...", "info")
        try:
            html_headers = headers.copy()
            html_headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            
            clean_html_url = sanitizar_url(url)
            resp = requests.get(clean_html_url, headers=html_headers, timeout=15, verify=False)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                json_ld_prods = []
                scripts = soup.find_all('script', type='application/ld+json')
                for script in scripts:
                    try:
                        if not script.string: continue
                        data = json.loads(script.string)
                        if isinstance(data, dict) and data.get('@type') == 'ItemList':
                            items = data.get('itemListElement', [])
                            for item in items:
                                prod = item.get('item', {})
                                if isinstance(prod, dict) and prod.get('@type') == 'Product':
                                    json_ld_prods.append(prod)
                        elif isinstance(data, dict) and data.get('@type') == 'Product':
                            json_ld_prods.append(data)
                    except Exception: continue
                        
                if json_ld_prods:
                    vistos_links = set()
                    for prod in json_ld_prods:
                        try:
                            nombre = prod.get('name', '').upper()
                            link_final = prod.get('url', '')
                            if not link_final: continue
                            link_final = urljoin("https://www.oechsle.pe", link_final)
                            
                            if link_final in vistos_links: continue
                            
                            offers = prod.get('offers', {})
                            p_o = 0.0
                            if isinstance(offers, dict):
                                p_o = float(offers.get('price', 0.0))
                            elif isinstance(offers, list) and offers:
                                p_o = float(offers[0].get('price', 0.0))
                                
                            img_url = prod.get('image', '')
                            if isinstance(img_url, list) and img_url:
                                img_url = img_url[0]
                                
                            if 0 < p_o <= limite:
                                vistos_links.add(link_final)
                                productos.append({
                                    "nombre": f"OECHSLE - {nombre}",
                                    "precio": p_o,
                                    "precio_regular": p_o,
                                    "link": link_final,
                                    "img": img_url
                                })
                        except Exception: continue
        except Exception as he:
            safe_log(f"🛑 [Oechsle HTML] Error en contingencia: {he}", "error")
            
    if productos:
        safe_log(f"✅ [Oechsle] ¡Éxito! Se encontraron {len(productos)} ofertas que cumplen el presupuesto.", "success")
    else:
        safe_log(f"⚠️ [Oechsle] Búsqueda finalizada, pero ningún equipo baja de S/. {limite:.2f}", "warning")
        
    return productos
