import os
import json
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime
from urllib.parse import urljoin
from supabase import create_client, Client
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
try:
    import streamlit as st
    if "SUPABASE_KEY" in st.secrets: SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except: pass
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def enviar_telegram(mensaje, url_compra, url_foto):
    TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
    CHAT_ID_TELEGRAM = "8019752668"
    url_api = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendPhoto"
    
    payload = {
        "chat_id": CHAT_ID_TELEGRAM,
        "photo": url_foto if url_foto else "https://via.placeholder.com/150",
        "caption": mensaje,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps({"inline_keyboard": [[{"text": "🛒 IR A LA OFERTA", "url": url_compra}]]})
    }
    try:
        r = requests.post(url_api, json=payload, timeout=12, verify=False)
        if r.status_code != 200:
            url_text = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
            requests.post(url_text, json={
                "chat_id": CHAT_ID_TELEGRAM,
                "text": mensaje + f"\n\n🛒 [Ir a la Tienda]({url_compra})",
                "parse_mode": "Markdown"
            }, timeout=10, verify=False)
    except: pass

def escanear_tienda(url, limite):
    productos = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}

    # =======================================================
    # MOTOR 1: BELCORP
    # =======================================================
    if any(k in url for k in ["tiendabelcorp", "cyzone", "lbel", "esika"]):
        marca = "cyzone" if "cyzone" in url else "lbel" if "lbel" in url else "esika"
        api_url = f"https://{marca}.tiendabelcorp.com.pe/api/catalog_system/pub/products/search"
        params = {"ft": "perfume", "_from": 0, "_to": 20, "O": "OrderByPriceASC"}
        try:
            resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False)
            for item in resp.json():
                precio = float(item["items"][0]["sellers"][0]["commertialOffer"]["Price"])
                if 0 < precio <= limite:
                    productos.append({"nombre": f"{marca.upper()} - {item['productName'].upper()}", "precio": precio, "link": item["link"], "img": item["items"][0]["images"][0]["imageUrl"]})
        except: pass

    # =======================================================
    # MOTOR 2: TRIATHLON (Inyección y Lectura de JSON Interno)
    # =======================================================
    elif "triathlon." in url:
        try:
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Buscamos el script oculto de VTEX que contiene toda la base de datos de la página
                script_vtex = soup.find('script', text=re.compile(r'__STATE__'))
                if script_vtex:
                    raw_json = re.search(r'__STATE__\s*=\s*({.+})', script_vtex.string)
                    if raw_json:
                        data = json.loads(raw_json.group(1))
                        
                        # Agrupamos los datos por productos
                        productos_dict = {}
                        precios_dict = {}
                        
                        for llave, valor in data.items():
                            # 1. Extraer Nombres, Enlaces y Marcas
                            if llave.startswith("Product:") and "productName" in valor:
                                prod_id = llave.split(":")[1]
                                productos_dict[prod_id] = {
                                    "nombre": f"{valor.get('brand', '').upper()} - {valor.get('productName', '').upper()}",
                                    "link": urljoin(url, valor.get('linkText', '') + "/p")
                                }
                            
                            # 2. Extraer Precios de Oferta Reales
                            if "Price" in llave and valor.get("Price") is not None:
                                # Buscar a qué item pertenece
                                parent_key = llave.split(".")[0]
                                if parent_key in data:
                                    # Caminar hacia arriba en el JSON para encontrar el ID del producto
                                    precios_dict[parent_key] = float(valor["Price"])

                        # Cruzar la información y filtrar por precio límite
                        for llave, valor in data.items():
                            if llave.startswith("Product:") and "items" in valor:
                                prod_id = llave.split(":")[1]
                                if prod_id in productos_dict:
                                    for item_ref in valor.get("items", []):
                                        item_id = item_ref.get("id")
                                        # Buscar precio en los sellers de este item
                                        for k, v in data.items():
                                            if item_id in k and "commertialOffer" in k:
                                                offer = data.get(k, {})
                                                precio = float(offer.get("Price", 9999))
                                                
                                                if 0 < precio <= limite:
                                                    # Buscar imagen
                                                    img_url = ""
                                                    images = offer.get("images", [])
                                                    if images:
                                                        img_obj = data.get(images[0]["id"])
                                                        if img_obj: img_url = img_obj.get("imageUrl", "")
                                                    
                                                    prod_final = productos_dict[prod_id]
                                                    productos.append({
                                                        "nombre": prod_final["nombre"],
                                                        "precio": precio,
                                                        "link": prod_final["link"],
                                                        "img": img_url
                                                    })
                
                # --- PLAN B: Si el script cambia, usamos un fallback clásico ---
                if not productos:
                    items = soup.select('.vtex-product-summary-2-x-container, [class*="productSummary"]')
                    for t in items:
                        try:
                            tit_el = t.select_one('[class*="productName"], h2, h3')
                            precio_el = t.select_one('[class*="sellingPriceValue"], [class*="price-value"]')
                            if tit_el and precio_el:
                                numeros = re.findall(r'\d+[\.,]\d{2}|\d+', precio_el.text)
                                if numeros:
                                    precio = float(numeros[0].replace(',', '.'))
                                    if 0 < precio <= limite:
                                        link_el = t.find('a', href=True)
                                        productos.append({
                                            "nombre": tit_el.text.strip().upper(),
                                            "precio": precio,
                                            "link": urljoin(url, link_el['href']) if link_el else url,
                                            "img": ""
                                        })
                        except: pass
        except: pass

    # =======================================================
    # MOTOR 3: PLATANITOS
    # =======================================================
    else:
        for pagina in range(1, 4):
            url_paginada = url
            if "platanitos.com" in url:
                conector = "&" if "?" in url else "?"
                url_paginada = f"{url}{conector}page={pagina}"
            try:
                resp = requests.get(url_paginada, headers=headers, timeout=15, verify=False)
                if resp.status_code not in [200, 206]: break
                soup = BeautifulSoup(resp.text, 'html.parser')
                items = soup.find_all(['div', 'article', 'li', 'a'], class_=lambda x: x and any(k in x.lower() for k in ['product', 'card', 'item', 'grid', 'element']))
                if not items: break
                
                for t in items:
                    try:
                        tit = t.find(['h3', 'h2', 'span', 'p', 'div', 'a'], class_=re.compile(r'(title|name|nombre|description)', re.I))
                        if not tit or len(tit.text.strip()) < 3: continue
                        
                        precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', t.text)
                        if precios:
                            precio = float(precios[0].replace(',', '.'))
                            if precio <= limite:
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
                                productos.append({"nombre": tit.text.strip().upper(), "precio": precio, "link": enlace_final, "img": img['src'] if img else ""})
                    except: continue
                time.sleep(0.3)
            except: break
    return productos

