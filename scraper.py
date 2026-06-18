import os
import json
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime
from urllib.parse import urljoin
from supabase import create_client, Client

# --- CONFIGURACIÓN DE ÉLITE MULTI-ENTORNO ---
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"

SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY")
if not SUPABASE_KEY:
    try:
        import streamlit as st
        SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    except:
        pass

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

def enviar_telegram(mensaje, url_compra, url_foto):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendPhoto"
    payload = {
        "chat_id": CHAT_ID_TELEGRAM,
        "photo": url_foto if url_foto else "https://via.placeholder.com/150",
        "caption": mensaje,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps({"inline_keyboard": [[{"text": "🛒 Comprar Aquí", "url": url_compra}]]})
    }
    requests.post(url, json=payload, timeout=10)

def escanear_tienda(url, limite):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9"
    }
    productos = []
    url_clean = str(url).strip().lower()

    # =========================================================
    # 🕵️‍♂️ TIENDAS BELCORP (CYZONE, LBEL, ESIKA) - SIN SILENCIADOR
    # =========================================================
    if "tiendabelcorp" in url_clean or "cyzone" in url_clean or "lbel" in url_clean or "esika" in url_clean:
        marca = "cyzone" if "cyzone" in url_clean else "lbel" if "lbel" in url_clean else "esika"
        api_url = f"https://api.tiendabelcorp.com.pe/v2/products/search/{marca}/PE"
        params = {
            "category": "perfumes",
            "page": 1,
            "pageSize": 20,
            "sort": "price_asc"
        }
        resp = requests.get(api_url, headers=headers, params=params, timeout=15)
        resp.raise_for_status() # 🚨 Rompe la app si Belcorp da error 403 o 404
        
        data = resp.json()
        for p in data.get("products", []):
            nombre = p.get("name", "Perfume Belcorp")
            precio = float(p.get("price", {}).get("value", 999))
            link_rel = p.get("urlKey", "")
            link_completo = f"https://{marca}.tiendabelcorp.com.pe/{link_rel}/p"
            img_url = p.get("images", [{}])[0].get("url", "")
            productos.append({"nombre": f"{marca.upper()} - {nombre}", "precio": precio, "link": link_completo, "img": img_url})

    # =========================================================
    # 🕵️‍♂️ TIENDA NATURA PERÚ - SIN SILENCIADOR
    # =========================================================
    elif "natura" in url_clean:
        tipo_perfume = "perfumeria-masculina" if "perfumeria-masculina" in url_clean else "perfumeria-femenina"
        api_url = "https://www.natura.com.pe/api/catalog_system/pub/products/search"
        params = {"ft": tipo_perfume, "_from": 0, "_to": 20, "O": "OrderByPriceASC"}
        
        resp = requests.get(api_url, headers=headers, params=params, timeout=15)
        resp.raise_for_status() # 🚨 Rompe la app si Natura te bloquea
        
        items = resp.json()
        for item in items:
            nombre = item.get("productName", "Perfume Natura")
            link_completo = item.get("link", url)
            
            img_url = ""
            items_internos = item.get("items", [])
            if items_internos and items_internos[0].get("images"):
                img_url = items_internos[0]["images"][0].get("imageUrl", "")
            
            precio = 999.0
            if items_internos and items_internos[0].get("sellers"):
                comm_offer = items_internos[0]["sellers"][0].get("commertialOffer", {})
                precio = float(comm_offer.get("Price", 999.0))
            
            productos.append({
                "nombre": f"NATURA - {nombre.upper()}",
                "precio": precio,
                "link": link_completo,
                "img": img_url
            })

    # =========================================================
    # 👟 COMODÍN: SAGA, MARATHON, ADIDAS, ETC.
    # =========================================================
    else:
        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')
        for t in soup.find_all('div', class_=lambda x: x and ('product' in x or 'card' in x)):
            tit = t.find(['h3', 'h2', 'span', 'p'], class_=re.compile(r'(title|name)', re.I))
            if not tit: continue
            nombre = tit.text.strip()
            a = t.find('a', href=True)
            link = urljoin(url, a['href']) if a else url
            img = t.find('img', src=True)
            img_url = img['src'] if img else ""
            precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', t.text)
            valores = sorted([float(p.replace(',', '.')) for p in precios if float(p.replace(',', '.')) > 2])
            if valores:
                productos.append({"nombre": nombre, "precio": valores[0], "link": link, "img": img_url})

    return productos

def revisar_ofertas():
    # Dejamos libre este bloque para capturar el error exacto en el Dashboard
    res = supabase.table("radares").select("*").execute()
    if not res or not res.data:
        return
    
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    for item in res.data:
        identificador = str(item['identificador']).strip()
        limite = float(item['precio_max'])
        url_radar = str(item['url']).strip().lower()
        
        parts = identificador.split("-")
        tienda_txt = parts[0].upper() if len(parts) > 0 else "TIENDA"
        cat_txt = parts[1].upper() if len(parts) > 1 else "OTROS"
        talla_txt = parts[3] if len(parts) > 3 else "Todas"
        
        prods = escanear_tienda(item['url'], limite)
        
        if prods:
            # Tomamos el precio más bajo encontrado en la página para el historial
            precio_actual = prods[0]['precio']
            
            # 📈 REGISTRO AUTOMÁTICO EN LA NUEVA TABLA DE SUPABASE
            try:
                supabase.table("historial_precios").insert({
                    "identificador": identificador,  # 🛑 ¡AQUÍ ESTÁ EL ERROR!
                    "precio": precio_actual,
                    "fecha": fecha_hoy
                }).execute()
            except: pass
                
                    
                    # Forzamos la inserción libre sin silenciador
                    supabase.table("historial_precios").insert({
                        "identificador": id_registro_dashboard, 
                        "precio": p['precio'],
                        "fecha": fecha_hoy
                    }).execute()
                    
                    ahorro = limite - p['precio']
                    porcentaje = (ahorro / limite) * 100 if limite > 0 else 0
                    
                    msg = (
                        f"🔥 *¡OFERTA DETECTADA POR COBY!* 🔥\n"
                        f"━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📦 *Producto:* {p['nombre']}\n"
                        f"🏪 *Tienda:* `{tienda_txt}`\n"
                        f"🏷️ *Categoría:* `{cat_txt}`\n\n"
                        f"💵 *Precio Actual:* `S/. {p['precio']:.2f}`\n"
                        f"🎯 *Tu Precio Límite:* `S/. {limite:.2f}`\n"
                    )
                    
                    if p['precio'] < limite:
                        msg += f"📉 *¡Te estás ahorrando:* S/. {ahorro:.2f} ({porcentaje:.1f}% menos)!\n"
                    else:
                        msg += f"⚖️ *¡Llegó a tu precio objetivo exacto!*\n"
                        
                    msg += f"\n🚨 _¡Aprovecha antes de que vuele el stock!_"
                    
                    enviar_telegram(msg, p['link'], p['img'])
                    time.sleep(0.5)
