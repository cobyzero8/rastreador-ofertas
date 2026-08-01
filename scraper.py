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
    import time
    import json
    import requests
    import re
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin
    from datetime import datetime, timezone, timedelta

    # Función helper interna para sanitizar precios de Adidas
    def limpiar_precio_adidas(texto):
        if not texto:
            return 0.0
        texto = str(texto)
        # 1. Eliminar cualquier etiqueta o texto de porcentaje/descuento (ej. "-30%", "30%")
        texto = re.sub(r'-?\s*\d+\s*%', '', texto)
        # 2. Si vienen palabras como "Precio original", limpiarlas
        texto = re.sub(r'[^\d.,]', ' ', texto)
        # 3. Extraer el primer bloque de números (el precio real)
        match = re.search(r'\d+(?:[.,]\d+)?', texto)
        if match:
            num_str = match.group(0).replace(',', '.')
            try:
                return float(num_str)
            except ValueError:
                return 0.0
        return 0.0

    # =======================================================
    # ⏱️ CONTROL DE FRECUENCIA (MÁXIMO 1 VEZ CADA 2 HORAS)
    # =======================================================
    try:
        res_check = supabase.table("historial_precios")\
            .select("fecha")\
            .like("identificador", "ADIDAS%")\
            .order("fecha", descending=True)\
            .limit(1)\
            .execute()

        if res_check.data and len(res_check.data) > 0:
            ultima_fecha_str = res_check.data[0]['fecha']
            ultima_fecha = datetime.fromisoformat(ultima_fecha_str.replace('Z', '+00:00'))
            ahora = datetime.now(timezone.utc)
            minutos_transcurridos = (ahora - ultima_fecha).total_seconds() / 60

            if minutos_transcurridos < 110:
                safe_log(f"⏳ [Adidas] Escaneado hace {int(minutos_transcurridos)} min. Se omite esta ronda para ahorrar créditos de ScraperAPI.", "caption")
                return []
    except Exception as e:
        safe_log(f"⚠️ No se pudo verificar el temporizador de Adidas: {e}", "caption")

    productos_map = {}
    texto_html = ""
    status_code = 0

    safe_log("🚀 [Adidas] Solicitando página a través de ScraperAPI (Proxy Residencial)...", "info")

    api_key = "4cd72a5cadb77297cd9f41f11dc632c0"
    try:
        if "SCRAPERAPI_KEY" in st.secrets:
            api_key = st.secrets["SCRAPERAPI_KEY"]
    except Exception:
        pass

    payload = {
        'api_key': api_key,
        'url': url
    }

    try:
        resp = requests.get('https://api.scraperapi.com/', params=payload, timeout=40)
        status_code = resp.status_code
        texto_html = resp.text
    except Exception as e:
        safe_log(f"🚨 [Adidas] Error al conectar con ScraperAPI: {e}", "warning")
        return []

    if status_code != 200 or len(texto_html) <= 5000:
        safe_log(f"🚨 [Adidas] ScraperAPI devolvió estado HTTP {status_code}.", "warning")
        return []

    texto_html = texto_html.replace('\xa0', ' ').replace('&nbsp;', ' ')
    soup = BeautifulSoup(texto_html, 'html.parser')

    # Estrategia 1: Extracción JSON desde __NEXT_DATA__
    next_script = soup.find('script', id='__NEXT_DATA__')
    if next_script:
        try:
            json_data = json.loads(next_script.text)

            def buscar_productos_next(nodo):
                if isinstance(nodo, dict):
                    for k in ['products', 'results', 'items', 'itemListElement']:
                        if k in nodo and isinstance(nodo[k], list) and len(nodo[k]) > 0:
                            if isinstance(nodo[k][0], dict) and any(key in nodo[k][0] for key in ['title', 'name', 'displayName']):
                                return nodo[k]
                    for v in nodo.values():
                        res = buscar_productos_next(v)
                        if res: return res
                elif isinstance(nodo, list):
                    for x in nodo:
                        res = buscar_productos_next(x)
                        if res: return res
                return []

            items_json = buscar_productos_next(json_data)
            if items_json:
                for prod_j in items_json:
                    try:
                        nombre = str(prod_j.get('name') or prod_j.get('title') or prod_j.get('displayName') or "").strip().upper()
                        if len(nombre) < 3: continue

                        # Usar limpiador específico para Adidas
                        p_o = limpiar_precio_adidas(prod_j.get('salePrice') or prod_j.get('price'))
                        p_r = limpiar_precio_adidas(prod_j.get('originalPrice') or prod_j.get('price'))
                        if p_r == 0: p_r = p_o

                        if 0 < p_o <= limite:
                            link_rel = prod_j.get('url') or prod_j.get('link') or prod_j.get('href') or ""
                            link_final = urljoin("https://www.adidas.pe", link_rel) if link_rel else url
                            img_url = str(prod_j.get('image', ''))

                            productos_map[link_final] = {
                                "nombre": f"ADIDAS - {nombre}",
                                "precio": p_o,
                                "precio_regular": max(p_r, p_o),
                                "link": link_final,
                                "img": img_url
                            }
                    except Exception:
                        continue
        except Exception:
            pass

    # Estrategia 2: Fallback por selectores HTML
    if not productos_map:
        titulos_testid = soup.find_all(attrs={"data-testid": "product-card-title"})
        for tit_el in titulos_testid:
            try:
                nombre_prod = tit_el.text.strip().upper()
                ancestor = tit_el

                oferta_el, regular_el, enlace_el, img_el = None, None, None, None
                for _ in range(5):
                    ancestor = ancestor.parent
                    if not ancestor: break
                    if not oferta_el: oferta_el = ancestor.find(attrs={"data-testid": "main-price"})
                    if not regular_el: regular_el = ancestor.find(attrs={"data-testid": "original-price"})
                    if not enlace_el: enlace_el = ancestor.find('a', href=True)
                    if not img_el: img_el = ancestor.find('img')

                if oferta_el:
                    # Limpieza estricta descartando etiquetas de porcentaje
                    precio_oferta = limpiar_precio_adidas(oferta_el.text)
                    precio_regular = limpiar_precio_adidas(regular_el.text) if regular_el else precio_oferta

                    if 0 < precio_oferta <= limite:
                        link_final = urljoin("https://www.adidas.pe", enlace_el['href']) if enlace_el else url
                        img_url = img_el.get('src', '') if img_el else ''

                        productos_map[link_final] = {
                            "nombre": f"ADIDAS - {nombre_prod}",
                            "precio": precio_oferta,
                            "precio_regular": max(precio_regular, precio_oferta),
                            "link": link_final,
                            "img": img_url
                        }
            except Exception:
                continue

    productos_list = list(productos_map.values())
    if productos_list:
        safe_log(f"✅ [Adidas] ¡Éxito vía ScraperAPI! Se indexaron {len(productos_list)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [Adidas] No se encontraron ofertas por debajo de S/. {limite:.2f}", "warning")

    return productos_list





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


