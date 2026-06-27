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
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
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
    # MOTOR 5: ADIDAS PERÚ (IMPERSONACIÓN AUTOMÁTICA PURA)
    # -------------------------------------------------------
    elif "adidas" in url_low:
        try:
            texto_html = ""
            status_code = 0
            
            try:
                from curl_cffi import requests as crequests
                st.caption("🚀 Ejecutando firma TLS pura (Chrome 120 sin alterar cabeceras) para Adidas...")
                # 🔥 CLAVE: No pasamos 'headers' customizados para no corromper la huella digital del navegador
                resp = crequests.get(url, impersonate="chrome120", timeout=15)
                texto_html = resp.text
                status_code = resp.status_code
            except ImportError:
                st.caption("⚠️ `curl_cffi` no detectado. Usando conector estándar...")
                resp = requests.get(url, headers={"User-Agent": random.choice(LISTA_USER_AGENTS)}, timeout=15, verify=False)
                texto_html = resp.text
                status_code = resp.status_code
            
            if status_code != 200:
                st.warning(f"⚠️ Adidas rechazó la conexión. Código HTTP: {status_code}.")
                return []
                
            texto_html = texto_html.replace('\xa0', ' ').replace('&nbsp;', ' ')
            soup = BeautifulSoup(texto_html, 'html.parser')
            
            # Buscador por Atributos Fijos del Servidor (data-testid)
            titulos_testid = soup.find_all(attrs={"data-testid": "product-card-title"})
            
            for tit_el in titulos_testid:
                try:
                    nombre_prod = tit_el.text.strip().upper()
                    if len(nombre_prod) < 3: 
                        continue
                    
                    ancestor = tit_el
                    oferta_el = None
                    regular_el = None
                    enlace_el = None
                    img_el = None
                    
                    for _ in range(5):
                        ancestor = ancestor.parent
                        if not ancestor: 
                            break
                        if not oferta_el: 
                            oferta_el = ancestor.find(attrs={"data-testid": "main-price"})
                        if not regular_el: 
                            regular_el = ancestor.find(attrs={"data-testid": "original-price"})
                        if not enlace_el: 
                            enlace_el = ancestor.find('a', href=True)
                        if not img_el: 
                            img_el = ancestor.find('img')
                            
                    if oferta_el:
                        precio_oferta = limpiar_precio_pnp(oferta_el.text)
                        precio_regular = limpiar_precio_pnp(regular_el.text) if regular_el else precio_oferta
                        
                        if 0 < precio_oferta <= limite:
                            enlace_final = urljoin(url, enlace_el['href']) if enlace_el else url
                            img_final = ""
                            if img_el:
                                img_final = img_el.get('data-src') or img_el.get('src') or ""
                                if img_final.startswith('//'): 
                                    img_final = 'https:' + img_final
                                
                            productos.append({
                                "nombre": f"ADIDAS - {nombre_prod}",
                                "precio": precio_oferta,
                                "precio_regular": max(precio_regular, precio_oferta),
                                "link": enlace_final,
                                "img": img_final
                            })
                except:
                    continue

            # Capa B: Respaldo por JSON Estructurado Interno
            if not productos:
                json_scripts = soup.find_all('script', type='application/ld+json')
                for script in json_scripts:
                    try:
                        script_content = script.text if script.text else (script.string if script.string else "")
                        js_data = json.loads(script_content)
                        elements = js_data.get("itemListElement", []) if isinstance(js_data, dict) else []
                        for element in elements:
                            item = element.get("item", {})
                            nombre_p = item.get("name", "").upper()
                            if len(nombre_p) < 3: continue
                            offers = item.get("offers", {})
                            p_o = safe_float(offers.get("lowPrice") or offers.get("price", 0))
                            if 0 < p_o <= limite:
                                productos.append({
                                    "nombre": f"ADIDAS - {nombre_p}",
                                    "precio": p_o,
                                    "precio_regular": safe_float(offers.get("highPrice", p_o)),
                                    "link": urljoin(url, item.get("url", "")),
                                    "img": item.get("image", "")
                                })
                        if productos: break
                    except: continue

            # Sistema de Control en Pantalla para Validación en Vivo
            if not productos:
                st.info(f"ℹ️ Diagnóstico Adidas: HTML recibido de forma limpia ({len(texto_html)} letras). Analizando estructura...")
                if len(texto_html) < 4000:
                    st.error("🚨 Alerta: Akamai devolvió un cascarón vacío. Se requiere reintentar para forzar rotación de IP.")
                    with st.expander("🔍 Ver fragmento del código"):
                        st.code(texto_html[:1000], language="html")
                    
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
