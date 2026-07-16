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
    """Motor aislado exclusivo para THN.pe (The Athlete's Foot)"""
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
        
        # Buscar contenedores de productos genéricos
        tarjetas = soup.find_all(['div', 'article', 'li'], class_=re.compile(r'(product-summary|product-card|item-card|vtex-product|grid-item)', re.I))
        
        for t in tarjetas:
            try:
                # 1. Enlace
                a_el = t.find('a', href=True)
                if not a_el: continue
                link_final = urljoin("https://www.thn.pe", a_el['href'])
                
                # 2. Nombre
                tit_el = t.find(['h2', 'h3', 'span', 'div'], class_=re.compile(r'(name|title|brand|description)', re.I))
                nombre = tit_el.text.strip().upper() if tit_el else ""
                if not nombre: nombre = a_el.text.strip().upper()
                if len(nombre) < 4: continue
                
                # 3. Precios (Regex difuso sobre el contenedor)
                textos_precios = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', t.text)
                if not textos_precios: continue
                
                nums = sorted(list(set([limpiar_precio_pnp(p) for p in textos_precios if limpiar_precio_pnp(p) > 0])))
                if not nums: continue
                
                p_o = nums[0]
                p_r = nums[-1] if len(nums) > 1 else p_o
                
                if 0 < p_o <= limite:
                    # 4. Imagen
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
    """(Motor estacionado temporalmente)"""
    return []