def motor_estilos(url, limite):
    import requests
    from bs4 import BeautifulSoup
    from urllib.parse import urlparse, parse_qs, urljoin, unquote
    import re
    import random
    import json

    productos_map = {}
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
        
        # Descartar tallas o segmentos numéricos incompatibles
        segmentos = [s for s in raw_path.split('/') if s and not re.match(r'^\d+[\-_.]\d+$', s)]
        path_limpio = '/' + '/'.join(segmentos) if segmentos else "/poleras-hombre"
        path_base = '/' + '/'.join(segmentos[-2:]) if len(segmentos) >= 2 else path_limpio

        # Estrategia de peticiones secuenciales para VTEX Estilos
        urls_a_probar = []

        # 1. Búsqueda por término explícito (_q o ft)
        q_term = query_params.get('_q', query_params.get('ft', [None]))[0]
        if q_term:
            urls_a_probar.append((
                "https://www.estilos.com.pe/api/catalog_system/pub/products/search",
                {"ft": q_term, "O": "OrderByPriceASC", "_from": "0", "_to": "49"}
            ))

        # 2. Búsqueda por categoría / marcas (/puma/quiksilver/m/poleras hombre)
        urls_a_probar.append((
            f"https://www.estilos.com.pe/api/catalog_system/pub/products/search{path_limpio}",
            {"O": "OrderByPriceASC", "_from": "0", "_to": "49"}
        ))
        
        # 3. Búsqueda por ruta base reducida
        if path_base != path_limpio:
            urls_a_probar.append((
                f"https://www.estilos.com.pe/api/catalog_system/pub/products/search{path_base}",
                {"O": "OrderByPriceASC", "_from": "0", "_to": "49"}
            ))

        safe_log(f"📡 [Estilos API] Consultando catálogo VTEX de Estilos...", "info")

        for api_endpoint, params in urls_a_probar:
            try:
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
                        
                        if len(productos_map) > 0:
                            break
            except Exception:
                continue

    except Exception as e:
        safe_log(f"⚠️ [Estilos API] Error de consulta: {e}", "warning")

    # Respaldo HTML por JSON-LD en caso de contingencia
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


