import os
import json
import requests
from bs4 import BeautifulSoup
import re
import time
import random
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse
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
    # MOTOR COBY-API EXCLUSIVO DE ADIDAS PERÚ (ANTI-AKAMAI)
    # -------------------------------------------------------
    elif "adidas" in url_low:
        try:
            parsed_url = urlparse(url)
            path_clean = parsed_url.path.strip("/")
            api_adidas = f"https://www.adidas.pe/api/plp/content-engine?sitePath={path_clean}"
            
            texto_html = ""
            status_code = 0
            
            try:
                from curl_cffi import requests as crequests
                st.caption("🚀 Simulando entorno TLS de Red Humana (Chrome HTTP/2) para Adidas...")
                resp = crequests.get(api_adidas, impersonate="chrome", timeout=15)
                texto_html = resp.text
                status_code = resp.status_code
            except ImportError:
                st.caption("⚠️ `curl_cffi` no detectado en entorno. Usando inyección estructural de cabeceras...")
                headers_full = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*",
                    "Accept-Language": "es-PE,es-419;q=0.9,es;q=0.8",
                    "Origin": "https://www.adidas.pe",
                    "Referer": f"https://www.adidas.pe/{path_clean}",
                    "Sec-Ch-Ua": '"Not/A)Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Sec-Fetch-Dest": "empty",
                    "Sec-Fetch-Mode": "cors",
                    "Sec-Fetch-Site": "same-origin",
                    "X-Requested-With": "XMLHttpRequest"
                }
                resp = requests.get(api_adidas, headers=headers_full, timeout=15, verify=False)
                texto_html = resp.text
                status_code = resp.status_code
            
            if status_code != 200:
                st.warning(f"⚠️ Adidas bloqueó la conexión automática. Código de estado HTTP: {status_code}. El firewall de Adidas (Akamai) rechazó el servidor.")
                return []
                
            try:
                data_json = json.loads(texto_html)
                items_raw = data_json.get("raw", {}).get("plpData", {}).get("results", [])
                
                for prod_json in items_raw:
                    try:
                        nombre_p = prod_json.get("title", "").upper()
                        if not nombre_p: 
                            continue
                        
                        p_o = float(prod_json.get("salePrice", 0) or prod_json.get("price", 0))
                        p_r = float(prod_json.get("price", p_o))
                        
                        if 0 < p_o <= limite:
                            link_f = urljoin("https://www.adidas.pe", prod_json.get("url", ""))
                            img_f = prod_json.get("image", {}).get("src", "")
                            
                            productos.append({
                                "nombre": f"ADIDAS - {nombre_p}",
                                "precio": p_o,
                                "precio_regular": p_r,
                                "link": link_f,
                                "img": img_f
                            })
                    except: 
                        continue
            except:
                # 🛠️ CORRECCIÓN DE ALINEACIÓN DE EXCEPT: Alineado al ras de su try
                soup = BeautifulSoup(texto_html, 'html.parser')
                for t in soup.find_all(['div', 'article', 'li', 'a'], class_=lambda x: x and any(k in x.lower() for k in ['product', 'card', 'item', 'grid'])):
                    try:
                        tit = t.find(['h3', 'h2', 'span', 'p', 'div', 'a'], class_=re.compile(r'(title|name|nombre|description)', re.I))
                        if not tit: 
                            continue
                        precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', t.text)
                        if precios:
                            p_o = float(precios[0].replace(',', '.'))
                            if p_o <= limite:
                                a_href = t.find('a', href=True)['href'] if t.find('a', href=True) else url
                                productos.append({"nombre": f"ADIDAS - {tit.text.strip().upper()}", "precio": p_o, "precio_regular": p_o, "link": urljoin(url, a_href), "img": ""})
                    except: 
                        continue
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
        
        st.write(f"🔄 **Patrullando Tienda:** `{ident.split('-')[0]}` | Categoría: *{grupo}*...")
        
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
                
                supabase.table("historial_precios").upsert({"identificador": f"{item['identificador']}-{n_u.replace(' ','_')}", "precio": p_v, "precio_regular": p_r, "link_producto": p['link'], "imagen_producto": p.get('img', ''), "fecha": fecha_hoy}).execute()
                
                if p_v < p_r:
                    emoji = mapa_emojis.get(grupo, "🔥")
                    msg_t = f"{emoji} <b>¡BAJÓ DE PRECIO! REMATE</b> {emoji}\n━━━━━━━━━━━━━━━━━━━━━\n\n📦 <b>Producto:</b> <code>{p['nombre']}</code>\n🏪 <b>Tienda:</b> <code>{ident.split('-')[0]}</code>\n❌ <b>Normal:</b> S/. {p_r:.2f}\n💰 <b>Oferta:</b> S/. {p_v:.2f}\n📉 <b>Ahorro:</b> S/. {(p_r - p_v):.2f}\n"
                    if enviar_telegram_real(msg_t, p['link'], p.get('img', '')): 
                        alertas += 1
            except: 
                pass
            
    return f"Éxito. Modelos procesados: {total}. Alertas Telegram: {alertas}."
