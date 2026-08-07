import re
import time
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, urljoin
from utils import sanitizar_url, safe_log, limpiar_precio_pnp

def motor_triathlon(url, limite, headers=None):
    productos_map = {}
    vistos_links = set()
    url = sanitizar_url(url)
    
    if not headers:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9;image/webp,*/*;q=0.8",
            "Accept-Language": "es-PE,es;q=0.9",
            "Referer": "https://www.triathlon.com.pe/"
        }

    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        for page_num in range(1, 4):
            query_params['page'] = [str(page_num)]
            new_query = urlencode(query_params, doseq=True)
            page_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, new_query, parsed_url.fragment))

            resp = requests.get(page_url, headers=headers, timeout=15, verify=False)
            if resp.status_code != 200: break

            soup = BeautifulSoup(resp.text, 'html.parser')
            tarjetas = soup.select('[class*="product-summary-"]') or soup.select('[class*="vtex-product-summary-"]') or soup.select('[class*="summaryContainer"]')

            if not tarjetas: break
                
            for t in tarjetas:
                try:
                    link_final = ""
                    for a in t.find_all('a', href=True):
                        href = a['href'].lower()
                        if '/p' in href and not any(x in href for x in ['/account', '/checkout', '/cart', '/busca', '/login']):
                            link_final = urljoin("https://www.triathlon.com.pe", a['href'])
                            break
                    
                    if not link_final: continue

                    nombre_el = t.select_one('[class*="productName"]') or t.select_one('[class*="brandName"]') or t.select_one('[class*="productBrand"]')
                    raw_nombre = nombre_el.text.strip() if nombre_el else ""
                    
                    if not raw_nombre or len(raw_nombre) < 5 or raw_nombre.upper() in ['ADIDAS', 'PUMA', 'NIKE', 'UNDER ARMOUR']:
                        textos_internos = [a.get_text().strip() for a in t.find_all('a') if len(a.get_text().strip()) > 5]
                        raw_nombre = max(textos_internos, key=len) if textos_internos else "ZAPATILLA SPORT"

                    nombre_limpio = re.sub(r'-\d+%', '', raw_nombre)
                    nombre_limpio = re.sub(r'(?:S/\.?\s*)(\d[\d\.,]*)', '', nombre_limpio)
                    nombre_limpio = nombre_limpio.replace("Antes:", "").replace("Ahora:", "").strip().upper()
                    nombre_limpio = re.sub(r'\s+', ' ', nombre_limpio)

                    if len(nombre_limpio) < 4: continue

                    texto_tarjeta = t.get_text()
                    textos_precios = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', texto_tarjeta)
                    if not textos_precios: continue
                        
                    precios_num = sorted(list(set([limpiar_precio_pnp(p) for p in textos_precios if limpiar_precio_pnp(p) > 0])))
                    if not precios_num: continue
                        
                    p_o = precios_num[0]
                    p_r = precios_num[-1] if len(precios_num) > 1 else p_o

                    img_el = t.find('img')
                    img_url = ""
                    if img_el:
                        srcset = img_el.get('srcset') or img_el.get('data-srcset')
                        if srcset:
                            urls_set = re.findall(r'(https?://\S+)', srcset)
                            if urls_set: img_url = urls_set[0].split('?')[0]
                        if not img_url: img_url = img_el.get('data-src') or img_el.get('src') or ""

                    if img_url.startswith('//'): img_url = 'https:' + img_url
                    if 'data:image' in img_url.lower() or 'pixel' in img_url.lower(): img_url = ""

                    if 0 < p_o <= limite:
                        if link_final in vistos_links: continue
                        vistos_links.add(link_final)
                        
                        productos_map[link_final] = {
                            "nombre": f"Triathlon - {nombre_limpio}",
                            "precio": p_o,
                            "precio_regular": max(p_r, p_o),
                            "link": link_final,
                            "img": img_url
                        }
                except Exception: continue
            time.sleep(0.5)

    except Exception as e:
        safe_log(f"🛑 [Triathlon] Error crítico en paginación: {e}", "error")

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [Triathlon] ¡Éxito! Se consolidaron {len(productos_finales)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [Triathlon] No se encontraron ofertas bajo el límite de S/. {limite:.2f}", "warning")

    return productos_finales