def motor_promart(url, limite, headers=None):
    import requests
    import re
    from urllib.parse import urlparse, urljoin, unquote

    productos_map = {}
    
    if not headers:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.promart.pe/"
        }

    try:
        parsed_url = urlparse(url)
        
        # 1. Construcción dinámica según la categoría de la URL enviada
        path = parsed_url.path.rstrip('/')
        api_base_url = f"https://www.promart.pe/api/catalog_system/pub/products/search{path}"

        # 2. Armado manual del Query String sin romper los filtros VTEX
        query_parts = []
        if parsed_url.query:
            for pair in parsed_url.query.split('&'):
                # Elimina filtros redundantes de categoría que causan el HTTP 400
                if pair.startswith('fq=C:') or pair.startswith('fq=C%3A'):
                    continue
                if pair.startswith('_from=') or pair.startswith('_to='):
                    continue
                query_parts.append(pair)
        
        if not any(p.startswith('O=') for p in query_parts):
            query_parts.append("O=OrderByPriceASC")
        query_parts.append("_from=0")
        query_parts.append("_to=49")

        final_query_string = "&".join(query_parts)
        final_api_url = f"{api_base_url}?{final_query_string}"

        safe_log("📡 [Promart API] Consultando catálogo VTEX...", "info")
        resp = requests.get(final_api_url, headers=headers, timeout=15, verify=False)

        if resp.status_code in [200, 206]:
            data = resp.json()
            safe_log(f"🔍 [Promart API] Catálogo recibido ({len(data)} ítems). Procesando...", "info")

            url_decodificada = unquote(url).lower()
            
            # 3. FILTRO ESPECÍFICO DE TV: Solo se activa si la URL pide explícitamente el rango 50-59
            exigir_50_59_tv = "50-59" in url_decodificada and ("televisor" in path or "tv" in path)

            for p in data:
                try:
                    nombre_prod = p.get("productName", "").strip().upper()
                    
                    # Validación estricta de pulgadas SOLO si es búsqueda de TVs 50-59"
                    if exigir_50_59_tv:
                        match_pulgadas = re.search(r'(\d{2})\s*(?:"|”|’|PULGADAS|PULGADA|P\b)', nombre_prod)
                        if match_pulgadas:
                            pulgadas = int(match_pulgadas.group(1))
                            if not (50 <= pulgadas <= 59):
                                continue
                        elif not any(k in nombre_prod for k in ["50-59", "50", "55", "58"]):
                            continue

                    link_rel = p.get("link", "")
                    link_final = urljoin("https://www.promart.pe", link_rel) if link_rel else url

                    items = p.get("items", [])
                    if not items: continue

                    first_item = items[0]
                    images = first_item.get("images", [])
                    img_final = images[0].get("imageUrl", "") if images else ""
                    if img_final.startswith('//'): img_final = 'https:' + img_final

                    sellers = first_item.get("sellers", [])
                    if not sellers: continue

                    offer = sellers[0].get("commertialOffer", {})
                    
                    if offer.get("AvailableQuantity", 0) <= 0: 
                        continue

                    p_o = float(offer.get("Price", 0.0))
                    p_r = float(offer.get("ListPrice", p_o))
                    
                    # Detección de Tarjeta oh!
                    p_tarjeta = None
                    installment_options = offer.get("PaymentOptions", {}).get("installmentOptions", [])
                    
                    for option in installment_options:
                        p_name = f"{option.get('paymentSystemName', '')} {option.get('paymentName', '')}".lower()
                        if "oh" in p_name:
                            installments = option.get("installments", [])
                            if installments:
                                total_val = float(installments[0].get("total", 0))
                                val = total_val / 100.0 if total_val > 10000 else float(installments[0].get("value", 0))
                                if 0 < val < p_o:
                                    p_tarjeta = val
                                    break

                    precio_minimo = p_tarjeta if p_tarjeta else p_o

                    if 0 < precio_minimo <= limite:
                        productos_map[link_final] = {
                            "nombre": f"PROMART - {nombre_prod}",
                            "precio": p_o,
                            "precio_tarjeta": p_tarjeta,
                            "precio_regular": max(p_r, p_o),
                            "link": link_final,
                            "img": img_final
                        }
                except Exception:
                    continue
        else:
            safe_log(f"🛑 [Promart API] Código HTTP: {resp.status_code}", "error")

    except Exception as e:
        safe_log(f"🛑 [Promart API] Error crítico: {e}", "error")

    productos_list = list(productos_map.values())
    if productos_list:
        safe_log(f"✅ [Promart] ¡Éxito! Se indexaron {len(productos_list)} ofertas válidas.", "success")
    else:
        safe_log(f"⚠️ [Promart] No hay productos que cumplan el filtro por debajo de S/. {limite:.2f}", "warning")

    return productos_list


def motor_coolbox(url, limite, headers=None):
    import requests
    import re
    from urllib.parse import urlparse, parse_qs, urljoin, unquote

    productos_map = {}
    
    if not headers:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.coolbox.pe/"
        }

    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        path = parsed_url.path.rstrip('/')

        # 1. DETECCIÓN DE CLUSTERS Y COLECCIONES (Ej. initialQuery=1539)
        initial_map = query_params.get("initialMap", [""])[0]
        initial_query = query_params.get("initialQuery", [""])[0]

        query_parts = []

        if initial_map == "productClusterIds" and initial_query:
            # Si es un cluster/colección dinámico, usamos la API base sin la ruta /todo-tv
            api_base_url = "https://www.coolbox.pe/api/catalog_system/pub/products/search"
            query_parts.append(f"fq=productClusterIds:{initial_query}")
        else:
            # Si es una categoría normal, mantenemos la ruta
            api_base_url = f"https://www.coolbox.pe/api/catalog_system/pub/products/search{path}"

        # 2. LIMPIEZA Y TRADUCCIÓN DE PARÁMETROS
        params_ignorar = ['initialmap', 'initialquery', 'map', 'query', 'searchstate', '_from', '_to']
        
        if parsed_url.query:
            for pair in parsed_url.query.split('&'):
                if not pair or '=' not in pair:
                    continue
                
                key, val = pair.split('=', 1)
                key_lower = key.lower()
                
                if key_lower in params_ignorar:
                    continue
                
                if key_lower in ['order', 'orderby']:
                    query_parts.append(f"O={val}")
                else:
                    query_parts.append(pair)
        
        # Paginación y ordenamiento por menor precio
        if not any(p.startswith('O=') for p in query_parts):
            query_parts.append("O=OrderByPriceASC")
        query_parts.append("_from=0")
        query_parts.append("_to=49")

        final_query_string = "&".join(query_parts)
        final_api_url = f"{api_base_url}?{final_query_string}"

        safe_log("📡 [Coolbox API] Consultando catálogo VTEX...", "info")
        resp = requests.get(final_api_url, headers=headers, timeout=15, verify=False)

        if resp.status_code in [200, 206]:
            data = resp.json()
            safe_log(f"🔍 [Coolbox API] Catálogo recibido ({len(data)} ítems). Procesando...", "info")

            url_decodificada = unquote(url).lower()
            exigir_50_59_tv = "50-59" in url_decodificada and ("tv" in path or "televisor" in path or "todo-tv" in path)

            for p in data:
                try:
                    nombre_prod = p.get("productName", "").strip().upper()
                    
                    # Filtro inteligente de pulgadas si se trata de televisores
                    if exigir_50_59_tv:
                        match_pulgadas = re.search(r'(\d{2})\s*(?:"|”|’|PULGADAS|PULGADA|P\b)', nombre_prod)
                        if match_pulgadas:
                            pulgadas = int(match_pulgadas.group(1))
                            if not (50 <= pulgadas <= 59):
                                continue
                        elif not any(k in nombre_prod for k in ["50-59", "50", "55", "58"]):
                            continue

                    link_rel = p.get("link", "")
                    link_final = urljoin("https://www.coolbox.pe", link_rel) if link_rel else url

                    items = p.get("items", [])
                    if not items: 
                        continue

                    first_item = items[0]
                    images = first_item.get("images", [])
                    img_final = images[0].get("imageUrl", "") if images else ""
                    if img_final.startswith('//'): 
                        img_final = 'https:' + img_final

                    sellers = first_item.get("sellers", [])
                    if not sellers: 
                        continue

                    offer = sellers[0].get("commertialOffer", {})
                    
                    if offer.get("AvailableQuantity", 0) <= 0: 
                        continue

                    p_o = float(offer.get("Price", 0.0))          # Precio Web / Oferta
                    p_r = float(offer.get("ListPrice", p_o))      # Precio Lista tachado
                    
                    # Detección de Precio Exclusivo con Tarjetas asociadas
                    p_tarjeta = None
                    installment_options = offer.get("PaymentOptions", {}).get("installmentOptions", [])
                    
                    for option in installment_options:
                        p_name = f"{option.get('paymentSystemName', '')} {option.get('paymentName', '')}".lower()
                        if any(t in p_name for t in ["oh", "bcp", "cmr", "diners", "tarjeta", "bbva"]):
                            installments = option.get("installments", [])
                            if installments:
                                total_val = float(installments[0].get("total", 0))
                                val = total_val / 100.0 if total_val > 10000 else float(installments[0].get("value", 0))
                                if 0 < val < p_o:
                                    p_tarjeta = val
                                    break

                    precio_minimo = p_tarjeta if p_tarjeta else p_o

                    if 0 < precio_minimo <= limite:
                        productos_map[link_final] = {
                            "nombre": f"COOLBOX - {nombre_prod}",
                            "precio": p_o,
                            "precio_tarjeta": p_tarjeta,
                            "precio_regular": max(p_r, p_o),
                            "link": link_final,
                            "img": img_final
                        }
                except Exception:
                    continue
        else:
            safe_log(f"🛑 [Coolbox API] Código HTTP: {resp.status_code}", "error")

    except Exception as e:
        safe_log(f"🛑 [Coolbox API] Error crítico: {e}", "error")

    productos_list = list(productos_map.values())
    if productos_list:
        safe_log(f"✅ [Coolbox] ¡Éxito! Se indexaron {len(productos_list)} ofertas válidas.", "success")
    else:
        safe_log(f"⚠️ [Coolbox] No hay productos que cumplan el filtro por debajo de S/. {limite:.2f}", "warning")

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


