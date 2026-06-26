import os
import json
import requests
from bs4 import BeautifulSoup
import re
import time
import random
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
from supabase import create_client, Client
import urllib3
import streamlit as st

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =======================================================
# INICIALIZACIÓN GLOBAL BLINDADA DE SUPABASE
# =======================================================
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = st.secrets["SUPABASE_KEY"] if "SUPABASE_KEY" in st.secrets else os.environ.get("SUPABASE_KEY")

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    raise ValueError("Error crítico: No se encontró la SUPABASE_KEY en el entorno ni en Secrets.")

# =======================================================
# RUTA 3: POOL GLOBAL DE USER-AGENTS PARA ROTACIÓN ACTIVA
# =======================================================
LISTA_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0"
]

# =======================================================
# FUNCIÓN GLOBAL DE LIMPIEZA DE PRECIOS PERUANOS (BLINDADA)
# =======================================================
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

# =======================================================
# FUNCIÓN DE ENVÍO REAL A TELEGRAM (FORMATO HTML)
# =======================================================
def enviar_telegram_real(mensaje, link_producto="", url_imagen=""):
    token = st.secrets.get("TELEGRAM_TOKEN")
    chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        return False

    mensaje_html = f"{mensaje}\n\n👉 <a href='{link_producto}'><b>¡COMPRAR AQUÍ!</b></a>"

    if url_imagen:
        url_api = f"https://api.telegram.org/bot{token}/sendPhoto"
        payload = {
            "chat_id": chat_id,
            "photo": url_imagen,
            "caption": mensaje_html,
            "parse_mode": "HTML"
        }
    else:
        url_api = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": mensaje_html,
            "parse_mode": "HTML"
        }

    try:
        res = requests.post(url_api, json=payload, timeout=10)
        return res.status_code == 200
    except:
        return False

