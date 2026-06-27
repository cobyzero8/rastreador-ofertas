import os
import json
import requests
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
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"
]

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
    except: 
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
    except: 
        return False

# =======================================================
# NÚCLEO EXTRACTOR ADAPTATIVO
# =======================================================
def escanear_tienda(url, limite):
    productos = []
    headers = {"User-Agent": random.choice(LISTA_USER_AGENTS), "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8", "Accept-Language": "es-ES,es;q=0.9"}
    url_low = url.lower()

    # -------------------------------------------------------
    # MOTOR BELCORP
    # -------------------------------------------------------
    if any(k in url_low for k in ["tiendabelcorp", "cyzone", "lbel", "esika"]):
        marca = "cyzone" if "cyzone" in url_low else "lbel" if "lbel" in url_low else "esika"
        try:
            resp = requests.get(f"https://{marca}.tiendabelcorp.com.pe/api/catalog_system/pub/products/search", headers=headers, params={"ft": "perfume", "_from": 0, "_to": 20, "O": "OrderByPriceASC"}, timeout=15, verify=False)
            for item in resp.json():
                offer = item["items"][0]["sellers"][0]["commertialOffer"]
                if 0 < float(offer["Price"]) <= limite:
                    productos.append({"nombre": f"{marca.upper()} - {item['productName'].upper()}", "precio": float(offer["Price"]), "precio_regular": float(offer.get("ListPrice", offer["Price"])), "link": item["link"], "img": item["items"][0]["images"][0]["imageUrl"]})
        except: 
            pass

    # -------------------------------------------------------
    # MOTOR CONECTA RETAIL (Efe / La Curacao)
    # -------------------------------------------------------
    elif "efe.com.pe" in url_low or "lacuracao.pe" in url_low:
        tag = "EFE" if "efe.com.pe" in url_low else "CURACAO"
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
                            if img.startswith('//'): 
                                img = 'https:' + img
                            productos.append({"nombre": f"{tag} - {tit_el.text.strip().upper()}", "precio": p_o, "precio_regular": limpiar_precio_pnp(r_el.text) if r_el else p_o, "link": urljoin(url, tit_el['href']), "img": img})
                    except: 
                        continue
        except: 
            pass

    # -------------------------------------------------------
    # MOTOR 5: ADIDAS PERÚ (MINERÍA DE JAVASCRIPT RECURSIVA)
    # -------------------------------------------------------
    elif "adidas" in url_low:
        try:
            texto_html = ""
            status_code = 0
            
            try:
                from curl_cffi import requests as crequests
                st.caption("🚀 Descargando datos dinámicos de Adidas mediante HTTP/2...")
                resp = crequests.get(url, impersonate="chrome", timeout=15)
                texto_html = resp.text
                status_code = resp.status_code
            except ImportError:
                headers_full = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
                }
                resp = requests.get(url, headers=headers_full, timeout=15, verify=False)
                texto_html = resp.text
                status_code = resp.status_code
            
            if status_code != 200:
                st.warning(f"⚠️ Adidas rechazó la conexión. Código HTTP: {status_code}.")
                return []
                
            # 🎯 ESTRATEGIA DE MINERÍA NÚCLEO: Extraer el JSON oculto en window.__INITIAL_STATE__
            json_bloque = None
            match_state = re.search(r'window\.__INITIAL_STATE__\s*=\s*(\{.*?\});', texto_html)
            if match_state:
                try: json_bloque = json.loads(match_state.group(1))
                except: pass
                
            if not json_bloque:
                # Intento alternativo por si está en otra variable global o bloque de scripts
                soup = BeautifulSoup(texto_html, 'html.parser')
                for sc in soup.find_all('script'):
                    if sc.text and 'initial_state' in sc.text.lower() or 'plpdata' in sc.text.lower():
                        match_inner = re.search(r'=\s*(\{.*?\});', sc.text)
                        if match_inner:
                            try:
                                json_bloque = json.loads(match_inner.group(1))
                                break
                            except: pass

            # Si encontramos el JSON estructurado, hacemos una búsqueda recursiva profunda de productos
            if json_bloque:
                items_raw = []
                def buscar_nodos_producto(nodo):
                    if isinstance(nodo, dict):
                        for k in ['products', 'results', 'items', 'itemListElement']:
                            if k in nodo and isinstance(nodo[k], list) and len(nodo[k]) > 0:
                                if isinstance(nodo[k][0], dict) and any(key in nodo[k][0] for key in ['title', 'name', 'displayName', 'productId']):
                                    return nodo[k]
                        for v in nodo.values():
                            res = buscar_nodos_producto(v)
                            if res: return res
                    elif isinstance(nodo, list):
                        for x in nodo:
                            res = buscar_nodos_producto(x)
                            if res: return res
                    return []
                
                items_raw = buscar_nodos_producto(json_bloque)
                
                for prod_j in items_raw:
                    try:
                        # Extraer del esquema estructurado o directo del objeto de catálogo
                        item_data = prod_j.get('item', prod_j) if isinstance(prod_j.get('item'), dict) else prod_j
                        nombre = item_data.get('name') or item_data.get('title') or item_data.get('displayName') or ""
                        nombre = str(nombre).upper()
                        if len(nombre) < 3: continue
                        
                        # Manejo inteligente de precios anidados
                        p_o = 0.0
                        p_r = 0.0
                        offers = item_data.get('offers', {})
                        if isinstance(offers, dict) and 'price' in offers:
                            p_o = safe_float(offers.get('price'))
                            p_r = safe_float(offers.get('highPrice', p_o))
                        else:
                            p_o = safe_float(item_data.get('salePrice') or item_data.get('price'))
                            p_r = safe_float(item_data.get('originalPrice') or item_data.get('price') or p_o)
                            
                        if 0 < p_o <= limite:
                            link_rel = item_data.get('url') or item_data.get('link') or item_data.get('href') or ""
                            link_f = urljoin("https://www.adidas.pe", link_rel)
                            
                            img_src = ""
                            img_raw = item_data.get('image') or item_data.get('imageUrl') or ""
                            if isinstance(img_raw, dict): img_src = img_raw.get('src') or img_raw.get('url') or ""
                            else: img_src = str(img_raw)
                            
                            if img_src.startswith('//'): img_src = 'https:' + img_src
                            
                            productos.append({
                                "nombre": f"ADIDAS - {nombre}",
                                "precio": p_o,
                                "precio_regular": max(p_r, p_o),
                                "link": link_f,
                                "img": img_src
                            })
                    except: continue

            # 🌐 CAPA DE RESPALDO EXTREMA: Parsing regex directo sobre el HTML por si el script falla
            if not productos:
                soup = BeautifulSoup(texto_html, 'html.parser')
                texto_html_limpio = texto_html.replace('\xa0', ' ').replace('&nbsp;', ' ')
                soup_limpia = BeautifulSoup(texto_html_limpio, 'html.parser')
                
                items = soup_limpia.select('.gl-product-card') or soup_limpia.select('[class*="gl-product-card"]') or soup_limpia.find_all(['div', 'article', 'li', 'a'], class_=lambda x: x and any(k in x.lower() for k in ['product', 'card', 'item', 'gl-']))
                for t in items:
                    try:
                        tit_el = t.select_one('.gl-product-card__title') or t.select_one('[class*="title"]') or t.find(['h3', 'h4', 'p', 'a'])
                        if not tit_el: continue
                        nombre_prod = tit_el.text.strip().upper()
                        
                        precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', t.text)
                        if precios:
                            prices_extracted = [float(pr.replace(',', '.')) for pr in precios]
                            precio_oferta = min(prices_extracted)
                            precio_regular = max(prices_extracted)
                            
                            if 0 < precio_oferta <= limite:
                                a_href = t.find('a', href=True)['href'] if t.find('a', href=True) else url
                                productos.append({
                                    "nombre": f"ADIDAS - {nombre_prod}", 
                                    "precio": precio_oferta, 
                                    "precio_regular": precio_regular, 
                                    "link": urljoin(url, a_href), 
                                    "img": ""
                                })
                    except: continue
                    
            if not productos:
                st.info(f"ℹ️ Diagnóstico Adidas: HTML recibido correctamente ({len(texto_html)} letras), pero ningún modelo está por debajo de S/. {limite:.2f} o requiere actualización de filtros.")
                
        except Exception as e:
            st.error(f"Fallo en comunicación con Adidas: {e}")

    # -------------------------------------------------------
    # MOTOR PLATANITOS Y TRADICIONALES
    # -------------------------------------------------------
    else:
        for pagina in range(1, 4):
            url_paginada = f"{url}{'&' if '?' in url else '?'}page={pagina}" if "platanitos.com" in url_low else url
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
                        precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', t.text)
                        if precios:
                            p_o = float(precios[0].replace(',', '.'))
                            if p_o <= limite:
                                del_el = t.find(['del', 'span'], class_=re.compile(r'(regular|original|old)', re.I))
                                p_r = float(re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', del_el.text)[0].replace(',', '.')) if del_el and re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', del_el.text) else p_o
                                a_el = t.find('a', href=True) or (t if t.name == 'a' and t.has_attr('href') else None)
                                if a_el and 'productos?' not in a_el['href'].lower():
                                    img_el = t.find('img', src=True)
                                    productos.append({"nombre": tit.text.strip().upper(), "precio": p_o, "precio_regular": p_r, "link": urljoin(url, a_el['href']), "img": img_el['src'] if img_el else ""})
                    except: 
                        continue
            except: 
                break
    return productos