def motor_nike(url, limite=9999, max_pages=10, use_playwright_fallback=False, session=None, step=12, sz=None, max_items=500):
    import os, time, re, random, json, requests
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, urljoin
    from bs4 import BeautifulSoup
    from datetime import datetime, timezone

    logs_ejecucion = []

    def _safe_log(msg, level="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level.upper()}] {msg}"
        logs_ejecucion.append(log_entry)
        try:
            if 'safe_log' in globals():
                safe_log(msg, level)
            else:
                print(log_entry)
        except Exception:
            print(log_entry)

    def _save_debug(name, content, mode="w"):
        try:
            os.makedirs("ml_debug", exist_ok=True)
            path = os.path.join("ml_debug", name)
            with open(path, mode, encoding="utf-8") as fh:
                fh.write(content)
            return path
        except Exception as e:
            _safe_log(f"No se pudo guardar debug {name}: {e}", "warning")
            return None

    def _safe_parse_price(val):
        if 'limpiar_precio_pnp' in globals():
            try: return float(limpiar_precio_pnp(val))
            except Exception: pass
        try:
            s = re.sub(r'[^\d\.,]', '', str(val))
            if s.count('.') > 1: s = s.replace('.', '')
            s = s.replace(',', '.')
            return float(s) if s else 0.0
        except Exception: return 0.0

    def _normalize_identifier(link):
        try:
            m = re.search(r'([A-Z0-9\-]{4,})', link.split('?')[0].rstrip('/').split('/')[-1])
            if m: return f"NIKE-{m.group(1).upper()}"
            return f"NIKE-{abs(hash(link))}"
        except Exception:
            return f"NIKE-{abs(hash(link))}"

    start_ts = datetime.now(timezone.utc).isoformat()
    productos = []
    session = session or requests.Session()
    sz = sz or step
    STEP_SIZE = int(step)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Referer": "https://www.nike.com.pe/"
    }
    session.headers.update(headers)

    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    vistos = set()
    total_checked = 0

    _safe_log(f"🚀 Iniciando motor_nike para URL: {url}")

    try:
        for page in range(1, max_pages + 1):
            offset = (page - 1) * STEP_SIZE
            query_params["start"] = [str(offset)]
            query_params["sz"] = [str(sz)]
            new_query = urlencode(query_params, doseq=True)
            page_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, new_query, parsed_url.fragment))

            _safe_log(f"⚡ Escaneando Página {page} (start={offset})...")

            resp = None
            attempts, backoff = 0, 1
            while attempts < 3:
                try:
                    session.headers.update({"User-Agent": headers["User-Agent"]})
                    resp = session.get(page_url, timeout=15)
                    break
                except requests.RequestException as e:
                    attempts += 1
                    _safe_log(f"⚠️ Intento {attempts} falló: {e}", "warning")
                    time.sleep(backoff)
                    backoff *= 2

            if not resp:
                _safe_log("❌ Error fatal: No se obtuvo respuesta HTTP de Nike.", "error")
                break

            # 🔍 BLOQUE DE DIAGNÓSTICO EN VIVO
            _safe_log(f"📡 [DIAGNÓSTICO NIKE] Status Code recibido: {resp.status_code}")
            _safe_log(f"📡 [DIAGNÓSTICO NIKE] Tamaño del contenido: {len(resp.text)} caracteres")
            
            # Tomamos una muestra de los primeros 300 caracteres para ver qué respondió exactamente el servidor
            preview_texto = resp.text[:300].replace('\n', ' ').strip()
            _safe_log(f"🔍 [DIAGNÓSTICO NIKE] Preview HTML: {preview_texto}...")

            _save_debug("raw_html_nike.html", resp.text)
            _save_debug("raw_html_last.html", resp.text)

            if resp.status_code != 200:
                _safe_log(f"🛑 HTTP {resp.status_code} devuelto por Nike en {page_url}", "error")
                break

            text = resp.text
            
            # Verificación extra por si la respuesta contiene avisos de bloqueo ocultos
            if any(term in text.lower() for term in ["access denied", "cloudflare", "captcha", "security check"]):
                _safe_log("🚨 [ALERTA] El servidor devolvió una página de seguridad/bloqueo anti-bot de Nike.", "error")

            soup = BeautifulSoup(text, "html.parser")
            page_products = []

            # 1️⃣ Capa 1: JSON
            if '"results"' in text or '"products"' in text or '"searchResults"' in text:
                try:
                    json_blocks = re.findall(r'(\{(?:[^{}]|(?1))*\})', text[:300000])
                    for jb in json_blocks:
                        if '"results"' in jb and '"price"' in jb:
                            try:
                                parsed = json.loads(jb)
                                results = parsed.get("results") or parsed.get("products") or parsed.get("searchResults") or []
                                for it in results:
                                    if len(productos) + len(page_products) >= max_items: break
                                    nombre = (it.get("title") or it.get("name") or "").strip()
                                    precio = float(it.get("price") or 0) if it.get("price") else 0.0
                                    link = it.get("permalink") or it.get("url") or ""
                                    img = it.get("thumbnail") or it.get("image") or ""
                                    if nombre and 0 < precio <= limite:
                                        ident = _normalize_identifier(link or page_url)
                                        if ident in vistos: continue
                                        vistos.add(ident)
                                        page_products.append({
                                            "identificador": ident, "nombre": f"NIKE - {nombre.upper()}",
                                            "precio": precio, "precio_regular": float(it.get("original_price") or precio),
                                            "link": link, "img": img, "fecha": datetime.now(timezone.utc).isoformat()
                                        })
                                if page_products:
                                    _safe_log(f"✅ Se hallaron {len(page_products)} productos vía JSON embebido.")
                                    break
                            except Exception: continue
                except Exception as e_json:
                    _safe_log(f"Error procesando JSON: {e_json}", "warning")

            # 2️⃣ Capa 2: DOM HTML
            if not page_products:
                cards = soup.select(".product-tile, .product-card, .product-grid li, .product-grid div.product, a[href*='/product/'], a[href*='/productos/']")
                _safe_log(f"🔍 Tarjetas detectadas en HTML mediante selectores: {len(cards)}")

                for t in cards:
                    if len(productos) + len(page_products) >= max_items: break
                    try:
                        total_checked += 1
                        a_el = t if t.name == "a" else t.select_one("a[href]") or t
                        href = a_el.get("href") if a_el else None
                        if not href: continue
                        link_final = urljoin(f"{parsed_url.scheme}://{parsed_url.netloc}", href) if href.startswith("/") else href

                        tit_el = t.select_one(".product-name, .product-tile-title, .product-title, .pdp-link, h2, h3")
                        nombre = (tit_el.text.strip() if tit_el else (a_el.get("aria-label") or a_el.text or "")).strip()
                        if not nombre or len(nombre) < 3 or "TODAS" in nombre.upper(): continue

                        price_container = t.select_one(".price, .product-price, .product-tile-price") or t
                        price_texts = []
                        for sel in ["span.price", "span.amount", ".sales .value", ".value", "span"]:
                            el = price_container.select_one(sel)
                            if el and el.text: price_texts.append(el.text)

                        p_o = 0.0
                        if price_texts:
                            for txt in price_texts:
                                p = _safe_parse_price(txt)
                                if p > 0:
                                    p_o = p
                                    break
                        if p_o == 0.0:
                            m = re.search(r"(?:S/\.?\s*)(\d[\d\.,]*)", t.text)
                            if m: p_o = _safe_parse_price(m.group(1))

                        if p_o == 0.0: continue

                        p_r = p_o
                        del_el = t.select_one("del, .strike-through, .original-price")
                        if del_el and del_el.text:
                            p_r_val = _safe_parse_price(del_el.text)
                            if p_r_val > 0: p_r = p_r_val

                        if p_o < 30.0:
                            continue

                        if not (0 < p_o <= limite):
                            continue

                        identificador = _normalize_identifier(link_final)
                        if identificador in vistos: continue

                        img_el = t.select_one("img")
                        img_url = ""
                        if img_el:
                            img_url = img_el.get("data-src") or img_el.get("src") or ""
                            if img_url.startswith("//"): img_url = "https:" + img_url

                        vistos.add(identificador)
                        page_products.append({
                            "identificador": identificador, "nombre": f"NIKE - {nombre.upper()}",
                            "precio": p_o, "precio_regular": max(p_r, p_o), "link": link_final,
                            "img": img_url, "fecha": datetime.now(timezone.utc).isoformat()
                        })
                    except Exception as e_card:
                        continue

            if not page_products:
                _safe_log(f"🛑 No se encontraron productos válidos en la página start={offset}. Finalizando ciclo.")
                break

            existing_links = {p["link"] for p in productos}
            for p in page_products:
                if p.get("link") not in existing_links:
                    productos.append(p)
                    existing_links.add(p.get("link"))

            _safe_log(f"📈 Total acumulado de productos válidos: {len(productos)}")
            time.sleep(random.uniform(0.6, 1.4))

            if len(productos) >= max_items: break

    except Exception as e:
        _safe_log(f"💥 Error crítico general en motor_nike: {e}", "error")

    combined = {
        "metadata": {"url_tested": url, "limit": limite, "max_pages": max_pages, "step": STEP_SIZE, "sz": sz, "timestamp": start_ts, "checked": total_checked},
        "logs": logs_ejecucion,
        "productos": productos
    }
    try:
        _save_debug("combined_debug.json", json.dumps(combined, ensure_ascii=False, indent=2))
    except Exception: pass

    return productos


