import os
import json
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin
from supabase import create_client, Client
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =======================================================
# INICIALIZACIÓN GLOBAL BLINDADA DE SUPABASE
# =======================================================
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

try:
    import streamlit as st
    if "SUPABASE_KEY" in st.secrets: 
        SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except: 
    pass

if SUPABASE_URL and SUPABASE_KEY:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
else:
    raise ValueError("Error crítico: No se encontró la SUPABASE_KEY en el entorno ni en Secrets.")

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
# NÚCLEO DE EXTRACCIÓN DE TIENDAS
# =======================================================
def escanear_tienda(url, limite):
    productos = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"}
    url_low = url.lower()

    # -------------------------------------------------------
    # MOTOR 1: BELCORP (Cyzone, L'Bel, Ésika)
    # -------------------------------------------------------
    if any(k in url_low for k in ["tiendabelcorp", "cyzone", "lbel", "esika"]):
        marca = "cyzone" if "cyzone" in url_low else "lbel" if "lbel" in url_low else "esika"
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
                        "precio": precio_oferta, "precio_regular": precio_regular,
                        "link": item["link"], "img": item["items"][0]["images"][0]["imageUrl"]
                    })
        except: pass

    # -------------------------------------------------------
    # MOTOR 2: CONECTA RETAIL (¡Efe y La Curacao!)
    # -------------------------------------------------------
    elif "efe.com.pe" in url_low or "lacuracao.pe" in url_low:
        tienda_tag = "EFE" if "efe.com.pe" in url_low else "CURACAO"
        try:
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
                                "precio": precio_oferta, "precio_regular": precio_regular, 
                                "link": enlace_final, "img": img_final
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

# =======================================================
# SISTEMA DE PATRULLAJE DE OFERTAS
# =======================================================
def revisar_ofertas(filtro_objetivo="TODOS"):
    try:
        res = supabase.table("radares").select("*").execute()
    except Exception as e:
        import streamlit as st
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
    
    # Zona horaria de Perú (UTC-5)
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
                
                # Identificador ÚNICO por producto para que no se pisen en el Dashboard
                nombre_slug = nombre_unico.replace(" ", "_").replace("-", "_")
                id_producto_unico = f"{item['identificador']}-{nombre_slug}"
                
                payload = {
                    "identificador": id_producto_unico,
                    "precio": float(p['precio']), 
                    "fecha": fecha_hoy
                }
                
                # Guardamos/Actualizamos en la base de datos
                supabase.table("historial_precios").upsert(payload).execute()
                
                # --- SISTEMA DE ALERTAS (TELEGRAM) ---
                try:
                    from scraper import enviar_telegram
                except:
                    def enviar_telegram(msg, link, img): pass
                
                emoji = mapa_emojis.get(grupo, "🔥")
                text_alerta = f"{emoji} *PRODUCTO EN TU RANGO* {emoji}\n"
                text_alerta += f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                text_alerta += f"📦 *Producto:* `{p['nombre']}`\n"
                text_alerta += f"🏪 *Tienda:* `{ident.split('-')[0]}`\n"
                text_alerta += f"🏷️ *Categoría:* `{grupo}`\n"
                text_alerta += f"💵 *Precio Actual:* `S/. {p['precio']:.2f}`\n"
                text_alerta += f"🎯 *Tu Tope:* `S/. {item['precio_max']:.2f}`\n"
                
                try:
                    enviar_telegram(text_alerta, p['link'], p.get('img', ''))
                    alertas_enviadas += 1
                    time.sleep(0.4)
                except:
                    pass
                    
            except Exception as e:
                import streamlit as st
                st.error(f"Error procesando ítem: {e}")
                
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
