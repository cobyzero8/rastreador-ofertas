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

    # =======================================================
    # MOTOR 2: JBL Y SAMSUNG
    # =======================================================
    elif "jbl." in url or "samsung." in url:
        try:
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                items = soup.select('.product-tile') or soup.select('[class*="product-item"]') or soup.select('[class*="productCard"]')
                if not items:
                    items = soup.find_all(['div', 'article'], class_=re.compile(r'(product|card|item|tile)', re.I))
                
                for t in items:
                    try:
                        tit_el = t.select_one('.pdp-link a') or t.find(['h2', 'h3', 'h1', 'span', 'p'], class_=re.compile(r'(title|name|nombre)', re.I))
                        if not tit_el: continue
                        nombre_prod = tit_el.text.strip().upper()
                        if len(nombre_prod) < 5: continue
                        
                        # Captura precio de lista viejo (regular) vs el de venta (oferta)
                        reg_el = t.select_one('.price .list .value') or t.select_one('[class*="list-price"]') or t.select_one('del')
                        precio_el = t.select_one('.price .sales .value') or t.select_one('.sales') or t.select_one('[class*="price"]')
                        
                        raw_txt_oferta = precio_el.text if precio_el else t.text
                        precios_oferta = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', raw_txt_oferta)
                        if not precios_oferta: precios_oferta = re.findall(r'\b\d{2,4}\.\d{2}\b', raw_txt_oferta)
                            
                        if precios_oferta:
                            p_of = precios_oferta[0].replace('.', '').replace(',', '.') if ',' in precios_oferta[0] and '.' in precios_oferta[0] else precios_oferta[0].replace(',', '.')
                            precio_oferta = float(p_of)
                            
                            # Intentar sacar el regular, si no hay, es igual al de oferta
                            precio_regular = precio_oferta
                            if reg_el:
                                precios_reg = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', reg_el.text)
                                if precios_reg:
                                    p_rg = precios_reg[0].replace('.', '').replace(',', '.') if ',' in precios_reg[0] and '.' in precios_reg[0] else precios_reg[0].replace(',', '.')
                                    precio_regular = float(p_rg)
                            
                            if 0 < precio_oferta <= limite:
                                link_el = t.find('a', href=True)
                                enlace_final = urljoin(url, link_el['href']) if link_el else url
                                img_el = t.find('img')
                                img_final = ""
                                if img_el:
                                    img_final = img_el.get('data-src') or img_el.get('src') or ''
                                    if img_final.startswith('//'): img_final = 'https:' + img_final
                                
                                productos.append({
                                    "nombre": f"JBL - {nombre_prod}", "precio": precio_oferta, "precio_regular": precio_regular, "link": enlace_final, "img": img_final
                                })
                    except: continue
        except: pass

    # =======================================================
    # MOTOR 3: PLATANITOS Y TRADICIONALES
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
                        
                        # Platanitos a veces mete el precio antiguo en etiquetas <del> o clases 'regular'
                        del_el = t.find(['del', 'span'], class_=re.compile(r'(regular|original|old)', re.I))
                        
                        precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', t.text)
                        if precios:
                            precio_oferta = float(precios[0].replace(',', '.'))
                            precio_regular = precio_oferta
                            
                            if del_el:
                                precios_del = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', del_el.text)
                                if precios_del: precio_regular = float(precios_del[0].replace(',', '.'))
                            elif len(precios) > 1:
                                # Si re.findall pescó más de un precio en el texto de la tarjeta, por lo general el mayor es el de lista
                                precios_float = [float(pr.replace(',', '.')) for pr in precios]
                                precio_regular = max(precios_float)
                                precio_oferta = min(precios_float)
                            
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
                                    "nombre": tit.text.strip().upper(), "precio": precio_oferta, "precio_regular": precio_regular, "link": enlace_final, "img": img['src'] if img else ""
                                })
                    except: continue
                time.sleep(0.3)
            except: break
    return productos

def revisar_ofertas(filtro_objetivo="TODOS"):
    res = supabase.table("radares").select("*").execute()
    if not res or not res.data: return "Sin radares activos."
    
    total = 0
    alertas_enviadas = 0
    lista_html_streamlit = []
    mapa_emojis = {"PERFUMES": "🧪", "ZAPATILLAS": "👟", "TECNOLOGIA": "📺", "MEDIAS": "🧦", "POLOS": "👕", "CASACAS": "🧥", "SHORTS": "🩳", "BUZOS": "👖", "OTROS": "📦"}
    enviados_en_este_clic = set()
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    target = str(filtro_objetivo).strip().upper()
    
    for item in res.data:
        ident = item['identificador'].upper()
        
        if "PERFUME" in ident: grupo = "PERFUMES"
        elif "ZAPATILLA" in ident: grupo = "ZAPATILLAS"
        elif "TECNOLOGIA" in ident or "TV" in ident or "JBL" in ident or "SAMSUNG" in ident: grupo = "TECNOLOGIA"
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
                
                lista_html_streamlit.append(p)
                total += 1
                
                # Control anti-spam de Telegram
                ya_alertado = False
                try:
                    check = supabase.table("historial_precios")\
                        .select("id")\
                        .eq("identificador", item['identificador'])\
                        .eq("precio", p['precio'])\
                        .eq("fecha", fecha_hoy)\
                        .execute()
                    if check.data and len(check.data) > 0:
                        ya_alertado = True
                except: pass
                
                supabase.table("historial_precios").insert({
                    "identificador": item['identificador'], "precio": p['precio'], "fecha": fecha_hoy
                }).execute()
                
                if ya_alertado:
                    continue
                
                # Telegram
                emoji = mapa_emojis.get(grupo, "🔥")
                text_alerta = f"{emoji} *PRODUCTO EN TU RANGO* {emoji}\n"
                text_alerta += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                text_alerta += f"📦 *Producto:* `{p['nombre']}`\n"
                text_alerta += f"🏪 *Tienda:* `{ident.split('-')[0]}`\n"
                text_alerta += f"💵 *Precio Actual:* `S/. {p['precio']:.2f}`\n"
                text_alerta += f"🎯 *Tu Tope:* `S/. {item['precio_max']:.2f}`\n"
                enviar_telegram(text_alerta, p['link'], p.get('img', ''))
                alertas_enviadas += 1
                time.sleep(0.4)
            except: pass
            
    # MOSTRAR EN STREAMLIT CON CÁLCULO DE DESCUENTOS EN TIEMPO REAL
    if len(lista_html_streamlit) > 0:
        try:
            import streamlit as st
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
                        
                        # Si el precio regular detectado es mayor al de oferta, calculamos la rebaja
                        if p_regular > p_oferta:
                            ahorro_soles = p_regular - p_oferta
                            porcentaje = (ahorro_soles / p_regular) * 100
                            
                            st.markdown(f"❌ ~~Precio Regular: S/. {p_regular:.2f}~~")
                            st.markdown(f"💰 **Precio Oferta: S/. {p_oferta:.2f}**")
                            st.markdown(f"🔥 **¡Ahorraste S/. {ahorro_soles:.2f}! ({porcentaje:.0f}% de Descuento)**")
                        else:
                            st.markdown(f"💰 **Precio Actual: S/. {p_oferta:.2f}**")
                            st.caption("ℹ️ _La tienda no reporta precio regular anterior, o se encuentra a precio de etiqueta original._")
                            
                        st.markdown(f"🔗 [🌐 IR A COMPRAR DIRECTO EN LA TIENDA]({prod['link']})")
        except: pass

    return f"Éxito. Modelos únicos: {total}. Alertas enviadas a Telegram: {alertas_enviadas}."