def revisar_ofertas(filtro_objetivo="TODOS"):
    res = supabase.table("radares").select("*").execute()
    if not res or not res.data: return "Sin radares activos."
    
    total = 0
    alertas_enviadas = 0
    mapa_emojis = {"PERFUMES": "🧪", "ZAPATILLAS": "👟", "TECNOLOGIA": "📺", "MEDIAS": "🧦", "POLOS": "👕", "CASACAS": "🧥", "SHORTS": "🩳", "BUZOS": "👖", "OTROS": "📦"}
    enviados_en_este_clic = set()
    
    target = str(filtro_objetivo).strip().upper()
    
    for item in res.data:
        ident = item['identificador'].upper()
        
        if "PERFUME" in ident: grupo = "PERFUMES"
        elif "ZAPATILLA" in ident: grupo = "ZAPATILLAS"
        elif "TECNOLOGIA" in ident or "TV" in ident: grupo = "TECNOLOGIA"
        elif "MEDIAS" in ident: grupo = "MEDIAS"
        elif "POLOS" in ident: grupo = "POLOS"
        elif "CASACAS" in ident: grupo = "CASACAS"
        elif "SHORTS" in ident: grupo = "SHORTS"
        elif "BUZOS" in ident: grupo = "BUZOS"
        else: grupo = "OTROS"
        
        if target != "TODOS" and target != grupo:
            continue
        
        prods = escanear_tienda(item['url'], item['precio_max'])
        for p in prods:
            try:
                nombre_unico = p['nombre'].strip().upper()
                if nombre_unico in enviados_en_este_clic: continue
                enviados_en_este_clic.add(nombre_unico)
                
                fecha_hoy = datetime.now().strftime("%Y-%m-%d")
                supabase.table("historial_precios").insert({
                    "identificador": item['identificador'], 
                    "precio": p['precio'], 
                    "fecha": fecha_hoy
                }).execute()
                total += 1
                
                emoji = mapa_emojis.get(grupo, "🔥")
                text_alerta = f"{emoji} *PRODUCTO DISPONIBLE EN TU RANGO* {emoji}\n"
                text_alerta += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                text_alerta += f"📦 *Producto:* `{p['nombre']}`\n"
                text_alerta += f"🏪 *Tienda:* `{ident.split('-')[0]}`\n"
                text_alerta += f"🏷️ *Categoría:* `{grupo}`\n\n"
                text_alerta += f"💵 *Precio Actual:* `S/. {p['precio']:.2f}`\n"
                text_alerta += f"🎯 *Tu Tope:* `S/. {item['precio_max']:.2f}`\n\n"
                text_alerta += f"🚨 _¡Revisa si te gusta el modelo!_"
                
                enviar_telegram(text_alerta, p['link'], p.get('img', ''))
                alertas_enviadas += 1
                time.sleep(0.4)
            except: pass
            
    return f"Éxito. Modelos únicos: {total}. Alertas enviadas: {alertas_enviadas}."