def motor_jbl(url, limite, headers):
    """Motor JBL Original: Tu lógica nativa con restauración de headers y evasión de redireccionamientos"""
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    
    productos = []
    url_low = url.lower()
    
    # 🕵️‍♂️ MAPEADO DE KEYWORDS QUE EVITAN REDIRECCIONES (Y EVITAN EL 403 DE DATADOME)
    # 'barra' y 'wireless' provocan redirecciones 302 hacia páginas protegidas.
    # Usamos sinónimos directos de búsqueda que devuelven el catálogo limpio en 200 OK.
    if "barra" in url_low:
        keyword = "cinema"       # Trae la línea "JBL Cinema" (SB180, SB140, etc.) sin redirección
    elif "wireless" in url_low or "audifono" in url_low:
        keyword = "auriculares"  # Trae todos los audífonos y auriculares sin redirección
    elif "parlante" in url_low:
        keyword = "parlante"     # Este funciona directo en tu código original
    else:
        keyword = "jbl"          # Consulta genérica de respaldo
        
    api_url = "https://www.jbl.com.pe/on/demandware.store/Sites-JB-PE-Site/es_PE/Search-UpdateGrid"
    params = {"q": keyword, "srule": "price-low-to-high", "sz": "24"}
    
    try:
        safe_log(f"📡 [JBL API] Accediendo con tus headers de bucle y keyword optimizada: '{keyword}'...", "info")
        
        # ⚡ CLAVE: Usamos tus headers originales y bloqueamos redirecciones sospechosas
        resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False, allow_redirects=False)
        
        # Si detectamos un intento de redirección (301, 302), aplicamos un fallback seguro
        if resp.status_code in [301, 302]:
            safe_log(f"⚠️ [JBL API] La palabra '{keyword}' intentó redireccionar. Usando fallback seguro 'jbl'...", "warning")
            params["q"] = "jbl"
            resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False, allow_redirects=False)
        
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = soup.select('.product-tile') or soup.select('[class*="product-item"]')
            
            safe_log(f"🔍 [JBL API] Catálogo leído con éxito. Procesando {len(items)} productos para '{keyword}'...", "info")
            vistos_links = set()
            
            for t in items:
                try:
                    tit_el = t.select_one('.pdp-link a') or t.select_one('.product-name')
                    if not tit_el: continue
                    nombre_prod = tit_el.text.strip().upper()
                    
                    reg_el = t.select_one('.price .list .value') or t.select_one('del')
                    precio_el = t.select_one('.price .sales .value') or t.select_one('.sales')
                    
                    txt_oferta = precio_el.text if precio_el else t.text
                    precio_oferta = limpiar_precio_pnp(txt_oferta)
                    if not precio_oferta: continue
                    
                    # Tu corrección de decimales nativa original
                    if 0 < precio_oferta < 10.0 and any(k in nombre_prod for k in ["BARRA", "TV", "PARLANTE", "CINEMA", "SOUNDBAR"]):
                        precio_oferta = precio_oferta * 1000
                        
                    precio_regular = precio_oferta
                    if reg_el:
                        precio_regular = limpiar_precio_pnp(reg_el.text)
                        if 0 < precio_regular < 10.0 and any(k in nombre_prod for k in ["BARRA", "TV", "PARLANTE", "CINEMA", "SOUNDBAR"]):
                            precio_regular = precio_regular * 1000
                    
                    # Filtro de presupuesto
                    if 0 < precio_oferta <= limite:
                        link_el = t.find('a', href=True)
                        enlace_final = urljoin(url, link_el['href']) if link_el else url
                        
                        if enlace_final in vistos_links: continue
                        vistos_links.add(enlace_final)
                        
                        img_el = t.find('img')
                        img_final = ""
                        if img_el:
                            img_final = img_el.get('data-src') or img_el.get('src') or ''
                            if img_final.startswith('//'): img_final = 'https:' + img_final
                            
                        productos.append({
                            "nombre": f"JBL - {nombre_prod}", 
                            "precio": precio_oferta, 
                            "precio_regular": precio_regular, 
                            "link": enlace_final, 
                            "img": img_final
                        })
                except Exception: 
                    continue
        else:
            safe_log(f"🛑 [JBL API] Acceso denegado en puerto trasero. Código HTTP: {resp.status_code}", "error")
            
    except Exception as e:
        safe_log(f"🛑 [JBL API] Error inesperado en el módulo: {e}", "error")
        
    # Reporte de control final en Streamlit
    if productos:
        safe_log(f"✅ [JBL API] ¡Éxito! Se indexaron {len(productos)} ofertas bajo el límite de S/. {limite:.2f}", "success")
    else:
        safe_log(f"⚠️ [JBL API] Catálogo procesado, pero ninguna oferta baja de S/. {limite:.2f}", "warning")
        
    return productos


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
    """Motor HIRAOKA Definitivo: Extractor especializado para Magento 2 (Infracommerce)"""
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
        
        # Selectores nativos para la arquitectura de cajas de Hiraoka (Magento 2)
        tarjetas = soup.select('.product-item') or soup.select('.product-item-info') or soup.select('.item.product')
        
        for t in tarjetas:
            try:
                # 1. Extraer Nombre y Enlace de la Ficha
                tit_el = t.select_one('.product-item-link') or t.select_one('.product-item-name a') or t.select_one('.product-name a')
                if not tit_el: continue
                nombre = tit_el.text.strip().upper()
                link_final = urljoin("https://hiraoka.com.pe", tit_el['href'])
                
                # 2. Extraer Precios de las etiquetas de Infracommerce
                o_el = t.select_one('[data-price-type="finalPrice"] .price') or t.select_one('.special-price .price') or t.select_one('.price-box .price')
                r_el = t.select_one('[data-price-type="oldPrice"] .price') or t.select_one('.old-price .price')
                
                if not o_el:
                    # Respaldo difuso por texto si cambian el diseño de precios
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
                
                # 3. Filtrar por límite e indexar la imagen real del producto
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
    """Motor CARSA de Alta Fidelidad: Emulación de navegador real"""
    productos = []
    
    # Cabeceras que engañan al servidor haciéndole creer que somos un navegador Chrome real
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
        
        # SI ESTO NO SALE, EL SERVIDOR NOS ESTÁ CORTANDO EL ACCESO
        safe_log(f"📡 [Diag CARSA] Código de respuesta: {resp.status_code} | Tamaño: {len(resp.text)}", "info")
        
        if resp.status_code != 200:
            safe_log(f"🛑 [Diag CARSA] Bloqueo total por Firewall/Anti-Bot. Código {resp.status_code}", "error")
            return []

        # Si llegamos aquí, sí descargamos contenido. Ahora busquemos productos.
        # Buscamos en el texto del HTML cualquier rastro de JSON de precios
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
    """Motor OECHSLE Híbrido V3: Preservación de Query String nativa para evitar Bloqueos de Codificación (Error 400)"""
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
        
        # 💡 SOLUCIÓN AL RADAR DE SONIDO: Mapeamos 'query=' a 'ft=' directamente para la API de VTEX
        if 'query=' in raw_query:
            raw_query = raw_query.replace('query=', 'ft=')
        
        # 💡 SOLUCIÓN AL ERROR 400 DE TELEVISORES:
        # VTEX rechaza parámetros codificados con '+' para espacios, exige estrictamente '%20'.
        # Al usar la query string nativa del navegador directamente, evitamos que python re-codifique el enlace.
        has_category_filter = 'fq=C:' in raw_query or 'fq=C%3A' in raw_query
        
        if has_category_filter:
            api_url = f"https://www.oechsle.pe/api/catalog_system/pub/products/search?{raw_query}"
        else:
            category_path = parsed_url.path.rstrip('/')
            if category_path and not category_path.startswith('/'):
                category_path = '/' + category_path
            api_url = f"https://www.oechsle.pe/api/catalog_system/pub/products/search{category_path}?{raw_query}"
            
        # Agregamos la paginación estándar al final de la URL preservando la codificación nativa
        if '_from=' not in api_url:
            api_url += "&_from=0&_to=49"
            
        safe_log("📡 [Oechsle] Conectando con la base de datos oficial...", "info")
        resp = requests.get(api_url, headers=headers, timeout=15, verify=False)
        
        # Si la API responde exitosamente (200 o 206)
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
        
    # 🛡️ CAPA DE RESPALDO (Si la API falla por cualquier motivo, extrae directamente del HTML)
    if not productos:
        safe_log("🛡️ [Oechsle] Activando plan de contingencia HTML...", "info")
        try:
            html_headers = headers.copy()
            html_headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            resp = requests.get(url, headers=html_headers, timeout=15, verify=False)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Buscamos metadatos JSON-LD
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
    
    # Ruteo seguro y aislado por tienda
    if "carsa.pe" in dominio: return motor_carsa(url, limite) # <--- LA NUEVA LÍNEA AÑADIDA
    elif "thn.pe" in dominio: return motor_thn(url, limite)
    elif any(k in dominio for k in ["tiendabelcorp", "cyzone", "lbel", "esika"]): return motor_belcorp(url, limite, headers)
    elif "efe.com.pe" in dominio or "lacuracao.pe" in dominio: return motor_conecta_retail(url, limite, headers, "EFE" if "efe.com.pe" in dominio else "CURACAO")
    elif "falabella.com" in dominio: return motor_falabella(url, limite, headers)
    elif "adidas" in dominio: return motor_adidas(url, limite)
    elif "jbl" in dominio: return motor_jbl(url, limite, headers=headers)
    elif "platanitos.com" in dominio: return motor_platanitos(url, limite)
    elif "hiraoka.com.pe" in dominio: return motor_hiraoka(url, limite)
    elif "oechsle.pe" in dominio: return motor_oechsle(url, limite)
    
    else: return motor_tradicional_general(url, limite, headers)

