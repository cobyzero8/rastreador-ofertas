import os
import json
import requests
import httpx
from bs4 import BeautifulSoup
import re
import time
import random
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse, parse_qs
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
    """Función segura para mostrar logs tanto en la App (Streamlit) como en Consola (GitHub)"""
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
    if not texto_precio: 
        return 0.0
    try:
        texto = re.sub(r'[^\d.,]', '', texto_precio).strip()
        if not texto: 
            return 0.0
        if ',' in texto and '.' in texto:
            if texto.rfind('.') > texto.rfind(','): 
                texto = texto.replace(',', '')
            else: 
                texto = texto.replace('.', '').replace(',', '.')
        else:
            if ',' in texto and len(texto.split(',')[-1]) != 2: 
                texto = texto.replace(',', '')
            elif '.' in texto and len(texto.split('.')[-1]) != 2: 
                texto = texto.replace('.', '')
            elif ',' in texto: 
                texto = texto.replace(',', '.')
        match = re.findall(r'\d+\.\d+|\d+', texto)
        return float(match[0]) if match else 0.0
    except Exception: 
        return 0.0

def safe_float(val):
    if val is None: 
        return 0.0
    if isinstance(val, (int, float)): 
        return float(val)
    return limpiar_precio_pnp(str(val))

def enviar_telegram_real(mensaje, link_producto="", url_imagen=""):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: 
        return False
    mensaje_html = f"{mensaje}\n\n👉 <a href='{link_producto}'><b>¡COMPRAR AQUÍ!</b></a>"
    url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto" if url_imagen else f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "parse_mode": "HTML"}
    if url_imagen: 
        payload["photo"], payload["caption"] = url_imagen, mensaje_html
    else: 
        payload["text"] = mensaje_html
    try: 
        return requests.post(url_api, json=payload, timeout=10).status_code == 200
    except Exception: 
        return False

def extraer_productos_json_universal(nodo):
    coleccion = []
    if isinstance(nodo, dict):
        if any(k in nodo for k in ['displayName', 'productName', 'title']) and any(k in nodo for k in ['prices', 'price', 'salePrice']):
            nombre = nodo.get('displayName') or nodo.get('productName') or nodo.get('title')
            if nombre and len(str(nombre).strip()) > 3:
                coleccion.append(nodo)
        for v in nodo.values():
            coleccion.extend(extraer_productos_json_universal(v))
    elif isinstance(nodo, list):
        for item in nodo:
            coleccion.extend(extraer_productos_json_universal(item))
    return coleccion

