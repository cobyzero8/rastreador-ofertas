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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}

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
                                    if any(x in href_test for x in ['cat=', 'brand=', 'filter=', 'javascript', 'productos?']):
                                        continue
                                    if 'detalle' in href_test or 'producto' in href_test:
                                        a_href = enlace['href']
                                        break
                                    a_href = enlace['href']
                                
                                if not a_href and enlaces_internos:
                                    a_href = enlaces_internos[0]['href']
                                if not a_href and t.name == 'a' and t.has_attr('href'):
                                    a_href = t['href']
                                    
                                if a_href and 'productos?' in a_href.lower():
                                    continue
                                    
                                enlace_final = urljoin(url, a_href) if a_href else url
                                img = t.find('img', src=True)
                                
                                # Guardamos todo lo que encontremos en esta página
                                productos.append({"nombre": tit.text.strip().upper(), "precio": precio, "link": enlace_final, "img": img['src'] if img else ""})
                    except: 
                        continue
                time.sleep(0.3)
            except: 
                break
    return productos

def revisar_ofertas(categoria_filtro="TODOS", sub_ropa_filtro="TODOS"):
    res = supabase.table("radares").select("*").execute()
    if not res or not res.data: return "Sin radares activos."
    
    total = 0
    alertas_enviadas = 0
    mapa_emojis = {"PERFUMES": "🧪", "ZAPATILLAS": "👟", "TECNOLOGIA": "📺", "ROPA": "👕", "OTROS": "📦"}
    
    # --- MEMORIA CORTA DE ESTE ESCANEO ---
    # Usaremos un conjunto (set) para recordar los nombres de productos que ya mandamos en este clic
    enviados_en_este_clic = set()
    
    for item in res.data:
        ident = item['identificador'].upper()
        if "PERFUME" in ident: grupo = "PERFUMES"
        elif "ZAPATILLA" in ident: grupo = "ZAPATILLAS"
        elif "TECNOLOGIA" in ident or "TV" in ident: grupo = "TECNOLOGIA"
        elif "ROPA" in ident: grupo = "ROPA"
        else: grupo = "OTROS"
        
        if categoria_filtro != "TODOS" and categoria_filtro != grupo: 
            continue
        if grupo == "ROPA" and categoria_filtro == "ROPA":
            if sub_ropa_filtro != "TODOS" and sub_ropa_filtro not in ident: 
                continue
        
        prods = escanear_tienda(item['url'], item['precio_max'])
        for p in prods:
            try:
                nombre_unico = p['nombre'].strip().upper()
                
                # --- NUEVO FILTRO ANTIDUPLICADOS INTERNO ---
                # Si el nombre del polo ya está en nuestra lista de enviados de este clic, lo saltamos
                if nombre_unico in enviados_en_este_clic:
                    continue
                
                # Si es un modelo nuevo en este escaneo, lo agregamos a la memoria para que no se repita
                enviados_en_este_clic.add(nombre_unico)
                
                # Guardamos registro histórico en Supabase
                fecha_hoy = datetime.now().strftime("%Y-%m-%d")
                supabase.table("historial_precios").insert({
                    "identificador": item['identificador'], 
                    "precio": p['precio'], 
                    "fecha": fecha_hoy
                }).execute()
                total += 1
                
                # Enviamos el mensaje limpio a Telegram
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