# =======================================================
# SISTEMA DE PATRULLAJE CENTRAL (CON SISTEMA ANTI-SPAM)
# =======================================================
def revisar_ofertas(filtro_objetivo="TODOS"):
    try: res = supabase.table("radares").select("*").execute()
    except Exception as e: return f"Fallo Supabase: {e}"
    if not res or not res.data: return "Sin radares."
    
    total, alertas = 0, 0
    enviados = set()
    lista_html_streamlit = []
    zona_peru = timezone(timedelta(hours=-5))
    fecha_hoy = datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")
    target = str(filtro_objetivo).strip().upper()
    mapa_emojis = {"PERFUMES": "🧪", "ZAPATILLAS": "👟", "MEDIAS": "🧦", "POLOS": "👕", "CASACAS": "🧥", "SHORTS": "🩳", "BUZOS": "👖", "AUDIFONOS": "🎧", "TV": "📺", "PARLANTE": "🔊", "BARRA DE SONIDO": "🎵", "CELULAR": "📱", "PC": "💻", "REFRIGERADORA": "❄️", "LAVADORA": "🧺", "ELECTRODOMESTICOS": "🔌", "CAMA": "🛏️", "OTROS": "📦"}
    
    for item in res.data:
        ident = item['identificador'].upper()
        url_low = item['url'].lower()
        
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
                
                if grupo in ["BARRA DE SONIDO", "PARLANTE", "AUDIFONOS"]:
                    palabras_prohibidas = ["SABANA", "SÁBANA", "ALMOHADA", "COLCHON", "COLCHÓN", "EDREDON", "EDREDÓN", "CAMA", "FRAZADA", "MANTA", "SABANAS", "ALMOHADAS"]
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
                precio_anterior = None
                registro_existe = False
                
                try:
                    res_ant = supabase.table("historial_precios").select("precio").eq("identificador", id_registro).execute()
                    if res_ant.data and len(res_ant.data) > 0:
                        precio_anterior = float(res_ant.data[0]['precio'])
                        registro_existe = True
                except Exception: pass
                
                datos_guardar = {"identificador": id_registro, "precio": p_v, "precio_regular": p_r, "link_producto": p['link'], "imagen_producto": p.get('img', ''), "fecha": fecha_hoy}
                try:
                    if registro_existe: supabase.table("historial_precios").update(datos_guardar).eq("identificador", id_registro).execute()
                    else: supabase.table("historial_precios").insert(datos_guardar).execute()
                except Exception: pass
                
                debe_alertar = False
                if precio_anterior is not None:
                    if p_v < precio_anterior: debe_alertar = True
                else:
                    debe_alertar = False
                
                if debe_alertar:
                    emoji = mapa_emojis.get(grupo, "🔥")
                    msg_t = f"{emoji} <b>¡PRECIO BAJÓ EN VIVO!</b> {emoji}\n━━━━━━━━━━━━━━━━━━━━━\n\n📦 <b>Producto:</b> <code>{p['nombre']}</code>\n🏪 <b>Tienda:</b> <code>{tienda_actual}</code>\n❌ <b>Precio de Lista Anterior:</b> S/. {precio_anterior:.2f}\n💰 <b>Precio de Oferta Nuevo:</b> S/. {p_v:.2f}\n📉 <b>Ahorraste respecto a ayer:</b> S/. {(precio_anterior - p_v):.2f}\n"
                    if enviar_telegram_real(msg_t, p['link'], p.get('img', '')): alertas += 1
            except Exception: pass
                
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