def motor_natura(url, limite=9999, max_pages=10, page_size=12, use_playwright_fallback=False, session=None, max_items=500, headers_override=None):
    """
    Motor Natura ultra fluido y protegido contra congelamientos.
    - Timeout estricto de 5s en API BFF.
    - Caída automática e inmediata a Scraping Directo de Catálogo (HTML/JSON-LD).
    - Retorna lista de productos 100% compatible con revisar_ofertas.
    """
    import os, time, random, json, requests, re
    from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, urljoin
    from bs4 import BeautifulSoup
    from datetime import datetime, timezone

    try:
        import streamlit as st
    except Exception:
        st = None

    logs_ejecucion = []

    def _log(msg, level="info"):
        ts = datetime.now(timezone.utc).isoformat()
        entry = {"ts": ts, "level": level, "msg": msg}
        logs_ejecucion.append(entry)
        try:
            if st:
                if level == "error": st.error(msg)
                elif level == "warning": st.warning(msg)
                elif level == "success": st.success(msg)
                else: st.write(f"👉 {msg}")
            else:
                print(f"[{level.upper()}] {msg}")
        except Exception:
            print(f"[{level.upper()}] {msg}")
        return entry

    def _ensure_debug_dir():
        try:
            d = os.path.join(os.getcwd(), "ml_debug")
            os.makedirs(d, exist_ok=True)
            return d
        except Exception: return None

    def _save_text(path, txt):
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(txt); fh.flush()
            return True
        except Exception: return False

    def _safe_parse_price(txt):
        try:
            s = re.sub(r'[^\d\.,]', '', str(txt))
            if s.count('.') > 1: s = s.replace('.', '')
            s = s.replace(',', '.')
            return float(s) if s else 0.0
        except Exception: return 0.0

    def _normalize_identifier(link):
        try:
            token = link.split('?')[0].rstrip('/').split('/')[-1]
            token = re.sub(r'[^A-Za-z0-9\-]', '', token) or str(abs(hash(link)))
            return f"NATURA-{token.upper()}"
        except Exception:
            return f"NATURA-{abs(hash(link))}"

    debug_dir = _ensure_debug_dir()
    start_ts = datetime.now(timezone.utc).isoformat()
    productos = []
    vistos = set()
    session = session or requests.Session()

    headers = {
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "accept-language": "es-PE,es;q=0.9,en;q=0.8",
        "referer": "https://www.natura.com.pe/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    try:
        if st and "NATURA_X_API_KEY" in st.secrets:
            headers["x-api-key"] = st.secrets["NATURA_X_API_KEY"]
        if st and "NATURA_AUTH_BEARER" in st.secrets:
            headers["authorization"] = f"Bearer {st.secrets['NATURA_AUTH_BEARER']}"
    except Exception: pass

    if headers_override and isinstance(headers_override, dict):
        headers.update(headers_override)

    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    refine_1 = q.get("refine_1", [None])[0]
    cgid_match = re.search(r'/c/([a-zA-Z0-9\-]+)', parsed.path)
    cgid = cgid_match.group(1) if cgid_match else None

    base = f"{parsed.scheme}://{parsed.netloc}"
    endpoint = base + "/bff-app-natura-peru/search"

    base_params = {
        "count": page_size,
        "q": "",
        "expand": "prices,availability,images,variations",
        "sort": "top-sellers",
        "apiMode": "product"
    }
    if refine_1: base_params["refine_1"] = refine_1
    elif cgid: base_params["cgid"] = cgid

    _log(f"🌿 Iniciando motor_natura para URL: {url} | Límite: S/. {limite}")

    use_bff_api = True

    for page in range(0, max_pages):
        start = page * page_size
        page_items = []

        # 1️⃣ INTENTO VÍA API BFF (Si sigue activo)
        if use_bff_api:
            params = dict(base_params)
            params["start"] = start
            _log(f"⚡ Intentando API BFF Natura (Timeout estricto: 5s)...")
            
            resp = None
            try:
                # Timeout ultracorto (3s conectar, 5s leer) para jamás congelar la pantalla
                resp = session.get(endpoint, params=params, headers=headers, timeout=(3, 5))
                _log(f"📡 Respuesta API BFF: HTTP {resp.status_code}")
            except Exception as e:
                _log("⏰ Timeout o bloqueo en API BFF. Desactivando BFF para usar catálogo directo.", "warning")
                use_bff_api = False # Desactiva la API para no perder tiempo en las siguientes páginas

            if resp and resp.status_code == 200:
                try:
                    data = resp.json()
                    items = data.get("results") or data.get("items") or data.get("products") or []
                    if not items and isinstance(data, dict):
                        for k, v in data.items():
                            if isinstance(v, list) and v and isinstance(v[0], dict):
                                if any(x in v[0] for x in ("name", "title", "price", "permalink", "productName")):
                                    items = v
                                    break
                    for it in items:
                        if len(productos) + len(page_items) >= max_items: break
                        try:
                            nombre = (it.get("name") or it.get("productName") or it.get("title") or "").strip()
                            if not nombre or len(nombre) < 3: continue
                            prices_info = it.get("prices") or it
                            p_o = _safe_parse_price(prices_info.get("salePrice") or prices_info.get("price") or prices_info.get("amount") or 0)
                            p_r = _safe_parse_price(prices_info.get("originalPrice") or prices_info.get("listPrice") or p_o)
                            p_r = max(p_r, p_o)
                            
                            if p_o == 0.0 or p_o > limite: continue
                            
                            link_rel = it.get("permalink") or it.get("url") or it.get("link") or ""
                            link_final = urljoin(base, link_rel) if link_rel else url
                            
                            images_info = it.get("images") or it.get("image") or ""
                            img_url = ""
                            if isinstance(images_info, list) and images_info:
                                img_url = images_info[0].get("url") if isinstance(images_info[0], dict) else str(images_info[0])
                            elif isinstance(images_info, str): img_url = images_info
                                
                            ident = _normalize_identifier(link_final)
                            if ident in vistos: continue
                            vistos.add(ident)
                            
                            page_items.append({
                                "identificador": ident,
                                "nombre": f"NATURA - {nombre.upper()}",
                                "precio": p_o,
                                "precio_regular": p_r,
                                "link": link_final,
                                "img": img_url,
                                "fecha": datetime.now(timezone.utc).isoformat()
                            })
                        except Exception: continue
                except Exception:
                    use_bff_api = False

        # 2️⃣ FALLBACK INSTANTÁNEO: SCRAPING DIRECTO DE LA PÁGINA WEB
        if not page_items:
            # Construir URL con paginación limpia
            query_p = dict(q)
            query_p["page"] = [str(page + 1)]
            page_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query_p, doseq=True), parsed.fragment))

            _log(f"🌐 Escaneando catálogo web directamente (Página {page + 1})...")
            try:
                resp_html = session.get(page_url, headers=headers, timeout=5)
                if resp_html.status_code == 200:
                    text = resp_html.text
                    soup = BeautifulSoup(text, "html.parser")

                    # Extraer vía JSON-LD Schema.org de VTEX
                    json_scripts = soup.find_all('script', type='application/ld+json')
                    for script in json_scripts:
                        if not script.string: continue
                        try:
                            data_ld = json.loads(script.string)
                            items_ld = data_ld.get('itemListElement', []) if isinstance(data_ld, dict) else (data_ld if isinstance(data_ld, list) else [])
                            for it in items_ld:
                                prod_data = it.get('item', it) if isinstance(it, dict) else {}
                                if not isinstance(prod_data, dict): continue
                                nombre = (prod_data.get('name') or '').strip()
                                if not nombre or len(nombre) < 3: continue
                                offers = prod_data.get('offers', {})
                                p_o = _safe_parse_price(offers.get('price') or offers.get('lowPrice') or 0)
                                p_r = _safe_parse_price(offers.get('highPrice') or p_o)
                                link_final = urljoin(base, prod_data.get('url') or '')
                                img = prod_data.get('image') or ''
                                if 0 < p_o <= limite:
                                    ident = _normalize_identifier(link_final)
                                    if ident not in vistos:
                                        vistos.add(ident)
                                        page_items.append({
                                            "identificador": ident,
                                            "nombre": f"NATURA - {nombre.upper()}",
                                            "precio": p_o,
                                            "precio_regular": max(p_r, p_o),
                                            "link": link_final,
                                            "img": img,
                                            "fecha": datetime.now(timezone.utc).isoformat()
                                        })
                        except Exception: continue

                    # Extraer vía DOM si JSON-LD no devolvió elementos
                    if not page_items:
                        cards = soup.select("[class*='productSummary'], .vtex-product-summary-2-x-container, div[data-product-id], article")
                        for t in cards:
                            try:
                                a_el = t.select_one("a[href]")
                                if not a_el: continue
                                link_final = urljoin(base, a_el["href"])
                                title_el = t.select_one("[class*='productName'], h2, h3") or a_el
                                title = title_el.get_text(strip=True)
                                price_el = t.select_one("[class*='sellingPrice'], .product-price")
                                p_o = _safe_parse_price(price_el.get_text() if price_el else "")
                                if p_o == 0.0 or p_o > limite: continue
                                ident = _normalize_identifier(link_final)
                                if ident in vistos: continue
                                vistos.add(ident)
                                img_el = t.select_one("img")
                                img_url = (img_el.get("src") or img_el.get("data-src") if img_el else "") or ""
                                page_items.append({
                                    "identificador": ident,
                                    "nombre": f"NATURA - {title.upper()}",
                                    "precio": p_o,
                                    "precio_regular": p_o,
                                    "link": link_final,
                                    "img": img_url,
                                    "fecha": datetime.now(timezone.utc).isoformat()
                                })
                            except Exception: continue
            except Exception as e_html:
                _log(f"⚠️ Error al obtener catálogo web: {e_html}", "warning")

        if not page_items:
            _log(f"ℹ️ Sin más ofertas en la página {page + 1}. Finalizando patrullaje de Natura.")
            break

        existing_links = {p["link"] for p in productos}
        for it in page_items:
            if len(productos) >= max_items: break
            if it["link"] not in existing_links:
                productos.append(it)
                existing_links.add(it["link"])

        _log(f"📦 Total acumulado de Natura: {len(productos)} ofertas.")
        if len(productos) >= max_items: break
        time.sleep(random.uniform(0.3, 0.7))

    _log(f"✅ Patrullaje de Natura completado. Total de productos indexados: {len(productos)}", "success")
    return productos









