import os
import json
import requests
import httpx
from bs4 import BeautifulSoup
import re
import time
import random
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse, parse_qs, quote
from supabase import create_client, Client
import urllib3
import streamlit as st
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =======================================================
# 🛡️ CONFIGURACIÓN DE ENTORNO BLINDADA
# =======================================================
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

try:
    if "SUPABASE_KEY" in st.secrets: 
        SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    if "TELEGRAM_TOKEN" in st.secrets: 
        TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
    if "TELEGRAM_CHAT_ID" in st.secrets: 
        TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
except Exception: 
    pass

if SUPABASE_URL and SUPABASE_KEY: 
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else: 
    raise ValueError("Error crítico: Falta SUPABASE_KEY.")

LISTA_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0"
]

# =======================================================
# 🛠️ HERRAMIENTAS AUXILIARES GLOBALES
# =======================================================
def safe_log(texto, tipo="text"):
    try:
        if tipo == "text" or tipo == "write": st.write(texto)
        elif tipo == "caption": st.caption(texto)
        elif tipo == "info": st.info(texto)
        elif tipo == "error": st.error(texto)
        elif tipo == "success": st.success(texto)
        elif tipo == "warning": st.warning(texto)
        elif tipo == "toast": st.toast(texto)
    except Exception:
        print(f"[{tipo.upper()}] {texto}")

def limpiar_precio_pnp(texto_precio):
    if not texto_precio: return 0.0
    try:
        texto = re.sub(r'[^\d.,]', '', texto_precio).strip()
        if not texto: return 0.0
        if ',' in texto and '.' in texto:
            if texto.rfind('.') > texto.rfind(','): texto = texto.replace(',', '')
            else: texto = texto.replace('.', '').replace(',', '.')
        else:
            if ',' in texto and len(texto.split(',')[-1]) != 2: texto = texto.replace(',', '')
            elif '.' in texto and len(texto.split('.')[-1]) != 2: texto = texto.replace('.', '')
            elif ',' in texto: texto = texto.replace(',', '.')
        match = re.findall(r'\d+\.\d+|\d+', texto)
        return float(match[0]) if match else 0.0
    except Exception: return 0.0

def safe_float(val):
    if val is None: return 0.0
    if isinstance(val, (int, float)): return float(val)
    return limpiar_precio_pnp(str(val))

def enviar_telegram_real(mensaje, link_producto="", url_imagen=""):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return False
    mensaje_html = f"{mensaje}\n\n👉 <a href='{link_producto}'><b>¡COMPRAR AQUÍ!</b></a>"
    url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto" if url_imagen else f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "parse_mode": "HTML"}
    if url_imagen: 
        payload["photo"], payload["caption"] = url_imagen, mensaje_html
    else: 
        payload["text"] = mensaje_html
    try: return requests.post(url_api, json=payload, timeout=10).status_code == 200
    except Exception: return False

def extraer_productos_json_universal(nodo):
    coleccion = []
    if isinstance(nodo, dict):
        if any(k in nodo for k in ['displayName', 'productName', 'title', 'name']) and any(k in nodo for k in ['prices', 'price', 'salePrice', 'value']):
            nombre = nodo.get('displayName') or nodo.get('productName') or nodo.get('title') or nodo.get('name')
            if nombre and len(str(nombre).strip()) > 3: coleccion.append(nodo)
        for v in nodo.values(): coleccion.extend(extraer_productos_json_universal(v))
    elif isinstance(nodo, list):
        for item in nodo: coleccion.extend(extraer_productos_json_universal(item))
    return coleccion

