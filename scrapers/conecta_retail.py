import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from utils import sanitizar_url, limpiar_precio_pnp

def motor_conecta_retail(url, limite=999999.0, headers=None):
    productos = []
    url = sanitizar_url(url)
    try:
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for t in (soup.select('.product-item') or soup.select('.product-item-info')):
                try:
                    tit_el = t.select_one('a.product-item-link') or t.select_one('.product-item-name a')
                    if not tit_el: continue
                    o_el = t.select_one('[data-price-type="finalPrice"] .price') or t.select_one('.special-price .price') or t.select_one('.price-box .price')
                    r_el = t.select_one('[data-price-type="oldPrice"] .price') or t.select_one('.old-price .price')
                    if not o_el: continue
                    p_o = limpiar_precio_pnp(o_el.text)
                    if 0 < p_o <= limite:
                        img_el = t.select_one('.product-image-photo') or t.find('img')
                        img = img_el.get('data-src') or img_el.get('src') or '' if img_el else ''
                        if img.startswith('//'): img = 'https:' + img
                        productos.append({
                            "nombre": f"{tag} - {tit_el.text.strip().upper()}",
                            "precio": p_o,
                            "precio_regular": limpiar_precio_pnp(r_el.text) if r_el else p_o,
                            "link": urljoin(url, tit_el['href']),
                            "img": img
                        })
                except Exception: continue
    except Exception: pass
    return productos