# =======================================================
# ENRUTADOR AISLADO
# =======================================================
#def escanear_tienda(url, limite):
 #   headers = {"User-Agent": random.choice(LISTA_USER_AGENTS), "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8", "Accept-Language": "es-ES,es;q=0.9"}
  #  dominio = urlparse(url).netloc.lower()
    
    #if "carsa.pe" in dominio: return motor_carsa(url, limite)
    #elif "thn.pe" in dominio: return motor_thn(url, limite)
   # elif any(k in dominio for k in ["tiendabelcorp", "cyzone", "lbel", "esika"]): return motor_belcorp(url, limite, headers)
  # elif "efe.com.pe" in dominio or "lacuracao.pe" in dominio: return motor_conecta_retail(url, limite, headers, "EFE" if "efe.com.pe" in dominio else "CURACAO")
    #elif "falabella.com" in dominio: return motor_falabella(url, limite, headers)
   # elif "adidas.pe" in dominio: return motor_adidas(url, limite)
   # elif "platanitos.com" in dominio: return motor_platanitos(url, limite)
    #elif "hiraoka.com.pe" in dominio: return motor_hiraoka(url, limite)
    #elif "oechsle.pe" in dominio: return motor_oechsle(url, limite)
    #elif "plazavea.com.pe" in dominio: return motor_plazavea(url, limite, headers=headers)
    #elif "juntoz.com" in dominio: return motor_juntoz(url, limite, headers=headers)
    #elif "triathlon.com.pe" in dominio: return motor_triathlon(url, limite, headers=headers)
    #elif "ripley.com.pe" in dominio: return motor_ripley(url, limite, headers=headers)
    #elif "footloose.pe" in dominio: return motor_footloose(url, limite)
    #elif "estilos.com.pe" in dominio: return motor_estilos(url, limite)
    #elif "promart.pe" in dominio: return motor_promart(url, limite, headers=headers)
    #elif "coolbox.pe" in dominio: return motor_coolbox(url, limite, headers=headers)
   # elif "nike.com.pe" in dominio: return motor_nike(url, limite)
    #elif "nike.com.pe" in url_completa: safe_log("🎯 [Enrutador] ¡Match detectado con Nike! Lanzando motor_nike...", "success") return motor_nike(url, limite)
    #else: return motor_tradicional_general(url, limite, headers)
