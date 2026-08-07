import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from utils import sanitizar_url, limpiar_precio_pnp

def motor_tradicional_general(url, limite, headers):
    productos = []
    url = sanitizar_url(url)
    try:
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        if resp.status_code in [200, 206]:
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = soup.find_all(['div', 'article', 'li', 'a'], class_=lambda x: x and any(k in x.lower() for k in ['product', 'card', 'item', 'grid']))
            for t in items:
                try:
                    tit = t.find(['h3', 'h2', 'span', 'p', 'div', 'a'], class_=re.compile(r'(title|name|nombre|description)', re.I))
                    if not tit or len(tit.text.strip()) < 3: continue
                    precios = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', t.text)
                    if precios:
                        p_o = limpiar_precio_pnp(precios[0])
                        if p_o <= limite:
                            del_el = t.find(['del', 'span'], class_=re.compile(r'(regular|original|old)', re.I))
                            p_r_matches = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', del_el.text) if del_el else []
                            p_r = limpiar_precio_pnp(p_r_matches[0]) if p_r_matches else p_o
                            a_el = t.find('a', href=True) or (t if t.name == 'a' and t.has_attr('href') else None)
                            if a_el and 'productos?' not in a_el['href'].lower():
                                img_el = t.find('img', src=True)
                                productos.append({
                                    "nombre": tit.text.strip().upper(),
                                    "precio": p_o,
                                    "precio_regular": p_r,
                                    "link": urljoin(url, a_el['href']),
                                    "img": img_el['src'] if img_el else ""
                                })
                except Exception: continue
    except Exception: pass
    return productos
