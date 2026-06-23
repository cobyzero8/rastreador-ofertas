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
    # MOTOR 2: MERCADO LIBRE (Fuerza Bruta por Enlaces)
    # =======================================================
    elif "mercadolibre.com" in url:
        for pagina in range(1, 4):
            url_paginada = url
            if pagina > 1:
                desde = ((pagina - 1) * 50) + 1
                if "_Desde_" in url: url_paginada = re.sub(r'_Desde_\d+', f'_Desde_{desde}', url)
                else:
                    if "/_" in url: url_paginada = url.replace("/_", f"_Desde_{desde}_")
                    elif "?" in url:
                        parts = url.split("?")
                        url_paginada = f"{parts[0]}_Desde_{desde}?{parts[1]}"
                    else: url_paginada = f"{url}_Desde_{desde}"
            try:
                resp = requests.get(url_paginada, headers=headers, timeout=15, verify=False)
                if resp.status_code != 200: break
                soup = BeautifulSoup(resp.text, 'html.parser')
                
                # Buscamos de forma masiva absolutamente todos los enlaces que apunten a un artículo real
                enlaces = soup.find_all('a', href=True)
                enlaces_productos = []
                for e in enlaces:
                    href = e['href']
                    # Filtro clave: Debe ser un link de producto y no repetirse en la lista temporal
                    if ('articulo.mercadolibre.com.pe' in href or '/p/MPE' in href) and href not in enlaces_productos:
                        enlaces_productos.append(href)
                
                if not enlaces_productos:
                    continue
                
                # Procesamos cada enlace recolectado de forma directa simulando su tarjeta
                for link in enlaces_productos:
                    try:
                        # Buscamos el contenedor más cercano al enlace para jalar su texto e imagen
                        ancestro = soup.find('a', href=link)
                        if not ancestro: continue
                        
                        # Subimos un nivel en el HTML para capturar el texto que rodea a este producto
                        contenedor_tarjeta = ancestro.find_parent(['div', 'li', 'article'])
                        texto_bloque = contenedor_tarjeta.text if contenedor_tarjeta else ancestro.text
                        
                        # Extracción agresiva de títulos (limpiamos textos raros)
                        titulo_limpio = "POLO ADIDAS IMPORTADO"
                        h_tit = contenedor_tarjeta.find(['h2', 'h3', 'p']) if contenedor_tarjeta else None
                        if h_tit: 
                            titulo_limpio = h_tit.text.strip().upper()
                        else:
                            # Si no hay cabecera, usamos las palabras clave de la URL del producto
                            slug = link.split('/')[3].replace('-', ' ').upper()
                            if len(slug) > 5 and not slug.startswith('MPE'): titulo_limpio = slug
                        
                        # Captura numérica del precio dentro de este bloque específico
                        precio = None
                        if contenedor_tarjeta:
                            # Buscamos la clase de fracción numérica que usa ML
                            fraccion = contenedor_tarjeta.select_one('.andes-money-amount__fraction, .poly-price__current .andes-money-amount__fraction')
                            if fraccion:
                                precio = float(fraccion.text.replace('.', '').replace(',', '').strip())
                        
                        if precio is None:
                            # Respaldo por expresiones regulares en el texto del bloque
                            numeros = re.findall(r'(?:S/\s*)(\d+)', texto_bloque)
                            if numeros: precio = float(numeros[0])
                            else: continue
                        
                        # Filtro por precio máximo
                        if 0 < precio <= limite:
                            img_src = ""
                            if contenedor_tarjeta:
                                img_el = contenedor_tarjeta.find('img')
                                if img_el:
                                    img_src = img_el.get('data-src', img_el.get('src', ''))
                            
                            productos.append({
                                "nombre": titulo_limpio,
                                "precio": precio,
                                "link": link,
                                "img": img_src
                            })
                    except: continue
                time.sleep(0.3)
            except: break
            
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