# =======================================================
# NÚCLEO DE EXTRACCIÓN DE TIENDAS
# =======================================================
def escanear_tienda(url, limite):
    productos = []
    # 🛡️ Aplicamos la rotación inicial de User-Agent seleccionando uno al azar
    headers = {
        "User-Agent": random.choice(LISTA_USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-ES,es;q=0.8,en-US;q=0.5,en;q=0.3"
    }
    url_low = url.lower()

    # -------------------------------------------------------
    # MOTOR 1: BELCORP (Cyzone, L'Bel, Ésika)
    # -------------------------------------------------------
    if any(k in url_low for k in ["tiendabelcorp", "cyzone", "lbel", "esika"]):
        marca = "cyzone" if "cyzone" in url_low else "lbel" if "lbel" in url_low else "esika"
        api_url = f"https://{marca}.tiendabelcorp.com.pe/api/catalog_system/pub/products/search"
        params = {"ft": "perfume", "_from": 0, "_to": 20, "O": "OrderByPriceASC"}
        try:
            headers["User-Agent"] = random.choice(LISTA_USER_AGENTS)
            resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False)
            for item in resp.json():
                item_comercial = item["items"][0]["sellers"][0]["commertialOffer"]
                precio_oferta = float(item_comercial["Price"])
                precio_regular = float(item_comercial.get("ListPrice", precio_oferta))
                if 0 < precio_oferta <= limite:
                    productos.append({
                        "nombre": f"{marca.upper()} - {item['productName'].upper()}", 
                        "precio": precio_oferta, 
                        "precio_regular": precio_regular,
                        "link": item["link"], 
                        "img": item["items"][0]["images"][0]["imageUrl"]
                    })
        except: pass

    # -------------------------------------------------------
    # MOTOR 2: CONECTA RETAIL (¡Efe y La Curacao!)
    # -------------------------------------------------------
    elif "efe.com.pe" in url_low or "lacuracao.pe" in url_low:
        tienda_tag = "EFE" if "efe.com.pe" in url_low else "CURACAO"
        try:
            headers["User-Agent"] = random.choice(LISTA_USER_AGENTS)
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                items = soup.select('.product-item') or soup.select('.product-item-info')
                
                for t in items:
                    try:
                        tit_el = t.select_one('a.product-item-link') or t.select_one('.product-item-name a')
                        if not tit_el: continue
                        nombre_prod = tit_el.text.strip().upper()
                        if len(nombre_prod) < 3: continue
                        
                        enlace_final = urljoin(url, tit_el['href'])
                        
                        oferta_el = t.select_one('[data-price-type="finalPrice"] .price') or t.select_one('.special-price .price') or t.select_one('.price-box .price')
                        regular_el = t.select_one('[data-price-type="oldPrice"] .price') or t.select_one('.old-price .price')
                        
                        if not oferta_el: continue
                        precio_oferta = limpiar_precio_pnp(oferta_el.text)
                        if not precio_oferta: continue
                        
                        precio_regular = limpiar_precio_pnp(regular_el.text) if regular_el else precio_oferta
                        if precio_regular < precio_oferta: precio_regular = precio_oferta
                        
                        img_el = t.select_one('.product-image-photo') or t.find('img')
                        img_final = ""
                        if img_el:
                            img_final = img_el.get('data-src') or img_el.get('src') or ''
                            if img_final.startswith('//'): img_final = 'https:' + img_final
                        
                        if 0 < precio_oferta <= limite:
                            productos.append({
                                "nombre": f"{tienda_tag} - {nombre_prod}",
                                "precio": precio_oferta,
                                "precio_regular": precio_regular,
                                "link": enlace_final,
                                "img": img_final
                            })
                    except: continue
        except: pass

    # -------------------------------------------------------
    # MOTOR 3: JBL (API interna)
    # -------------------------------------------------------
    elif "jbl.com.pe" in url_low:
        try:
            keyword = "barra" if "barra" in url_low else "wireless" if "wireless" in url_low else "parlante" if "parlante" in url_low else "audio"
            api_url = "https://www.jbl.com.pe/on/demandware.store/Sites-JB-PE-Site/es_PE/Search-UpdateGrid"
            params = {"q": keyword, "srule": "price-low-to-high", "sz": "24"}
            
            headers["User-Agent"] = random.choice(LISTA_USER_AGENTS)
            resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                items = soup.select('.product-tile') or soup.select('[class*="product-item"]')
                
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
                        
                        if 0 < precio_oferta < 10.0 and any(k in nombre_prod for k in ["BARRA", "TV", "PARLANTE", "CINEMA", "SOUNDBAR"]):
                            precio_oferta = precio_oferta * 1000
                            
                        precio_regular = precio_oferta
                        if reg_el:
                            precio_regular = limpiar_precio_pnp(reg_el.text)
                            if 0 < precio_regular < 10.0 and any(k in nombre_prod for k in ["BARRA", "TV", "PARLANTE", "CINEMA", "SOUNDBAR"]):
                                precio_regular = precio_regular * 1000
                        
                        if 0 < precio_oferta <= limite:
                            link_el = t.find('a', href=True)
                            enlace_final = urljoin(url, link_el['href']) if link_el else url
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
                    except: continue
        except: pass

    # -------------------------------------------------------
    # RUTA 2: MOTOR 5: ADIDAS PERÚ (Doble capa: JSON-LD + HTML)
    # -------------------------------------------------------
    elif "adidas" in url_low:
        try:
            headers["User-Agent"] = random.choice(LISTA_USER_AGENTS)
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Capa A: Extracción desde Metadatos Estructurados (JSON-LD)
                json_scripts = soup.find_all('script', type='application/ld+json')
                for script in json_scripts:
                    try:
                        js_data = json.loads(script.string)
                        if isinstance(js_data, dict) and (js_data.get("@type") == "ItemList" or "itemListElement" in js_data):
                            for element in js_data.get("itemListElement", []):
                                item = element.get("item", {})
                                if not item: continue
                                nombre_prod = item.get("name", "").upper()
                                if len(nombre_prod) < 3: continue
                                
                                enlace_final = item.get("url", url)
                                offers = item.get("offers", {})
                                
                                precio_oferta = 0.0
                                precio_regular = 0.0
                                if offers.get("@type") == "AggregateOffer":
                                    precio_oferta = float(offers.get("lowPrice", 0))
                                    precio_regular = float(offers.get("highPrice", precio_oferta))
                                elif offers.get("@type") == "Offer":
                                    precio_oferta = float(offers.get("price", 0))
                                    precio_regular = precio_oferta
                                    
                                if 0 < precio_oferta <= limite:
                                    productos.append({
                                        "nombre": f"ADIDAS - {nombre_prod}",
                                        "precio": precio_oferta,
                                        "precio_regular": precio_regular,
                                        "link": enlace_final,
                                        "img": item.get("image", "")
                                    })
                            if productos: break
                    except: continue

                # Capa B: Fallback Clásico por Selectores HTML de Rejilla si falló el JSON-LD
                if not productos:
                    items = soup.select('.glass-product-card') or soup.select('[class*="product-card"]') or soup.select('.grid-item')
                    for t in items:
                        try:
                            tit_el = t.select_one('[class*="title"]') or t.select_one('[class*="name"]') or t.find('a')
                            if not tit_el: continue
                            nombre_prod = tit_el.text.strip().upper()
                            if len(nombre_prod) < 3: continue
                            
                            enlace_el = t.find('a', href=True)
                            enlace_final = urljoin(url, enlace_el['href']) if enlace_el else url
                            
                            oferta_el = t.select_one('[class*="sale-price"]') or t.select_one('[class*="price___"]') or t.select_one('.price')
                            regular_el = t.select_one('[class*="original-price"]') or t.select_one('del')
                            
                            if not oferta_el: continue
                            precio_oferta = limpiar_precio_pnp(oferta_el.text)
                            if not precio_oferta: continue
                            
                            precio_regular = limpiar_precio_pnp(regular_el.text) if regular_el else precio_oferta
                            
                            img_el = t.find('img')
                            img_final = ""
                            if img_el:
                                img_final = img_el.get('data-src') or img_el.get('src') or ''
                                if img_final.startswith('//'): img_final = 'https:' + img_final
                            
                            if 0 < precio_oferta <= limite:
                                productos.append({
                                    "nombre": f"ADIDAS - {nombre_prod}",
                                    "precio": precio_oferta,
                                    "precio_regular": precio_regular,
                                    "link": enlace_final,
                                    "img": img_final
                                })
                        except: continue
        except: pass

    # -------------------------------------------------------
    # MOTOR 4: PLATANITOS Y TRADICIONALES
    # -------------------------------------------------------
    else:
        for pagina in range(1, 4):
            url_paginada = url
            if "platanitos.com" in url_low:
                conector = "&" if "?" in url else "?"
                url_paginada = f"{url}{conector}page={pagina}"
            try:
                headers["User-Agent"] = random.choice(LISTA_USER_AGENTS)
                resp = requests.get(url_paginada, headers=headers, timeout=15, verify=False)
                if resp.status_code not in [200, 206]: break
                soup = BeautifulSoup(resp.text, 'html.parser')
                items = soup.find_all(['div', 'article', 'li', 'a'], class_=lambda x: x and any(k in x.lower() for k in ['product', 'card', 'item', 'grid', 'element']))
                if not items: break
                
                for t in items:
                    try:
                        tit = t.find(['h3', 'h2', 'span', 'p', 'div', 'a'], class_=re.compile(r'(title|name|nombre|description)', re.I))
                        if not tit or len(tit.text.strip()) < 3: continue
                        
                        del_el = t.find(['del', 'span'], class_=re.compile(r'(regular|original|old)', re.I))
                        precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', t.text)
                        if precios:
                            precio_oferta = float(precios[0].replace(',', '.'))
                            precio_regular = precio_oferta
                            
                            if del_el:
                                precios_del = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', del_el.text)
                                if precios_del: precio_regular = float(precios_del[0].replace(',', '.'))
                            elif len(precios) > 1:
                                prices_extracted = [float(pr.replace(',', '.')) for pr in precios]
                                precio_regular = max(prices_extracted)
                                precio_oferta = min(prices_extracted)
                            
                            if precio_oferta <= limite:
                                a_href = None
                                enlaces_internos = t.find_all('a', href=True)
                                for enlace in enlaces_internos:
                                    href_test = enlace['href'].lower()
                                    if any(x in href_test for x in ['cat=', 'brand=', 'filter=', 'javascript', 'productos?']): continue
                                    if 'detalle' in href_test or 'producto' in href_test:
                                        a_href = enlace['href']
                                        break
                                    a_href = enlace['href']
                                
                                if not a_href and enlaces_internos: a_href = enlaces_internos[0]['href']
                                if not a_href and t.name == 'a' and t.has_attr('href'): a_href = t['href']
                                if a_href and 'productos?' in a_href.lower(): continue
                                    
                                enlace_final = urljoin(url, a_href) if a_href else url
                                img = t.find('img', src=True)
                                productos.append({
                                    "nombre": tit.text.strip().upper(), 
                                    "precio": precio_oferta, 
                                    "precio_regular": precio_regular, 
                                    "link": enlace_final, 
                                    "img": img['src'] if img else ""
                                })
                    except: continue
                time.sleep(0.3)
            except: break
    return productos