def encontrar_foto_fala(nodo):
    if isinstance(nodo, str):
        if (nodo.startswith('http') or nodo.startswith('//')) and ('falabella' in nodo or 'media' in nodo or any(ext in nodo.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp'])) and '/product/' not in nodo: return nodo
    elif isinstance(nodo, dict):
        for k in ['imageUrl', 'src', 'url', 'thumbnail', 'image']:
            val = nodo.get(k)
            if isinstance(val, str) and (val.startswith('http') or val.startswith('//')) and len(val) > 10 and '/product/' not in val: return val
        for v in nodo.values():
            res = encontrar_foto_fala(v)
            if res: return res
    elif isinstance(nodo, list):
        for item in nodo:
            res = encontrar_foto_fala(item)
            if res: return res
    return ''

def extraer_numeros_dict(d, valores_aux):
    if isinstance(d, dict):
        d_keys_str = "".join(d.keys()).lower()
        if any(x in d_keys_str for x in ['size', 'talla', 'option', 'variant']):
            for sub_v in d.values(): extraer_numeros_dict(sub_v, valores_aux)
            return
        for k, v in d.items():
            if any(x in k.lower() for x in ['price', 'precio']):
                if isinstance(v, (int, float)): valores_aux.append(float(v))
                elif isinstance(v, str):
                    fv = limpiar_precio_pnp(v)
                    if fv > 0: valores_aux.append(fv)
            elif 'value' in k.lower():
                contexto_valido = any(x in str(d).lower() for x in ['price', 'precio', 'sale', 'list', 'oferta', 'regular', 'internet', 'cmr'])
                contexto_invalido = any(x in str(d).lower() for x in ['size', 'talla', 'option', 'variant', 'sku'])
                if contexto_valido and not contexto_invalido:
                    if isinstance(v, (int, float)): valores_aux.append(float(v))
                    elif isinstance(v, str):
                        fv = limpiar_precio_pnp(v)
                        if fv > 0: valores_aux.append(fv)
        for sub_v in d.values(): extraer_numeros_dict(sub_v, valores_aux)
    elif isinstance(d, list):
        for item in d: extraer_numeros_dict(item, valores_aux)

# =======================================================
# 🚀 MOTORES DE EXTRACCIÓN (AISLADOS E INDEPENDIENTES)
# =======================================================

def motor_thn(url, limite):
    productos = []
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

def motor_belcorp(url, limite, headers):
    productos = []
    dominio = urlparse(url).netloc.lower()
    marca = "cyzone" if "cyzone" in dominio else "lbel" if "lbel" in dominio else "esika"
    try:
        resp = requests.get(f"https://{marca}.tiendabelcorp.com.pe/api/catalog_system/pub/products/search", headers=headers, params={"ft": "perfume", "_from": 0, "_to": 20, "O": "OrderByPriceASC"}, timeout=15, verify=False)
        for item in resp.json():
            offer = item["items"][0]["sellers"][0]["commertialOffer"]
            if 0 < float(offer["Price"]) <= limite:
                productos.append({"nombre": f"{marca.upper()} - {item['productName'].upper()}", "precio": float(offer["Price"]), "precio_regular": float(offer.get("ListPrice", offer["Price"])), "link": item["link"], "img": item["items"][0]["images"][0]["imageUrl"]})
    except Exception: pass
    return productos

def motor_conecta_retail(url, limite, headers, tag):
    productos = []
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
                        productos.append({"nombre": f"{tag} - {tit_el.text.strip().upper()}", "precio": p_o, "precio_regular": limpiar_precio_pnp(r_el.text) if r_el else p_o, "link": urljoin(url, tit_el['href']), "img": img})
                except Exception: continue
    except Exception: pass
    return productos

def motor_falabella(url, limite, headers):
    productos = []
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
                    nombre = str(prod.get('displayName') or prod.get('productName') or prod.get('title') or '').strip().upper()
                    if len(nombre) < 3: continue
                    
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
                            if any(x in tipo_p for x in ['sale', 'event', 'oferta', 'internet', 'current', 'card', 'cmr', 'eventprice']): p_o = float_p
                            elif any(x in tipo_p for x in ['list', 'original', 'regular', 'normal', 'normalprice']): p_r = float_p
                        
                        if p_o == 0.0 or p_r <= p_o:
                            valores_aux = []
                            extraer_numeros_dict(prod, valores_aux)
                            valores_unicos = sorted(list(set(valores_aux)))
                            if len(valores_unicos) >= 2:
                                p_o = valores_unicos[0]
                                p_r = valores_unicos[-1]
                            elif len(valores_unicos) == 1:
                                p_o = valores_unicos[0]
                                if p_r == 0.0: p_r = p_o

                    if p_o == 0.0: p_o = safe_float(prod.get('salePrice') or prod.get('price'))
                    if p_r == 0.0: p_r = safe_float(prod.get('listPrice') or prod.get('originalPrice') or prod.get('regularPrice') or p_o)
                    
                    if 0 < p_o <= limite:
                        link_rel = prod.get('url') or prod.get('link') or prod.get('href') or ''
                        link_final = urljoin("https://www.falabella.com.pe", link_rel)
                        img = encontrar_foto_fala(prod)
                        
                        if not img or '/product/' in str(img) or len(str(img)) < 15 or str(img).strip() in ['0', 'None', 'false']:
                            url_limpia = link_final.split('?')[0].split('#')[0]
                            match_id = [t for t in url_limpia.split('/') if t.isdigit() and len(t) >= 7]
                            if match_id: img = f"https://media.falabella.com/falabellaPE/{match_id[-1]}_01/w=800,h=800,fit=pad"
                        
                        if str(img).startswith('//'): img = 'https:' + str(img)
                        img = str(img).split(' ')[0].strip().rstrip(',')
                        productos.append({"nombre": f"FALABELLA - {nombre}", "precio": p_o, "precio_regular": max(p_r, p_o), "link": link_final, "img": str(img)})
                except Exception: continue

        if not productos:
            items = soup.find_all(['div', 'li', 'article'], class_=re.compile(r'(pod|card|product-item|item)', re.I))
            for t in items:
                try:
                    tit_el = t.find(['b', 'span', 'p', 'h3', 'h4', 'a'], id=re.compile(r'name', re.I)) or t.find(['b', 'span', 'p', 'h3', 'h4', 'a'], class_=re.compile(r'(title|name|description|displayName)', re.I))
                    if not tit_el or len(tit_el.text.strip()) < 3: continue
                    
                    el_event = t.find(attrs={"data-event-price": True}) or t.select_one('[data-event-price]')
                    el_normal = t.find(attrs={"data-normal-price": True}) or t.select_one('[data-normal-price]')
                    
                    p_o = 0.0
                    if el_event: p_o = safe_float(el_event.get('data-event-price'))
                    else:
                        o_el = t.find(id=re.compile(r'(salePrice|offerPrice|currentPrice|precio|event)', re.I)) or t.find(class_=re.compile(r'(salePrice|price-value|oferta|current-price|price-item|eventPrice)', re.I))
                        if o_el: p_o = limpiar_precio_pnp(o_el.text)
                        
                    p_r = p_o
                    if el_normal: p_r = safe_float(el_normal.get('data-normal-price'))
                    else:
                        r_el = t.find(id=re.compile(r'(listPrice|regularPrice|oldPrice|normal)', re.I)) or t.find(class_=re.compile(r'(listPrice|regular-price|old-price|normal-price)', re.I))
                        if r_el: p_r = limpiar_precio_pnp(r_el.text)
                    
                    if 0 < p_o <= limite:
                        a_el = t.find('a', href=True) or (t if t.name == 'a' else None)
                        link_final = urljoin(url, a_el['href']) if a_el else url
                        img_el = t.select_one('img[id^="testId-pod-image-"]') or t.find('img', id=re.compile(r'image', re.I)) or t.find('img')
                        img = ''
                        if img_el:
                            for attr in ['data-srcset', 'srcset', 'data-src', 'src', 'data-lazy']:
                                val = img_el.get(attr)
                                if val and 'data:image' not in str(val) and len(str(val)) > 10:
                                    img = str(val).split(' ')[0].strip()
                                    break
                        
                        if not img or '/product/' in str(img) or len(str(img)) < 15 or str(img).strip() in ['0', 'None', 'false']:
                            url_limpia = link_final.split('?')[0].split('#')[0]
                            match_id = [t for t in url_limpia.split('/') if t.isdigit() and len(t) >= 7]
                            if match_id: img = f"https://media.falabella.com/falabellaPE/{match_id[-1]}_01/w=800,h=800,fit=pad"
                        
                        if str(img).startswith('//'): img = 'https:' + str(img)
                        img = str(img).split(' ')[0].strip().rstrip(',')
                        productos.append({"nombre": f"FALABELLA - {tit_el.text.strip().upper()}", "precio": p_o, "precio_regular": max(p_r, p_o), "link": link_final, "img": img})
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

def motor_adidas(url, limite):
    return []

def motor_platanitos(url, limite):
    productos = []
    try:
        texto_html = ""
        try:
            headers = {"User-Agent": random.choice(LISTA_USER_AGENTS), "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8", "Accept-Language": "es-ES,es;q=0.9"}
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            texto_html = resp.text
        except Exception: pass

        if not texto_html or len(texto_html) < 2000: return []
        soup = BeautifulSoup(texto_html, 'html.parser')
        tarjetas = soup.find_all(['div', 'article', 'a'], class_=re.compile(r'(product|card|item|col|grid)', re.I))
                    
        for t in tarjetas:
            try:
                a_el = t.find('a', href=re.compile(r'/producto/', re.I)) or (t if t.name == 'a' and '/producto/' in t.get('href', '').lower() else None)
                if not a_el: continue
                link_final = urljoin("https://platanitos.com", a_el['href'])
                tit_el = t.find(['h3', 'h2', 'span', 'p', 'div'], class_=re.compile(r'(title|name|nombre|description)', re.I))
                nombre = tit_el.text.strip() if tit_el else ""
                if not nombre and a_el.has_attr('title'): nombre = a_el['title'].strip()
                if len(nombre) < 3 or "PLATANITOS" in nombre.upper(): continue
                
                textos_precios = []
                for el in t.find_all(['span', 'p', 'b', 'strong', 'del', 'small']):
                    if el.find(['span', 'p', 'b', 'strong', 'del', 'small']): continue
                    txt_el = el.text.strip() if el.text else ""
                    if 'S/' in txt_el and '%' not in txt_el and len(txt_el) < 20:
                        textos_precios.extend(re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', txt_el))
                        
                if not textos_precios: continue
                nums = sorted(list(set([limpiar_precio_pnp(p) for p in textos_precios if limpiar_precio_pnp(p) > 0])))
                if not nums: continue
                p_o = nums[0]
                p_r = nums[-1] if len(nums) > 1 else p_o
                
                if 0 < p_o <= limite:
                    img = ""
                    img_tags = t.find_all('img')
                    for img_el in img_tags:
                        src_candidato = img_el.get('data-src') or img_el.get('src') or img_el.get('data-lazy') or ""
                        if src_candidato and 'data:image' not in str(src_candidato).lower():
                            img = src_candidato
                            break
                    if str(img).startswith('//'): img = 'https:' + str(img)
                    productos.append({"nombre": f"PLATANITOS - {nombre.upper()}", "precio": p_o, "precio_regular": p_r, "link": link_final, "img": img})
            except Exception: continue
    except Exception: pass
    return productos

def motor_hiraoka(url, limite):
    productos = []
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
            except Exception:
                continue
                
    except Exception as e:
        print(f"Error en motor Hiraoka: {e}")
        
    return productos

def motor_carsa(url, limite):
    productos = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive"
    }
    
    try:
        safe_log(f"🚀 [Diag CARSA] Lanzando motor de alta fidelidad a: {url}", "info")
        session = requests.Session()
        resp = session.get(url, headers=headers, timeout=20, allow_redirects=True, verify=False)
        
        safe_log(f"📡 [Diag CARSA] Código de respuesta: {resp.status_code} | Tamaño: {len(resp.text)}", "info")
        
        if resp.status_code != 200:
            safe_log(f"🛑 [Diag CARSA] Bloqueo total por Firewall/Anti-Bot. Código {resp.status_code}", "error")
            return []

        matches = re.findall(r'"productName":"([^"]+)".*?"Price":(\d+\.?\d*)', resp.text)
        
        if not matches:
            safe_log("🛑 [Diag CARSA] Descarga exitosa, pero no encontramos productos con el buscador de texto.", "error")
        else:
            for nombre, precio in matches:
                p = float(precio)
                if 0 < p <= limite:
                    productos.append({"nombre": f"CARSA - {nombre}", "precio": p, "precio_regular": p, "link": url, "img": ""})
            safe_log(f"✅ [Diag CARSA] Se encontraron {len(matches)} productos. {len(productos)} cumplen el límite.", "success")
            
    except Exception as e:
        safe_log(f"🛑 [Diag CARSA] Error crítico: {str(e)}", "error")
        
    return productos

def motor_oechsle(url, limite):
    import json
    import re
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urlparse, urljoin
    
    productos = []
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
        
        if has_category_filter:
            api_url = f"https://www.oechsle.pe/api/catalog_system/pub/products/search?{raw_query}"
        else:
            category_path = parsed_url.path.rstrip('/')
            if category_path and not category_path.startswith('/'):
                category_path = '/' + category_path
            api_url = f"https://www.oechsle.pe/api/catalog_system/pub/products/search{category_path}?{raw_query}"
            
        if '_from=' not in api_url:
            api_url += "&_from=0&_to=49"
            
        safe_log("📡 [Oechsle] Conectando con la base de datos oficial...", "info")
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
                except Exception:
                    continue
        else:
            safe_log(f"⚠️ [Oechsle API] Código {resp.status_code} recibido. Activando contingencia de rescate...", "warning")
            
    except Exception as e:
        safe_log(f"⚠️ [Oechsle API] Error durante la consulta directa: {e}. Activando contingencia...", "warning")
        
    if not productos:
        safe_log("🛡️ [Oechsle] Activando plan de contingencia HTML...", "info")
        try:
            html_headers = headers.copy()
            html_headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            resp = requests.get(url, headers=html_headers, timeout=15, verify=False)
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
                    except Exception:
                        continue
                        
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
                        except Exception:
                            continue
        except Exception as he:
            safe_log(f"🛑 [Oechsle HTML] Error en contingencia: {he}", "error")
            
    if productos:
        safe_log(f"✅ [Oechsle] ¡Éxito! Se encontraron {len(productos)} ofertas que cumplen el presupuesto.", "success")
    else:
        safe_log(f"⚠️ [Oechsle] Búsqueda finalizada, pero ningún equipo baja de S/. {limite:.2f}", "warning")
        
    return productos

def motor_plazavea(url, limite, headers=None):
    import requests
    from urllib.parse import urlparse, parse_qs, urljoin

    productos = []
    
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
                except Exception:
                    continue
        else:
            safe_log(f"🛑 [Plaza Vea API] Error de conexión con VTEX. Código HTTP: {resp.status_code}", "error")

    except Exception as e:
        safe_log(f"🛑 [Plaza Vea API] Error crítico inesperado: {e}", "error")

    if productos:
        safe_log(f"✅ [Plaza Vea API] ¡Éxito! Se indexaron {len(productos)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [Plaza Vea API] No se encontraron productos bajo el límite de S/. {limite:.2f}", "warning")

    return productos

def motor_juntoz(url, limite, headers=None):
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    import re
    import random

    productos_map = {}
    
    if not headers:
        headers = {
            "User-Agent": random.choice(LISTA_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
            "Referer": "https://www.juntoz.com/"
        }

    try:
        safe_log(f"📡 [Juntoz] Descargando catálogo por HTML...", "info")
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        
        if resp.status_code != 200:
            safe_log(f"🛑 [Juntoz] Error de servidor. Código: {resp.status_code}", "error")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        enlaces_productos = []
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if ('/p/' in href or '/producto/' in href) and not any(x in href for x in ['/politica', '/ayuda', '/terminos', '/catalogo', '/tienda']):
                enlaces_productos.append(a)

        for a_el in enlaces_productos:
            try:
                href_rel = a_el['href']
                link_final = urljoin("https://juntoz.com", href_rel)
                
                contenedor_tarjeta = None
                ancestro_actual = a_el.parent
                
                for _ in range(6):
                    if not ancestro_actual or ancestro_actual.name in ['body', 'html']: break
                    texto_ancestro = ancestro_actual.get_text()
                    if 'S/.' in texto_ancestro or 'S/' in texto_ancestro:
                        contenedor_tarjeta = ancestro_actual
                        break
                    ancestro_actual = ancestro_actual.parent

                if not contenedor_tarjeta: continue

                nombre = a_el.get_text(separator=" ").strip().upper()
                if not nombre or len(nombre) < 5:
                    for otro_a in contenedor_tarjeta.find_all('a', href=True):
                        if otro_a['href'] == href_rel:
                            nombre_otro = otro_a.get_text(separator=" ").strip().upper()
                            if nombre_otro and len(nombre_otro) >= 5:
                                nombre = nombre_otro
                                break

                if not nombre or len(nombre) < 5:
                    img_el = contenedor_tarjeta.find('img')
                    if img_el and img_el.get('alt'):
                        nombre = img_el['alt'].strip().upper()

                if not nombre or len(nombre) < 5: continue
                nombre = nombre.replace("AGREGAR A CARRITO", "").replace("AGREGAR", "").strip()
                nombre = re.sub(r'\s+', ' ', nombre)

                texto_tarjeta = contenedor_tarjeta.get_text()
                textos_precios = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', texto_tarjeta)
                if not textos_precios: continue

                precios_numeros = [limpiar_precio_pnp(p) for p in textos_precios if limpiar_precio_pnp(p) > 0]
                if not precios_numeros: continue

                precios_unicos = sorted(list(set(precios_numeros)))
                p_o = precios_unicos[0]
                p_r = precios_unicos[-1] if len(precios_unicos) > 1 else p_o

                img_el = contenedor_tarjeta.find('img')
                img_url = ""
                if img_el:
                    img_url = img_el.get('data-src') or img_el.get('src') or img_el.get('data-lazy') or img_el.get('data-original') or ""
                
                if img_url.startswith('//'): img_url = 'https:' + img_url
                elif img_url and not img_url.startswith('http'): img_url = urljoin("https://juntoz.com", img_url)

                if 'data:image' in img_url.lower() or 'pixel' in img_url.lower(): img_url = ""

                if 0 < p_o <= limite:
                    if link_final in productos_map:
                        prod_existente = productos_map[link_final]
                        if len(nombre) > len(prod_existente['nombre']) or (img_url and not prod_existente['img']):
                            productos_map[link_final] = {
                                "nombre": f"Juntoz - {nombre}",
                                "precio": p_o,
                                "precio_regular": max(p_r, p_o),
                                "link": link_final,
                                "img": img_url or prod_existente['img']
                            }
                    else:
                        productos_map[link_final] = {
                            "nombre": f"Juntoz - {nombre}",
                            "precio": p_o,
                            "precio_regular": max(p_r, p_o),
                            "link": link_final,
                            "img": img_url
                        }
            except Exception:
                continue

    except Exception as e:
        safe_log(f"🛑 [Juntoz] Error crítico inesperado: {e}", "error")

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [Juntoz] ¡Éxito! Se indexaron {len(productos_finales)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [Juntoz] No se encontraron productos bajo el límite de S/. {limite:.2f}", "warning")

    return productos_finales

def motor_triathlon(url, limite, headers=None):
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urlparse, urlunparse, parse_qs, urlencode, urljoin
    import re
    import time

    productos_map = {}
    vistos_links = set()
    
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

def motor_ripley(url, limite, headers=None):
    safe_log("⏸️ [Ripley] Motor pausado temporalmente.", "caption")
    return []



def motor_footloose(url, limite):
    import requests
    from urllib.parse import urlparse, parse_qs, urljoin
    import re
    import random

    productos_map = {}
    headers = {
        "User-Agent": random.choice(LISTA_USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9",
        "Referer": "https://www.footloose.pe/"
    }

    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        # 1. Extraer la ruta raw de la consulta
        raw_path = parsed_url.path.rstrip('/')
        if 'query' in query_params:
            q_val = query_params['query'][0]
            if q_val.startswith('/'):
                raw_path = q_val.rstrip('/')

        # 2. Sanitizar segmentos descartando tallas numéricas que rompen VTEX (ej. "9-5")
        segmentos = [s for s in raw_path.split('/') if s and not re.match(r'^\d+[\-_.]\d+$', s)]
        path_limpio = '/' + '/'.join(segmentos) if segmentos else "/calzados"
        path_base = '/' + '/'.join(segmentos[:2]) if len(segmentos) >= 2 else path_limpio

        # 3. Construcción del plan de peticiones secuenciales
        urls_a_probar = []

        # Plan A: Path limpio omitiendo mapas de talla incompatibles
        if "map" in query_params:
            maps = query_params["map"][0].split(',')
            maps_validos = [m for m in maps if m in ['c', 'category-1', 'category-2', 'category-3', 'brand', 'b']]
            if maps_validos and len(maps_validos) == len(segmentos):
                urls_a_probar.append((f"https://www.footloose.pe/api/catalog_system/pub/products/search{path_limpio}", {"O": "OrderByPriceASC", "_from": "0", "_to": "49", "map": ",".join(maps_validos)}))

        # Plan B: Path limpio directo sin parámetro map
        urls_a_probar.append((f"https://www.footloose.pe/api/catalog_system/pub/products/search{path_limpio}", {"O": "OrderByPriceASC", "_from": "0", "_to": "49"}))
        
        # Plan C: Desescalado a categoría raíz (/calzados/hombres)
        if path_base != path_limpio:
            urls_a_probar.append((f"https://www.footloose.pe/api/catalog_system/pub/products/search{path_base}", {"O": "OrderByPriceASC", "_from": "0", "_to": "49"}))

        safe_log(f"📡 [Footloose API] Iniciando escaneo multinivel sobre `{path_limpio}`...", "info")

        # 4. Ejecución del escaneo con fallback automático
        for api_endpoint, params in urls_a_probar:
            try:
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
                        
                        # Si obtuvimos resultados dentro del rango de precio, rompemos el ciclo
                        if len(productos_map) > 0:
                            break
            except Exception:
                continue

    except Exception as e:
        safe_log(f"🛑 [Footloose API] Error de ejecución: {e}", "error")

    productos_list = list(productos_map.values())
    if productos_list:
        safe_log(f"✅ [Footloose] ¡Éxito! Se indexaron {len(productos_list)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [Footloose] No se encontraron ofertas por debajo de S/. {limite:.2f}", "warning")

    return productos_list


def motor_mercado_libre(url, limite):
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urlparse, parse_qs, urljoin, unquote, quote
    import re
    import random
    import json

    productos_map = {}

    # =======================================================
    # 🎯 1. EXTRAER EL TÉRMINO DE BÚSQUEDA LIMPIO DE LA URL
    # =======================================================
    parsed_url = urlparse(url)
    path_segments = [s for s in parsed_url.path.split('/') if s]
    
    terms = []
    for seg in path_segments:
        # Separa la parte principal previa a los parámetros de ordenamiento (_OrderId_...)
        clean_seg = seg.split('_')[0]
        if clean_seg and not clean_seg.isdigit():
            terms.append(clean_seg.replace('-', ' '))
    
    query_text = " ".join(terms).strip()

    # =======================================================
    # 📡 2. CAPA 1: CONSULTA A API OFICIAL (MPE - PERÚ)
    # =======================================================
    if query_text:
        try:
            safe_log(f"📡 [Mercado Libre API] Consultando término: `{query_text}`...", "info")
            api_url = f"https://api.mercadolibre.com/sites/MPE/search?q={quote(query_text)}&sort=price_asc&limit=50"
            
            # Cabeceras limpias y estándar sin parámetros de origen que activen el 403
            api_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
                "Accept": "application/json"
            }
            
            resp_api = requests.get(api_url, headers=api_headers, timeout=12)
            if resp_api.status_code == 200:
                data_api = resp_api.json()
                results = data_api.get("results", [])
                
                if results:
                    safe_log(f"🔍 [Mercado Libre API] ¡Éxito! Se procesaron {len(results)} productos.", "info")
                    for item in results:
                        try:
                            nombre = item.get("title", "").strip().upper()
                            link_final = item.get("permalink", "").split('#')[0]
                            
                            p_o = float(item.get("price", 0.0))
                            p_r = float(item.get("original_price") or p_o)
                            
                            img_url = item.get("thumbnail", "")
                            if img_url:
                                img_url = img_url.replace("http://", "https://")
                                img_url = re.sub(r'-I\.jpg$', '-O.jpg', img_url)
                            
                            if 0 < p_o <= limite and link_final:
                                productos_map[link_final] = {
                                    "nombre": f"MERCADO LIBRE - {nombre}",
                                    "precio": p_o,
                                    "precio_regular": max(p_r, p_o),
                                    "link": link_final,
                                    "img": img_url
                                }
                        except Exception:
                            continue
            else:
                safe_log(f"⚠️ [Mercado Libre API] Respuesta HTTP {resp_api.status_code}. Pasando a respaldo HTML...", "warning")

        except Exception as e:
            safe_log(f"⚠️ [Mercado Libre API] Excepción en consulta API: {e}", "warning")

    # =======================================================
    # 🛡️ 3. CAPA 2: RESPALDO DE RASPADO HTML DIRECTO
    # =======================================================
    if not productos_map:
        try:
            safe_log("🛡️ [Mercado Libre HTML] Escaneando estructura de respaldo...", "info")
            html_headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "es-PE,es;q=0.9"
            }
            
            resp = requests.get(url, headers=html_headers, timeout=15, verify=False)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Búsqueda de elementos compatibles con el diseño actual
                tarjetas = soup.find_all(['li', 'div'], class_=re.compile(r'(ui-search-layout__item|poly-card|ui-search-result)', re.I))

                safe_log(f"🔍 [Mercado Libre HTML] Se detectaron {len(tarjetas)} elementos en el HTML.", "info")

                for t in tarjetas:
                    try:
                        a_el = t.find('a', href=True)
                        if not a_el: continue
                        link_final = a_el['href'].split('#')[0]
                        
                        tit_el = t.find(['h2', 'h3', 'span', 'a'], class_=re.compile(r'(title|poly-component__title|ui-search-item__title)', re.I))
                        nombre = tit_el.text.strip().upper() if tit_el else ""
                        if not nombre and a_el.has_attr('title'): 
                            nombre = a_el['title'].strip().upper()
                        
                        if not nombre or len(nombre) < 3: continue

                        textos_precios = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', t.text)
                        if not textos_precios: continue
                        
                        nums = sorted(list(set([limpiar_precio_pnp(p) for p in textos_precios if limpiar_precio_pnp(p) > 0])))
                        if not nums: continue
                        
                        p_o = nums[0]
                        p_r = nums[-1] if len(nums) > 1 else p_o

                        img_el = t.find('img')
                        img_url = ""
                        if img_el:
                            img_url = img_el.get('data-src') or img_el.get('src') or ""
                            
                        if img_url.startswith('//'): img_url = 'https:' + img_url

                        if 0 < p_o <= limite:
                            productos_map[link_final] = {
                                "nombre": f"MERCADO LIBRE - {nombre}",
                                "precio": p_o,
                                "precio_regular": max(p_r, p_o),
                                "link": link_final,
                                "img": img_url
                            }
                    except Exception:
                        continue

        except Exception as he:
            safe_log(f"🛑 [Mercado Libre HTML] Error durante el raspado HTML: {he}", "error")

    productos_list = list(productos_map.values())
    if productos_list:
        safe_log(f"✅ [Mercado Libre] ¡Éxito! Se indexaron {len(productos_list)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [Mercado Libre] No se encontraron ofertas por debajo de S/. {limite:.2f}", "warning")

    return productos_list







def motor_tradicional_general(url, limite, headers):
    productos = []
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
                                productos.append({"nombre": tit.text.strip().upper(), "precio": p_o, "precio_regular": p_r, "link": urljoin(url, a_el['href']), "img": img_el['src'] if img_el else ""})
                except Exception: continue
    except Exception: pass
    return productos

# =======================================================
# ENRUTADOR AISLADO
# =======================================================
def escanear_tienda(url, limite):
    headers = {"User-Agent": random.choice(LISTA_USER_AGENTS), "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8", "Accept-Language": "es-ES,es;q=0.9"}
    dominio = urlparse(url).netloc.lower()
    
    if "carsa.pe" in dominio: return motor_carsa(url, limite)
    elif "thn.pe" in dominio: return motor_thn(url, limite)
    elif any(k in dominio for k in ["tiendabelcorp", "cyzone", "lbel", "esika"]): return motor_belcorp(url, limite, headers)
    elif "efe.com.pe" in dominio or "lacuracao.pe" in dominio: return motor_conecta_retail(url, limite, headers, "EFE" if "efe.com.pe" in dominio else "CURACAO")
    elif "falabella.com" in dominio: return motor_falabella(url, limite, headers)
    elif "adidas" in dominio: return motor_adidas(url, limite)
    elif "platanitos.com" in dominio: return motor_platanitos(url, limite)
    elif "hiraoka.com.pe" in dominio: return motor_hiraoka(url, limite)
    elif "oechsle.pe" in dominio: return motor_oechsle(url, limite)
    elif "plazavea.com.pe" in dominio: return motor_plazavea(url, limite, headers=headers)
    elif "juntoz.com" in dominio: return motor_juntoz(url, limite, headers=headers)
    elif "triathlon.com.pe" in dominio: return motor_triathlon(url, limite, headers=headers)
    elif "ripley.com.pe" in dominio: return motor_ripley(url, limite, headers=headers)
    elif "footloose.pe" in dominio: return motor_footloose(url, limite)
    elif "mercadolibre" in dominio: return motor_mercado_libre(url, limite)
    else: return motor_tradicional_general(url, limite, headers)

# =======================================================
# SISTEMA DE PATRULLAJE CENTRAL
# =======================================================
def revisar_ofertas(filtro_objetivo="TODOS"):
    try: 
        res = supabase.table("radares").select("*").execute()
    except Exception as e: 
        safe_log(f"🛑 Error de conexión con Supabase (Tabla radares): {e}", "error")
        return f"Fallo Supabase: {e}"
        
    if not res or not res.data: return "Sin radares activos."
    
    total, alertas = 0, 0
    enviados = set()
    lista_html_streamlit = []
    zona_peru = timezone(timedelta(hours=-5))
    fecha_hoy = datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")
    target = str(filtro_objetivo).strip().upper()
    mapa_emojis = {
        "PERFUMES": "🧪", "ZAPATILLAS": "👟", "MEDIAS": "🧦", "POLOS": "👕", 
        "CASACAS": "🧥", "SHORTS": "🩳", "BUZOS": "👖", "AUDIFONOS": "🎧", 
        "TV": "📺", "PARLANTE": "🔊", "BARRA DE SONIDO": "🎵", "CELULAR": "📱", 
        "PC": "💻", "REFRIGERADORA": "❄️", "LAVADORA": "🧺", "ELECTRODOMESTICOS": "🔌", 
        "CAMA": "🛏️", "OTROS": "📦"
    }
    
    for item in res.data:
        ident = item['identificador'].upper()
        url_low = item['url'].lower()
        
        # Categorización del Radar
        if "SHORT" in ident or "short" in url_low: grupo = "SHORTS"
        elif "PERFUME" in ident or "perfume" in url_low: grupo = "PERFUMES"
        elif "ZAPATILLA" in ident or "zapatilla" in url_low or "calzado" in url_low: grupo = "ZAPATILLAS"
        elif "MEDIAS" in ident or "medias" in url_low: grupo = "MEDIAS"
        elif "POLO" in ident or "polo" in url_low: grupo = "POLOS"
        elif "CASACA" in ident or "casaca" in url_low or "polera" in url_low: grupo = "CASACAS"
        elif "BUZO" in ident or "buzo" in url_low or "pantalon" in url_low: grupo = "BUZOS"
        elif "AUDIFONO" in ident or "audifono" in url_low: grupo = "AUDIFONOS"
        elif "TV" in ident or "smart-tv" in url_low: grupo = "TV"
        elif "PARLANTE" in ident or "speaker" in url_low: grupo = "PARLANTE"
        elif "BARRA" in ident or "soundbar" in url_low: grupo = "BARRA DE SONIDO"
        elif "CELULAR" in ident or "phone" in url_low or "celular" in url_low: grupo = "CELULAR"
        elif "PC" in ident or "laptop" in url_low: grupo = "PC"
        elif "REFRIGERADORA" in ident or "refrig" in url_low: grupo = "REFRIGERADORA"
        elif "LAVADORA" in ident or "lavado" in url_low: grupo = "LAVADORA"
        elif "ELECTRO" in ident: grupo = "ELECTRODOMESTICOS"
        elif "CAMA" in ident or "colchon" in url_low: grupo = "CAMA"
        else: grupo = "OTROS"

        if target != "TODOS" and target != grupo: continue
            
        tienda_actual = ident.replace('_', '-').split('-')[0]
        safe_log(f"🔄 **Patrullando Tienda:** `{tienda_actual}` | Categoría: *{grupo}*...", "write")
        
        prods = escanear_tienda(item['url'], item['precio_max'])
        for p in prods:
            try:
                n_u = re.sub(r'\s+', ' ', p['nombre']).strip().upper()
                
                # Filtro de palabras prohibidas para categoría Audio/Hogar
                if grupo in ["BARRA DE SONIDO", "PARLANTE", "AUDIFONOS"]:
                    palabras_prohibidas = ["SABANA", "SÁBANA", "ALMOHADA", "COLCHON", "COLCHÓN", "EDREDON", "EDREDÓN", "CAMA", "FRAZADA", "MANTA"]
                    if any(bad in n_u for bad in palabras_prohibidas): continue
                
                if n_u in enviados: continue
                enviados.add(n_u)
                total += 1
                p_v = float(p['precio'])
                p_r = max(float(p.get('precio_regular', p_v)), p_v)
                p['tienda_origen'] = tienda_actual
                lista_html_streamlit.append(p)
                
                id_limpio = re.sub(r'[^A-Z0-9_]', '', n_u.replace(' ', '_'))
                id_registro = f"{item['identificador']}-{id_limpio}"[:200]
                
                # 1. Consultar si el producto ya existe en la Base de Datos
                precio_anterior = None
                try:
                    res_ant = supabase.table("historial_precios").select("precio").eq("identificador", id_registro).execute()
                    if res_ant.data and len(res_ant.data) > 0:
                        precio_anterior = float(res_ant.data[0]['precio'])
                except Exception as e_sel:
                    safe_log(f"⚠️ Error al consultar historial ({id_registro[:25]}...): {e_sel}", "caption")
                
                datos_guardar = {
                    "identificador": id_registro, 
                    "precio": p_v, 
                    "precio_regular": p_r, 
                    "link_producto": p['link'], 
                    "imagen_producto": p.get('img', ''), 
                    "fecha": fecha_hoy
                }
                
                emoji = mapa_emojis.get(grupo, "🔥")

                # =======================================================
                # ⚡ LÓGICA DE ALERTAS Y REGISTRO
                # =======================================================

                # CASO 1: ES UN PRODUCTO COMPLETAMENTE NUEVO
                if precio_anterior is None:
                    try:
                        supabase.table("historial_precios").insert(datos_guardar).execute()
                    except Exception as e_in:
                        safe_log(f"🛑 Error al registrar producto nuevo: {e_in}", "error")

                    msg_t = (
                        f"✨ <b>¡NUEVO PRODUCTO ENCONTRADO!</b> ✨\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📦 <b>Producto:</b> <code>{p['nombre']}</code>\n"
                        f"🏪 <b>Tienda:</b> <code>{tienda_actual}</code>\n"
                        f"💰 <b>Precio Encontrado:</b> S/. {p_v:.2f}\n"
                    )
                    if enviar_telegram_real(msg_t, p['link'], p.get('img', '')): 
                        alertas += 1
                        time.sleep(0.3)

                # CASO 2: EL PRODUCTO YA EXISTÍA Y BAJÓ DE PRECIO
                elif p_v < precio_anterior:
                    try:
                        supabase.table("historial_precios").update(datos_guardar).eq("identificador", id_registro).execute()
                    except Exception as e_up:
                        safe_log(f"🛑 Error al actualizar precio más bajo: {e_up}", "error")

                    ahorro = precio_anterior - p_v
                    msg_t = (
                        f"{emoji} <b>¡OFERTA: BAJÓ DE PRECIO!</b> {emoji}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📦 <b>Producto:</b> <code>{p['nombre']}</code>\n"
                        f"🏪 <b>Tienda:</b> <code>{tienda_actual}</code>\n"
                        f"❌ <b>Precio Anterior:</b> S/. {precio_anterior:.2f}\n"
                        f"💰 <b>Nuevo Precio Oferta:</b> S/. {p_v:.2f}\n"
                        f"📉 <b>Te Ahorras:</b> S/. {ahorro:.2f}\n"
                    )
                    if enviar_telegram_real(msg_t, p['link'], p.get('img', '')): 
                        alertas += 1
                        time.sleep(0.3)

                # CASO 3: EL PRECIO SUBIÓ O SE MANTUVO IGUAL
                else:
                    pass

            except Exception as e_p:
                safe_log(f"⚠️ Error al procesar ítem en patrulla: {e_p}", "caption")
                
    if len(lista_html_streamlit) > 0:
        try:
            safe_log("---", "write")
            safe_log(f"### 🎯 Modelos encontrados e indexados en vivo ({len(lista_html_streamlit)}):", "write")
            for prod in lista_html_streamlit:
                with st.container(border=True):
                    col1, col2 = st.columns([2, 8])
                    with col1:
                        if prod.get('img') and len(prod['img']) > 5: st.image(prod['img'], width=120)
                        else: st.write("📷 _Sin Foto_")
                    with col2:
                        st.markdown(f"#### `{prod['nombre']}`")
                        st.markdown(f"🏪 **Tienda de Origen:** `{prod['tienda_origen']}`")
                        p_oferta = prod['precio']
                        p_regular = prod.get('precio_regular', p_oferta)
                        if p_regular > p_oferta:
                            ahorro_soles = p_regular - p_oferta
                            porcentaje = (ahorro_soles / p_regular) * 100
                            st.markdown(f"❌ ~~Precio Regular: S/. {p_regular:.2f}~~")
                            st.markdown(f"💰 **Precio Oferta: S/. {prod['precio']:.2f}**")
                            st.markdown(f"🔥 **¡Ahorraste S/. {ahorro_soles:.2f}! ({porcentaje:.0f}% de Descuento)**")
                        else:
                            st.markdown(f"💰 **Precio Actual: S/. {prod['precio']:.2f}**")
                        st.markdown(f"🔗 [🌐 IR A COMPRAR DIRECTO]({prod['link']})")
        except Exception: pass
            
    return f"Éxito. Modelos procesados: {total}. Alertas Telegram: {alertas}."