def escanear_tienda(url, limite):
    dominio = urlparse(url).netloc.lower()
    url_completa = str(url).lower()
    
    safe_log(f"🔎 [Enrutador] Analizando URL: {url} | Dominio detectado: {dominio}", "info")
    
    # 🛡️ Validación robusta usando la URL completa (evita errores por URLs mal copiadas en Supabase)
    if "natura.com.pe" in url_completa:
        safe_log("🎯 [Enrutador] ¡Match exacto con Natura! Lanzando motor_natura...", "success")
        return motor_natura(url, limite)
    else: 
        safe_log(f"💤 [Enrutador] Tienda omitida (motores desactivados temporalmente para pruebas).", "info")
        return []

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
    
    # 🚀 CONTENEDOR DE DIAGNÓSTICO EN TIEMPO REAL (Aparece PRIMERO arriba)
    status_container = st.status("🔍 **Iniciando Patrullaje y Diagnóstico en Vivo...**", expanded=True)
    
    with status_container:
        for item in res.data:
            ident = item['identificador'].upper()
            url_low = item['url'].lower()
            
            # Categorización del Radar (Incluyendo el parche de Nike en Zapatillas)
            if "SHORT" in ident or "short" in url_low: grupo = "SHORTS"
            elif "PERFUME" in ident or "perfume" in url_low: grupo = "PERFUMES"
            elif "ZAPATILLA" in ident or "zapatilla" in url_low or "calzado" in url_low or "nike.com.pe" in url_low: grupo = "ZAPATILLAS"
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
            st.write(f"🔄 **Patrullando Tienda:** `{tienda_actual}` | Categoría: *{grupo}*...")
            
            # Aquí se ejecuta el motor y los logs de diagnóstico saldrán en vivo dentro de la caja
            prods = escanear_tienda(item['url'], item['precio_max'])
            
            for p in prods:
                try:
                    n_u = re.sub(r'\s+', ' ', p['nombre']).strip().upper()
                    
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
                    
                    precio_anterior = None
                    try:
                        res_ant = supabase.table("historial_precios").select("precio").eq("identificador", id_registro).execute()
                        if res_ant.data and len(res_ant.data) > 0:
                            precio_anterior = float(res_ant.data[0]['precio'])
                    except Exception: pass
                    
                    datos_guardar = {
                        "identificador": id_registro, 
                        "precio": p_v, 
                        "precio_regular": p_r, 
                        "link_producto": p['link'], 
                        "imagen_producto": p.get('img', ''), 
                        "fecha": fecha_hoy
                    }
                    
                    emoji = mapa_emojis.get(grupo, "🔥")

                    if precio_anterior is None:
                        try: supabase.table("historial_precios").insert(datos_guardar).execute()
                        except Exception: pass

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

                    elif p_v < precio_anterior:
                        try: supabase.table("historial_precios").update(datos_guardar).eq("identificador", id_registro).execute()
                        except Exception: pass

                    ahorro = precio_anterior - p_v
                    if p_v < precio_anterior:
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
                except Exception: continue

        st.success("✅ **¡Patrullaje y Diagnóstico Finalizados con Éxito!**")

    # 📊 REPORTE VISUAL DE PRODUCTOS (Se muestra DESPUÉS del diagnóstico)
    if len(lista_html_streamlit) > 0:
        try:
            st.markdown("---")
            st.markdown(f"### 🎯 Modelos encontrados e indexados en vivo ({len(lista_html_streamlit)}):")
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