def encontrar_foto_fala(nodo):
    if isinstance(nodo, str):
        if (nodo.startswith('http') or nodo.startswith('//')) and ('falabella' in nodo or 'media' in nodo or any(ext in nodo.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp'])) and '/product/' not in nodo:
            return nodo
    elif isinstance(nodo, dict):
        for k in ['imageUrl', 'src', 'url', 'thumbnail', 'image']:
            val = nodo.get(k)
            if isinstance(val, str) and (val.startswith('http') or val.startswith('//')) and len(val) > 10 and '/product/' not in val:
                return val
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
            for sub_v in d.values(): 
                extraer_numeros_dict(sub_v, valores_aux)
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
        for sub_v in d.values():
            extraer_numeros_dict(sub_v, valores_aux)
    elif isinstance(d, list):
        for item in d:
            extraer_numeros_dict(item, valores_aux)

# =======================================================
# 🚀 MOTORES DE EXTRACCIÓN
# =======================================================

def motor_belcorp(url, limite, headers):
    productos = []
    dominio = urlparse(url).netloc.lower()
    marca = "cyzone" if "cyzone" in dominio else "lbel" if "lbel" in dominio else "esika"
    try:
        resp = requests.get(f"https://{marca}.tiendabelcorp.com.pe/api/catalog_system/pub/products/search", headers=headers, params={"ft": "perfume", "_from": 0, "_to": 20, "O": "OrderByPriceASC"}, timeout=15, verify=False)
        for item in resp.json():
            offer = item["items"][0]["sellers"][0]["commertialOffer"]
            if 0 < float(offer["Price"]) <= limite:
                productos.append({
                    "nombre": f"{marca.upper()} - {item['productName'].upper()}", 
                    "precio": float(offer["Price"]), 
                    "precio_regular": float(offer.get("ListPrice", offer["Price"])), 
                    "link": item["link"], 
                    "img": item["items"][0]["images"][0]["imageUrl"]
                })
    except Exception:
        pass
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
                    if not tit_el: 
                        continue
                    o_el = t.select_one('[data-price-type="finalPrice"] .price') or t.select_one('.special-price .price') or t.select_one('.price-box .price')
                    r_el = t.select_one('[data-price-type="oldPrice"] .price') or t.select_one('.old-price .price')
                    if not o_el: 
                        continue
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
                except Exception:
                    continue
    except Exception:
        pass
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
            except Exception:
                pass
            if status_code == 200 and len(texto_html) > 5000: 
                break
            else: 
                time.sleep(random.uniform(1.5, 3.0))
        
        safe_log(f"ℹ️ Diagnóstico Falabella: HTML recibido ({len(texto_html)} letras, Estado: {status_code}). Buscando ofertas...", "info")
        if status_code != 200 or len(texto_html) < 5000: 
            return []
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
                except Exception:
                    continue

        if fala_prods:
            for prod in fala_prods:
                try:
                    nombre = str(prod.get('displayName') or prod.get('productName') or prod.get('title') or '').strip().upper()
                    if len(nombre) < 3: 
                        continue
                    
                    p_o, p_r = 0.0, 0.0
                    precios_list = prod.get('prices') or prod.get('price') or []
                    if isinstance(precios_list, dict): 
                        precios_list = [precios_list]
                    
                    if isinstance(precios_list, list):
                        for pr in precios_list:
                            if not isinstance(pr, dict): 
                                continue
                            tipo_p = str(pr.get('type', '')).lower()
                            val_p = pr.get('price') or pr.get('value')
                            if isinstance(val_p, list) and len(val_p) > 0: 
                                val_p = val_p[0]
                            float_p = safe_float(val_p)
                            
                            if any(x in tipo_p for x in ['sale', 'event', 'oferta', 'internet', 'current', 'card', 'cmr', 'eventprice']): 
                                p_o = float_p
                            elif any(x in tipo_p for x in ['list', 'original', 'regular', 'normal', 'normalprice']): 
                                p_r = float_p
                        
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
                            if match_id:
                                img = f"https://media.falabella.com/falabellaPE/{match_id[-1]}_01/w=800,h=800,fit=pad"
                        
                        if str(img).startswith('//'): img = 'https:' + str(img)
                        img = str(img).split(' ')[0].strip().rstrip(',')
                        productos.append({"nombre": f"FALABELLA - {nombre}", "precio": p_o, "precio_regular": max(p_r, p_o), "link": link_final, "img": str(img)})
                except Exception:
                    continue

        if not productos:
            items = soup.find_all(['div', 'li', 'article'], class_=re.compile(r'(pod|card|product-item|item)', re.I))
            for t in items:
                try:
                    tit_el = t.find(['b', 'span', 'p', 'h3', 'h4', 'a'], id=re.compile(r'name', re.I)) or t.find(['b', 'span', 'p', 'h3', 'h4', 'a'], class_=re.compile(r'(title|name|description|displayName)', re.I))
                    if not tit_el or len(tit_el.text.strip()) < 3: 
                        continue
                    
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
                            if match_id:
                                img = f"https://media.falabella.com/falabellaPE/{match_id[-1]}_01/w=800,h=800,fit=pad"
                        
                        if str(img).startswith('//'): img = 'https:' + str(img)
                        img = str(img).split(' ')[0].strip().rstrip(',')
                        productos.append({"nombre": f"FALABELLA - {tit_el.text.strip().upper()}", "precio": p_o, "precio_regular": max(p_r, p_o), "link": link_final, "img": img})
                except Exception:
                    continue

        vistos = set()
        productos_unicos = []
        for p in productos:
            if p['link'] not in vistos:
                vistos.add(p['link'])
                productos_unicos.append(p)
        if productos_unicos: safe_log(f"🎯 Falabella Motor: ¡Se extrajeron exitosamente {len(productos_unicos)} productos!", "success")
        return productos_unicos
    except Exception as e:
        safe_log(f"Error interno en motor Falabella: {e}", "error")
    return productos

def motor_adidas(url, limite):
    """Motor Adidas con el bypass definitivo de Redes Sociales (Mascarada de Discord/Slackbot + HTTP/2)"""
    productos = []
    texto_html = ""
    status_code = 0
    
    # Lista de agentes Whitelistados por e-commerce para previsualización de enlaces de chat
    bots_whitelist = [
        "Mozilla/5.0 (compatible; Discordbot/2.0; +https://discordapp.com)",
        "Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)",
        "Mozilla/5.0 (compatible; WhatsApp/2.24.4; i)"
    ]
    
    headers = {
        "user-agent": random.choice(bots_whitelist),
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "accept-language": "es-PE,es;q=0.9",
        "cache-control": "no-cache"
    }
    
    try:
        with httpx.Client(http2=True, timeout=15.0, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            status_code = resp.status_code
            texto_html = resp.text
    except Exception as e:
        safe_log(f"Aviso HTTP/2 en Adidas: {e}", "caption")

    safe_log(f"ℹ️ Diagnóstico de Seguridad Adidas: Código recibido: {status_code}, Longitud: {len(texto_html)} letras.", "info")

    if texto_html and len(texto_html) > 5000:
        texto_html = texto_html.replace('\xa0', ' ').replace('&nbsp;', ' ')
        soup = BeautifulSoup(texto_html, 'html.parser')
        
        next_script = soup.find('script', id='__NEXT_DATA__')
        if next_script:
            try:
                json_data = json.loads(next_script.text)
                def buscar_en_json_back(nodo):
                    if isinstance(nodo, dict):
                        for k in ['products', 'results', 'items', 'itemListElement']:
                            if k in nodo and isinstance(nodo[k], list) and len(nodo[k]) > 0:
                                if isinstance(nodo[k][0], dict) and any(key in nodo[k][0] for key in ['title', 'name', 'displayName']):
                                    return nodo[k]
                        for v in nodo.values():
                            res = buscar_en_json_back(v)
                            if res: return res
                    elif isinstance(nodo, list):
                        for x in nodo:
                            res = buscar_en_json_back(x)
                            if res: return res
                    return []
                
                items_json = buscar_en_json_back(json_data)
                if items_json:
                    for prod_j in items_json:
                        try:
                            nombre = prod_j.get('name') or prod_j.get('title') or prod_j.get('displayName') or ""
                            nombre = str(nombre).upper()
                            if len(nombre) < 3: continue
                            p_o = safe_float(prod_j.get('salePrice') or prod_j.get('price'))
                            p_r = safe_float(prod_j.get('originalPrice') or prod_j.get('price') or p_o)
                            if p_r > (p_o * 10): p_r = p_r / 100
                            if 0 < p_o <= limite:
                                link_rel = prod_j.get('url') or prod_j.get('link') or prod_j.get('href') or ""
                                productos.append({"nombre": f"ADIDAS - {nombre}", "precio": p_o, "precio_regular": max(p_r, p_o), "link": urljoin("https://www.adidas.pe", link_rel), "img": str(prod_j.get('image', ''))})
                        except Exception:
                            continue
            except Exception:
                pass

        if not productos:
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
                        precio_oferta = limpiar_precio_pnp(oferta_el.text)
                        precio_regular = limpiar_precio_pnp(regular_el.text) if regular_el else precio_oferta
                        if precio_regular > (precio_oferta * 10): precio_regular = precio_regular / 100
                        if 0 < precio_oferta <= limite:
                            productos.append({"nombre": f"ADIDAS - {nombre_prod}", "precio": precio_oferta, "precio_regular": max(precio_regular, precio_oferta), "link": urljoin(url, enlace_el['href']) if enlace_el else url, "img": img_el.get('src', '') if img_el else ''})
                except Exception:
                    continue
                    
    if productos:
        safe_log(f"🎯 Adidas Motor: ¡Se extrajeron exitosamente {len(productos)} productos!", "success")
    return productos

def motor_jbl(url, limite, headers):
    """Motor dedicado para JBL Perú (Bypass por API unificada de catálogo de marca + Fallback HTML)"""
    productos = []
    dominio = urlparse(url).netloc.lower()
    
    # --- CAPA 1: EXTRACCIÓN MEDIANTE API DE SERVICIO UNIFICADO (VTEX BACKEND) ---
    try:
        api_url = f"https://{dominio}/api/catalog_system/pub/products/search"
        # Traemos los primeros 24 productos ordenados de forma ascendente
        resp_api = requests.get(api_url, headers=headers, params={"_from": 0, "_to": 24}, timeout=12, verify=False)
        if resp_api.status_code == 200 and isinstance(resp_api.json(), list):
            for item in resp_api.json():
                try:
                    nombre = item.get('productName', '').upper()
                    if not nombre: continue
                    items_vtex = item.get('items', [])
                    if not items_vtex: continue
                    sellers = items_vtex[0].get('sellers', [])
                    if not sellers: continue
                    comm_offer = sellers[0].get('commertialOffer', {})
                    
                    p_o = float(comm_offer.get('Price', 0))
                    p_r = float(comm_offer.get('ListPrice', p_o))
                    
                    if 0 < p_o <= limite:
                        link_final = item.get('link', url)
                        img_list = items_vtex[0].get('images', [{}])
                        img_final = img_list[0].get('imageUrl', '') if img_list else ''
                        
                        productos.append({
                            "nombre": f"JBL - {nombre}",
                            "precio": p_o,
                            "precio_regular": max(p_r, p_o),
                            "link": link_final,
                            "img": img_final
                        })
                except Exception:
                    continue
            if productos:
                safe_log(f"🎯 Motor JBL (API de Servicio): ¡Indexados {len(productos)} modelos audios!", "success")
                return productos
    except Exception:
        pass

    # --- CAPA 2: ESTRATEGIA DE EXTRACCIÓN HTML TRADICIONAL (FALLBACK) ---
    try:
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            tarjetas = soup.find_all(['div', 'li', 'article', 'a'], class_=re.compile(r'(product|card|item|shelf|grid)', re.I))
            for t in tarjetas:
                try:
                    tit_el = t.find(['h3', 'h2', 'h4', 'span', 'p', 'a'], class_=re.compile(r'(title|name|nombre)', re.I))
                    if not tit_el or len(tit_el.text.strip()) < 3: continue
                    
                    precios_encontrados = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', t.text)
                    if not precios_encontrados: continue
                    
                    nums = sorted(list(set([limpiar_precio_pnp(p) for p in precios_encontrados if limpiar_precio_pnp(p) > 0])))
                    if not nums: continue
                    p_o = nums[0]
                    p_r = nums[-1] if len(nums) > 1 else p_o
                    
                    if 0 < p_o <= limite:
                        a_el = t.find('a', href=True) or (t if t.name == 'a' and t.has_attr('href') else None)
                        link_final = urljoin(url, a_el['href']) if a_el else url
                        
                        img_el = t.find('img')
                        img = img_el.get('data-src') or img_el.get('src') or '' if img_el else ''
                        if img.startswith('//'): img = 'https:' + img
                        
                        productos.append({
                            "nombre": f"JBL - {tit_el.text.strip().upper()}",
                            "precio": p_o,
                            "precio_regular": p_r,
                            "link": link_final,
                            "img": img
                        })
                except Exception:
                    continue
    except Exception:
        pass

    vistos = set()
    productos_unicos = []
    for p in productos:
        if p['link'] not in vistos:
            vistos.add(p['link'])
            productos_unicos.append(p)
    if productos_unicos: safe_log(f"🎯 Motor JBL (Estructura Web): ¡Indexados {len(productos_unicos)} modelos!", "success")
    return productos_unicos

def motor_platanitos(url, limite):
    productos = []
    try:
        texto_html = ""
        try:
            headers = {
                "User-Agent": random.choice(LISTA_USER_AGENTS),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "es-ES,es;q=0.9"
            }
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            texto_html = resp.text
        except Exception:
            pass

        if not texto_html or len(texto_html) < 2000: 
            return []
        soup = BeautifulSoup(texto_html, 'html.parser')
        tarjetas = soup.find_all(['div', 'article', 'a'], class_=re.compile(r'(product|card|item|col|grid)', re.I))
        
        if not tarjetas:
            enlaces_prod = soup.find_all('a', href=re.compile(r'/producto/', re.I))
            seen_divs = set()
            for a in enlaces_prod:
                parent = a.find_parent('div')
                if parent and id(parent) not in seen_divs:
                    seen_divs.add(id(parent))
                    tarjetas.append(parent)
                    
        for t in tarjetas:
            try:
                a_el = t.find('a', href=re.compile(r'/producto/', re.I)) or (t if t.name == 'a' and '/producto/' in t.get('href', '').lower() else None)
                if not a_el: 
                    continue
                
                link_final = urljoin("https://platanitos.com", a_el['href'])
                tit_el = t.find(['h3', 'h2', 'span', 'p', 'div'], class_=re.compile(r'(title|name|nombre|description)', re.I))
                nombre = tit_el.text.strip() if tit_el else ""
                if not nombre and a_el.has_attr('title'): nombre = a_el['title'].strip()
                if not nombre:
                    spans = [s.text.strip() for s in t.find_all(['span', 'p']) if len(s.text.strip()) > 4]
                    if spans: nombre = spans[0]
                    
                if len(nombre) < 3 or "PLATANITOS" in nombre.upper(): 
                    continue
                
                textos_precios = []
                for el in t.find_all(['span', 'p', 'b', 'strong', 'del', 'small']):
                    if el.find(['span', 'p', 'b', 'strong', 'del', 'small']): continue
                    txt_el = el.text.strip() if el.text else ""
                    if 'S/' in txt_el and '%' not in txt_el and len(txt_el) < 20:
                        matches = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', txt_el)
                        textos_precios.extend(matches)
                        
                if not textos_precios: 
                    continue
                nums = sorted(list(set([limpiar_precio_pnp(p) for p in textos_precios if limpiar_precio_pnp(p) > 0])))
                if not nums: 
                    continue
                
                p_o = nums[0]
                p_r = nums[-1] if len(nums) > 1 else p_o
                
                if 0 < p_o <= limite:
                    img = ""
                    img_tags = t.find_all('img')
                    for img_el in img_tags:
                        src_candidato = img_el.get('data-src') or img_el.get('src') or img_el.get('data-lazy') or ""
                        src_low = str(src_candidato).lower()
                        if src_candidato and 'data:image' not in src_low:
                            if any(x in src_low for x in ['arrow', 'chevron', 'left', 'right', 'icon', 'logo', 'svg', 'loading', 'placeholder']):
                                continue
                            img = src_candidato
                            break
                    if not img and img_tags:
                        img = img_tags[0].get('data-src') or img_tags[0].get('src') or ""
                        
                    if str(img).startswith('//'): img = 'https:' + str(img)
                    productos.append({"nombre": f"PLATANITOS - {nombre.upper()}", "precio": p_o, "precio_regular": p_r, "link": link_final, "img": img})
            except Exception:
                continue
    except Exception:
        pass
    return productos

def motor_tradicional_general(url, limite, headers):
    productos = []
    dominio = urlparse(url).netloc.lower()
    for pagina in range(1, 4):
        url_paginada = f"{url}{'&' if '?' in url else '?'}page={pagina}" if "platanitos.com" in dominio else url
        try:
            resp = requests.get(url_paginada, headers=headers, timeout=15, verify=False)
            if resp.status_code not in [200, 206]: 
                break
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = soup.find_all(['div', 'article', 'li', 'a'], class_=lambda x: x and any(k in x.lower() for k in ['product', 'card', 'item', 'grid']))
            if not items: 
                break
            for t in items:
                try:
                    tit = t.find(['h3', 'h2', 'span', 'p', 'div', 'a'], class_=re.compile(r'(title|name|nombre|description)', re.I))
                    if not tit or len(tit.text.strip()) < 3: 
                        continue
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
                except Exception:
                    continue
        except Exception:
            break
    return productos

# =======================================================
# Enrutador Central del Escaneo
# =======================================================
def escanear_tienda(url, limite):
    headers = {"User-Agent": random.choice(LISTA_USER_AGENTS), "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8", "Accept-Language": "es-ES,es;q=0.9"}
    dominio = urlparse(url).netloc.lower()
    
    if any(k in dominio for k in ["tiendabelcorp", "cyzone", "lbel", "esika"]): 
        return motor_belcorp(url, limite, headers)
    elif "efe.com.pe" in dominio or "lacuracao.pe" in dominio:
        tag = "EFE" if "efe.com.pe" in dominio else "CURACAO"
        return motor_conecta_retail(url, limite, headers, tag)
    elif "falabella.com" in dominio: 
        return motor_falabella(url, limite, headers)
    elif "adidas" in dominio: 
        return motor_adidas(url, limite)
    elif "jbl" in dominio:
        return motor_jbl(url, limite, headers)
    elif "platanitos.com" in dominio: 
        return motor_platanitos(url, limite)
    else: 
        return motor_tradicional_general(url, limite, headers)

# =======================================================
# SISTEMA DE PATRULLAJE CENTRAL (CON MEMORIA BLINDADA)
# =======================================================
def revisar_ofertas(filtro_objetivo="TODOS"):
    try: 
        res = supabase.table("radares").select("*").execute()
    except Exception as e: 
        return f"Fallo Supabase: {e}"
    if not res or not res.data: 
        return "Sin radares."
    
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

        if target != "TODOS" and target != grupo: 
            continue
            
        tienda_actual = ident.split('-')[0]
        safe_log(f"🔄 **Patrullando Tienda:** `{tienda_actual}` | Categoría: *{grupo}*...", "write")
        
        prods = escanear_tienda(item['url'], item['precio_max'])
        for p in prods:
            try:
                n_u = re.sub(r'\s+', ' ', p['nombre']).strip().upper()
                if n_u in enviados: 
                    continue
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
                except Exception:
                    pass
                
                datos_guardar = {"identificador": id_registro, "precio": p_v, "precio_regular": p_r, "link_producto": p['link'], "imagen_producto": p.get('img', ''), "fecha": fecha_hoy}
                try:
                    if registro_existe: supabase.table("historial_precios").update(datos_guardar).eq("identificador", id_registro).execute()
                    else: supabase.table("historial_precios").insert(datos_guardar).execute()
                except Exception:
                    pass
                
                debe_alertar = False
                if precio_anterior is not None:
                    if p_v < precio_anterior: debe_alertar = True
                else:
                    if p_v < p_r: debe_alertar = True
                
                if debe_alertar:
                    emoji = mapa_emojis.get(grupo, "🔥")
                    msg_t = f"{emoji} <b>¡OFERTA DETECTADA!</b> {emoji}\n━━━━━━━━━━━━━━━━━━━━━\n\n📦 <b>Producto:</b> <code>{p['nombre']}</code>\n🏪 <b>Tienda:</b> <code>{tienda_actual}</code>\n❌ <b>Precio Anterior:</b> S/. {precio_anterior if precio_anterior else p_r:.2f}\n💰 <b>Precio Nuevo:</b> S/. {p_v:.2f}\n📉 <b>Ahorro Real:</b> S/. {((precio_anterior if precio_anterior else p_r) - p_v):.2f}\n"
                    if enviar_telegram_real(msg_t, p['link'], p.get('img', '')): 
                        alertas += 1
            except Exception: 
                pass
                
    if len(lista_html_streamlit) > 0:
        try:
            safe_log("---", "write")
            safe_log(f"### 🎯 Modelos encontrados e indexados en vivo ({len(lista_html_streamlit)}):", "write")
            for prod in lista_html_streamlit:
                with st.container(border=True):
                    col1, col2 = st.columns([2, 8])
                    with col1:
                        if prod.get('img') and len(prod['img']) > 5: 
                            st.image(prod['img'], width=120)
                        else: 
                            st.write("📷 _Sin Foto_")
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
                            st.caption("ℹ️ _Precio base de lista detectado o sin descuento de etiqueta._")
                        st.markdown(f"🔗 [🌐 IR A COMPRAR DIRECTO]({prod['link']})")
        except Exception: 
            pass
            
    return f"Éxito. Modelos procesados: {total}. Alertas Telegram: {alertas}."
