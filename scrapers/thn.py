import re
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from config import LISTA_USER_AGENTS
from utils import sanitizar_url, limpiar_precio_pnp, safe_log

def motor_thn(url, limite):
    productos = []
    url = sanitizar_url(url)
    try:
        headers = {
            "User-Agent": random.choice(LISTA_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-PE,es;q=0.9"
        }
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        if resp.status_code != 200: return []
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        tarjetas = soup.find_all(['div', 'article', 'li'], class_=re.compile(r'(product-summary|product-card|item-card|vtex-product|grid-item)', re.I))
        
        for t in tarjetas:
            try:
                a_el = t.find('a', href=True)
                if not a_el: continue
                link_final = urljoin("https://www.thn.pe", a_el['href'])
                
                tit_el = t.find(['h2', 'h3', 'span', 'div'], class_=re.compile(r'(name|title|brand|description)', re.I))
                nombre = tit_el.text.strip().upper() if tit_el else ""
                if not nombre: nombre = a_el.text.strip().upper()
                if len(nombre) < 4: continue
                
                textos_precios = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', t.text)
                if not textos_precios: continue
                
                nums = sorted(list(set([limpiar_precio_pnp(p) for p in textos_precios if limpiar_precio_pnp(p) > 0])))
                if not nums: continue
                
                p_o = nums[0]
                p_r = nums[-1] if len(nums) > 1 else p_o
                
                if 0 < p_o <= limite:
                    img_tags = t.find_all('img')
                    img = ""
                    for img_el in img_tags:
                        src = img_el.get('data-src') or img_el.get('src') or ""
                        if src and 'data:image' not in str(src).lower() and 'pixel' not in str(src).lower():
                            img = src
                            break
                    if str(img).startswith('//'): img = 'https:' + str(img)
                    
                    productos.append({
                        "nombre": f"THN - {nombre}",
                        "precio": p_o,
                        "precio_regular": max(p_r, p_o),
                        "link": link_final,
                        "img": img
                    })
            except Exception: continue
                
    except Exception as e:
        safe_log(f"Aviso en motor THN: {e}", "caption")
        
    vistos = set()
    productos_unicos = []
    for p in productos:
        if p['link'] not in vistos:
            vistos.add(p['link'])
            productos_unicos.append(p)
            
    return productos_unicos