# =======================================================
# SISTEMA DE PATRULLAJE CENTRAL
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
        
        if "SHORT" in ident or "short" in url_low: 
            grupo = "SHORTS"
        elif "PERFUME" in ident or "perfume" in url_low: 
            grupo = "PERFUMES"
        elif "ZAPATILLA" in ident or "zapatilla" in url_low or "calzado" in url_low: 
            grupo = "ZAPATILLAS"
        elif "MEDIAS" in ident or "medias" in url_low: 
            grupo = "MEDIAS"
        elif "POLO" in ident or "polo" in url_low: 
            grupo = "POLOS"
        elif "CASACA" in ident or "casaca" in url_low or "polera" in url_low: 
            grupo = "CASACAS"
        elif "BUZO" in ident or "buzo" in url_low or "pantalon" in url_low: 
            grupo = "BUZOS"
        elif "TV" in ident or "smart-tv" in url_low: 
            grupo = "TV"
        else: 
            grupo = "OTROS"
        
        # 🛡️ FIJADO ABSOLUTO: "grupo" escrito perfectamente en español para evitar congelamientos
        if target != "TODOS" and target != grupo: 
            continue
        
        tienda_actual = ident.split('-')[0]
        st.write(f"🔄 **Patrullando Tienda:** `{tienda_actual}` | Categoría: *{grupo}*...")
        
        prods = escanear_tienda(item['url'], item['precio_max'])
        for p in prods:
            try:
                n_u = p['nombre'].strip().upper()
                if n_u in enviados: 
                    continue
                enviados.add(n_u)
                total += 1
                
                p_v = float(p['precio'])
                p_r = max(float(p.get('precio_regular', p_v)), p_v)
                
                p['tienda_origen'] = tienda_actual
                lista_html_streamlit.append(p)
                
                supabase.table("historial_precios").upsert({"identificador": f"{item['identificador']}-{n_u.replace(' ','_')}", "precio": p_v, "precio_regular": p_r, "link_producto": p['link'], "imagen_producto": p.get('img', ''), "fecha": fecha_hoy}).execute()
                
                if p_v < p_r:
                    emoji = mapa_emojis.get(grupo, "🔥")
                    msg_t = f"{emoji} <b>¡BAJÓ DE PRECIO! REMATE</b> {emoji}\n━━━━━━━━━━━━━━━━━━━━━\n\n📦 <b>Producto:</b> <code>{p['nombre']}</code>\n🏪 <b>Tienda:</b> <code>{tienda_actual}</code>\n❌ <b>Normal:</b> S/. {p_r:.2f}\n💰 <b>Oferta:</b> S/. {p_v:.2f}\n📉 <b>Ahorro:</b> S/. {(p_r - p_v):.2f}\n"
                    if enviar_telegram_real(msg_t, p['link'], p.get('img', '')): 
                        alertas += 1
            except: 
                pass
            
    if len(lista_html_streamlit) > 0:
        try:
            st.write("---")
            st.write(f"### 🎯 Modelos encontrados e indexados en vivo ({len(lista_html_streamlit)}):")
            for prod in lista_html_streamlit:
                with st.container(border=True):
                    col1, col2 = st.columns([2, 8])
                    with col1:
                        if prod.get('img'): 
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
                            st.markdown(f"💰 **Precio Oferta: S/. {p_oferta:.2f}**")
                            st.markdown(f"🔥 **¡Ahorraste S/. {ahorro_soles:.2f}! ({porcentaje:.0f}% de Descuento)**")
                        else:
                            st.markdown(f"💰 **Precio Actual: S/. {p_oferta:.2f}**")
                            st.caption("ℹ️ _Precio base de lista detectado o sin descuento de etiqueta._")
                            
                        st.markdown(f"🔗 [🌐 IR A COMPRAR DIRECTO]({prod['link']})")
        except: 
            pass
            
    return f"Éxito. Modelos procesados: {total}. Alertas Telegram: {alertas}."