# =======================================================
# SISTEMA DE PATRULLAJE DE OFERTAS
# =======================================================
def revisar_ofertas(filtro_objetivo="TODOS"):
    try:
        res = supabase.table("radares").select("*").execute()
    except Exception as e:
        st.error(f"Error de conexión con Supabase: {e}")
        return "Fallo en lectura de radares."

    if not res or not res.data: 
        return "Sin radares activos."
    
    total = 0
    alertas_enviadas = 0
    lista_html_streamlit = []
    
    mapa_emojis = {
        "PERFUMES": "🧪", "ZAPATILLAS": "👟", "MEDIAS": "🧦", "POLOS": "👕", 
        "CASACAS": "🧥", "SHORTS": "🩳", "BUZOS": "👖", "AUDIFONOS": "🎧", 
        "TV": "📺", "PARLANTE": "🔊", "BARRA DE SONIDO": "🎵", "CELULAR": "📱", 
        "PC": "💻", "REFRIGERADORA": "❄️", "LAVADORA": "🧺", 
        "ELECTRODOMESTICOS": "🔌", "CAMA": "🛏️", "OTROS": "📦"
    }
    enviados_en_este_clic = set()
    
    zona_peru = timezone(timedelta(hours=-5))
    fecha_hoy = datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")
    target = str(filtro_objetivo).strip().upper()
    
    for item in res.data:
        ident = item['identificador'].upper()
        url_low = item['url'].lower()
        
        if any(k in ident for k in ["AUDIFONO", "AURICULAR", "FONO"]) or any(k in url_low for k in ["wireless", "tws", "headphone", "audio-oars"]): 
            grupo = "AUDIFONOS"
        elif "BARRA" in ident or "SOUNDBAR" in ident or "barra" in url_low: 
            grupo = "BARRA DE SONIDO"
        elif "PARLANTE" in ident or "ALTAVOZ" in ident or "parlante" in url_low: 
            grupo = "PARLANTE"
        elif "TV" in ident or "TELEVISOR" in ident or "smart-tv" in url_low or "televisores" in url_low: 
            grupo = "TV"
        elif "CELULAR" in ident or "TELEFONO" in ident or "smartphone" in url_low or "celulares" in url_low: 
            grupo = "CELULAR"
        elif "PC" in ident or "LAPTOP" in ident: 
            grupo = "PC"
        elif "REFRIGERADORA" in ident or "NEVERA" in ident: 
            grupo = "REFRIGERADORA"
        elif "LAVADORA" in ident: 
            grupo = "LAVADORA"
        elif "ELECTRO" in ident or "LICUADORA" in ident: 
            grupo = "ELECTRODOMESTICOS"
        elif "CAMA" in ident or "COLCHON" in ident or "cama" in url_low: 
            grupo = "CAMA"
        elif "PERFUME" in ident: 
            grupo = "PERFUMES"
        elif "ZAPATILLA" in ident: 
            grupo = "ZAPATILLAS"
        elif "MEDIAS" in ident: 
            grupo = "MEDIAS"
        elif "POLO" in ident: 
            grupo = "POLOS"
        elif "CASACA" in ident: 
            grupo = "CASACAS"
        elif "SHORT" in ident: 
            grupo = "SHORTS"
        elif "BUZO" in ident: 
            grupo = "BUZOS"
        else: 
            grupo = "OTROS"
        
        if target != "TODOS" and target != grupo:
            continue
        
        prods = escanear_tienda(item['url'], item['precio_max'])
        
        for p in prods:
            try:
                nombre_unico = p['nombre'].strip().upper()
                if nombre_unico in enviados_en_este_clic: continue
                enviados_en_este_clic.add(nombre_unico)
                
                lista_html_streamlit.append(p)
                total += 1
                
                nombre_slug = nombre_unico.replace(" ", "_").replace("-", "_")
                id_producto_unico = f"{item['identificador']}-{nombre_slug}"
                
                p_venta = float(p['precio'])
                p_real = float(p.get('precio_regular', p_venta))
                
                if p_real < p_venta:
                    p_real = p_venta
                
                payload = {
                    "identificador": id_producto_unico,
                    "precio": p_venta, 
                    "precio_regular": p_real, 
                    "link_producto": p['link'],
                    "imagen_producto": p.get('img', ''),
                    "fecha": fecha_hoy
                }
                
                supabase.table("historial_precios").upsert(payload).execute()
                
                # 🎯 ESTRATEGIA INTELIGENTE: Solo dispara a Telegram si el precio actual tiene descuento vs el regular
                if p_venta < p_real:
                    emoji = mapa_emojis.get(grupo, "🔥")
                    text_alerta = f"{emoji} <b>¡BAJÓ DE PRECIO! REMATE</b> {emoji}\n"
                    text_alerta += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                    text_alerta += f"📦 <b>Producto:</b> <code>{p['nombre']}</code>\n"
                    text_alerta += f"🏪 <b>Tienda:</b> <code>{ident.split('-')[0]}</code>\n"
                    text_alerta += f"❌ <b>Precio Regular:</b> S/. {p_real:.2f}\n"
                    text_alerta += f"💰 <b>Precio Oferta:</b> S/. {p_venta:.2f}\n"
                    text_alerta += f"📉 <b>Ahorro Neto:</b> S/. {(p_real - p_venta):.2f}\n"
                    text_alerta += f"🎯 <b>Tu Tope:</b> S/. {item['precio_max']:.2f}\n"
                    
                    if enviar_telegram_real(text_alerta, p['link'], p.get('img', '')):
                        alertas_enviadas += 1
                        time.sleep(0.4)
                        
            except Exception as e:
                st.error(f"Error procesando ítem: {e}")
                
    if len(lista_html_streamlit) > 0:
        try:
            st.write(f"### 🎯 Modelos encontrados en este instante ({len(lista_html_streamlit)}):")
            for prod in lista_html_streamlit:
                with st.container(border=True):
                    col1, col2 = st.columns([2, 8])
                    with col1:
                        if prod.get('img'): st.image(prod['img'], width=120)
                        else: st.write("📷 _Sin Foto_")
                    with col2:
                        st.markdown(f"#### `{prod['nombre']}`")
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
                            st.caption("ℹ️ _Precio de etiqueta original o sin descuento de lista reportado._")
                            
                        st.markdown(f"🔗 [🌐 IR A COMPRAR DIRECTO EN LA TIENDA]({prod['link']})")
        except: 
            pass

    return f"Éxito. Modelos individuales procesados y guardados: {total}. Alertas Telegram: {alertas_enviadas}."
