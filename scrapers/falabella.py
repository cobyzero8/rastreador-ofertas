import time
import json
import random
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from utils import (
    sanitizar_url, 
    extraer_productos_json_universal, 
    safe_float, 
    limpiar_precio_pnp, 
    encontrar_foto_fala
)

def motor_falabella(url, limite, headers):
    productos = []
    url = sanitizar_url(url)
    try:
        texto_html = ""
        status_code = 0
        for intento in range(1, 3):
            try:
                resp = requests.get(url, headers=headers, timeout=15, verify=False)
                texto_html = resp.text
                status_code = resp.status_code
            except Exception: pass
            if status_code == 200 and len(texto_html) > 5000: break
            else: time.sleep(random.uniform(1.5, 3.0))
        
        if status_code != 200 or len(texto_html) < 5000: return []
        soup = BeautifulSoup(texto_html, 'html.parser')
        
        fala_prods = []
        scripts_fala = soup.find_all('script')
        for script in scripts_fala:
            if script.text and 'displayName' in script.text and len(script.text) > 1000:
                try:
                    txt = script.text.strip()
                    start_idx = txt.find('{')
                    end_idx = txt.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        json_data = json.loads(txt[start_idx:end_idx+1])
                        encontrados = extraer_productos_json_universal(json_data)
                        if encontrados:
                            fala_prods = encontrados
                            break
                except Exception: continue

        if fala_prods:
            for prod in fala_prods:
                try:
                    # 1. Validar enlace de producto (Descarta filtros como CROMO, PLATINO, etc.)
                    link_rel = prod.get('url') or prod.get('link') or prod.get('href') or ''
                    if not link_rel or ('/product/' not in link_rel and '/p/' not in link_rel):
                        continue
                    
                    nombre = str(prod.get('displayName') or prod.get('productName') or prod.get('title') or '').strip().upper()
                    if len(nombre) < 5: continue
                    
                    # 2. Extracción precisa de precios desde campos oficiales de Falabella
                    p_o, p_r = 0.0, 0.0
                    precios_list = prod.get('prices') or prod.get('price') or []
                    if isinstance(precios_list, dict): precios_list = [precios_list]
                    
                    if isinstance(precios_list, list):
                        for pr in precios_list:
                            if not isinstance(pr, dict): continue
                            tipo_p = str(pr.get('type', '')).lower()
                            val_p = pr.get('price') or pr.get('value')
                            if isinstance(val_p, list) and len(val_p) > 0: val_p = val_p[0]
                            float_p = safe_float(val_p)
                            if any(x in tipo_p for x in ['sale', 'event', 'oferta', 'internet', 'current', 'card', 'cmr', 'eventprice']): 
                                p_o = float_p
                            elif any(x in tipo_p for x in ['list', 'original', 'regular', 'normal', 'normalprice']): 
                                p_r = float_p

                    if p_o == 0.0: p_o = safe_float(prod.get('salePrice') or prod.get('price'))
                    if p_r == 0.0: p_r = safe_float(prod.get('listPrice') or prod.get('originalPrice') or prod.get('regularPrice') or p_o)
                    
                    # Descartar precios incoherentes o fuera del límite
                    if 0 < p_o <= limite:
                        link_final = urljoin("https://www.falabella.com.pe", link_rel)
                        img = encontrar_foto_fala(prod)
                        
                        if not img or '/product/' in str(img) or len(str(img)) < 15 or str(img).strip() in ['0', 'None', 'false']:
                            url_limpia = link_final.split('?')[0].split('#')[0]
                            match_id = [t for t in url_limpia.split('/') if t.isdigit() and len(t) >= 7]
                            if match_id: img = f"https://media.falabella.com/falabellaPE/{match_id[-1]}_01/w=800,h=800,fit=pad"
                        
                        if str(img).startswith('//'): img = 'https:' + str(img)
                        img = str(img).split(' ')[0].strip().rstrip(',')
                        productos.append({
                            "nombre": f"FALABELLA - {nombre}", 
                            "precio": p_o, 
                            "precio_regular": max(p_r, p_o), 
                            "link": link_final, 
                            "img": str(img)
                        })
                except Exception: continue

        # Fallback HTML en caso el JSON no devuelva datos
        if not productos:
            items = soup.find_all(['div', 'li', 'article'], class_=re.compile(r'(pod|card|product-item|item)', re.I))
            for t in items:
                try:
                    a_el = t.find('a', href=True) or (t if t.name == 'a' else None)
                    if not a_el or '/product/' not in a_el['href']: continue
                    
                    link_final = urljoin(url, a_el['href'])
                    tit_el = t.find(['b', 'span', 'p', 'h3', 'h4', 'a'], class_=re.compile(r'(title|name|description|displayName)', re.I))
                    if not tit_el or len(tit_el.text.strip()) < 5: continue
                    
                    el_event = t.find(attrs={"data-event-price": True}) or t.select_one('[data-event-price]')
                    el_normal = t.find(attrs={"data-normal-price": True}) or t.select_one('[data-normal-price]')
                    
                    p_o = safe_float(el_event.get('data-event-price')) if el_event else 0.0
                    if p_o == 0.0:
                        o_el = t.find(class_=re.compile(r'(salePrice|price-value|oferta|current-price|eventPrice)', re.I))
                        if o_el: p_o = limpiar_precio_pnp(o_el.text)
                        
                    p_r = safe_float(el_normal.get('data-normal-price')) if el_normal else p_o
                    if p_r == 0.0:
                        r_el = t.find(class_=re.compile(r'(listPrice|regular-price|old-price|normal-price)', re.I))
                        if r_el: p_r = limpiar_precio_pnp(r_el.text)
                    
                    if 0 < p_o <= limite:
                        img_el = t.select_one('img[id^="testId-pod-image-"]') or t.find('img')
                        img = ''
                        if img_el:
                            for attr in ['data-srcset', 'srcset', 'data-src', 'src', 'data-lazy']:
                                val = img_el.get(attr)
                                if val and 'data:image' not in str(val) and len(str(val)) > 10:
                                    img = str(val).split(' ')[0].strip()
                                    break
                        
                        if not img or len(str(img)) < 15:
                            url_limpia = link_final.split('?')[0].split('#')[0]
                            match_id = [t for t in url_limpia.split('/') if t.isdigit() and len(t) >= 7]
                            if match_id: img = f"https://media.falabella.com/falabellaPE/{match_id[-1]}_01/w=800,h=800,fit=pad"
                        
                        if str(img).startswith('//'): img = 'https:' + str(img)
                        productos.append({
                            "nombre": f"FALABELLA - {tit_el.text.strip().upper()}", 
                            "precio": p_o, 
                            "precio_regular": max(p_r, p_o), 
                            "link": link_final, 
                            "img": img
                        })
                except Exception: continue

        vistos = set()
        productos_unicos = []
        for p in productos:
            if p['link'] not in vistos:
                vistos.add(p['link'])
                productos_unicos.append(p)
        return productos_unicos
    except Exception: pass
    return productos
