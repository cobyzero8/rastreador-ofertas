import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from utils import sanitizar_url, limpiar_precio_pnp

def motor_hiraoka(url, limite):
    productos = []
    url = sanitizar_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        if resp.status_code != 200: return []
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        tarjetas = soup.select('.product-item') or soup.select('.product-item-info') or soup.select('.item.product')
        
        for t in tarjetas:
            try:
                tit_el = t.select_one('.product-item-link') or t.select_one('.product-item-name a') or t.select_one('.product-name a')
                if not tit_el: continue
                nombre = tit_el.text.strip().upper()
                link_final = urljoin("https://hiraoka.com.pe", tit_el['href'])
                
                o_el = t.select_one('[data-price-type="finalPrice"] .price') or t.select_one('.special-price .price') or t.select_one('.price-box .price')
                r_el = t.select_one('[data-price-type="oldPrice"] .price') or t.select_one('.old-price .price')
                
                if not o_el:
                    textos_precios = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', t.text)
                    if textos_precios:
                        nums = sorted(list(set([limpiar_precio_pnp(p) for p in textos_precios if limpiar_precio_pnp(p) > 0])))
                        p_o = nums[0] if nums else 0.0
                        p_r = nums[-1] if len(nums) > 1 else p_o
                    else:
                        continue
                else:
                    p_o = limpiar_precio_pnp(o_el.text)
                    p_r = limpiar_precio_pnp(r_el.text) if r_el else p_o
                
                if 0 < p_o <= limite:
                    img_el = t.select_one('.product-image-photo') or t.find('img')
                    img_url = ""
                    if img_el:
                        img_url = img_el.get('data-src') or img_el.get('src') or ""
                    if img_url.startswith('//'): img_url = 'https:' + img_url
                    
                    productos.append({
                        "nombre": f"HIRAOKA - {nombre}",
                        "precio": p_o,
                        "precio_regular": max(p_r, p_o),
                        "link": link_final,
                        "img": img_url
                    })
            except Exception: continue
                
    except Exception as e:
        print(f"Error en motor Hiraoka: {e}")
        
    return productos
