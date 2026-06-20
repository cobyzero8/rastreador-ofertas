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

# --- CONFIGURACIÓN DE ÉLITE ---
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY")
if not SUPABASE_KEY:
    try:
        import streamlit as st
        SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    except Exception:
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
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception:
        pass

def escanear_tienda(url, limite):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9"
    }
    productos = []
    url_clean = str(url).strip().lower()

    # --- BLOQUE BELCORP (ESIKA/CYZONE/LBEL) ---
    if "tiendabelcorp" in url_clean or "cyzone" in url_clean or "lbel" in url_clean or "esika" in url_clean:
        marca = "cyzone" if "cyzone" in url_clean else "lbel" if "lbel" in url_clean else "esika"
        api_url = f"https://{marca}.tiendabelcorp.com.pe/api/catalog_system/pub/products/search"
        params = {"ft": "perfume", "_from": 0, "_to": 20, "O": "OrderByPriceASC"}
        
        try:
            resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False)
            if resp.status_code == 200:
                for item in resp.json():
                    nombre = item.get("productName", "Perfume Belcorp")
                    img_url = item["items"][0]["images"][0]["imageUrl"] if item.get("items") and item["items"][0].get("images") else ""
                    precio = float(item["items"][0]["sellers"][0]["commertialOffer"]["Price"]) if item.get("items") and item["items"][0].get("sellers") else 999.0
                    productos.append({"nombre": f"{marca.upper()} - {nombre.upper()}", "precio": precio, "link": item.get("link", url), "img": img_url})
        except Exception as e:
            print(f"Error Belcorp: {e}")

    # --- COMODÍN GENERAL (PLATANITOS, MIFARMA, ETC) ---
    else:
        try:
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for t in soup.find_all('div', class_=lambda x: x and ('product' in x or 'card' in x or 'item' in x)):
                tit = t.find(['h3', 'h2', 'span', 'p'], class_=re.compile(r'(title|name|nombre)', re.I))
                if not tit: continue
                precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', t.text)
                valores = sorted([float(p.replace(',', '.')) for p in precios if float(p.replace(',', '.')) > 2])
                if valores:
                    a = t.find('a', href=True)
                    img = t.find('img', src=True)
                    productos.append({"nombre": tit.text.strip().upper(), "precio": valores[0], "link": urljoin(url, a['href']) if a else url, "img": img['src'] if img else ""})
        except Exception as e:
            print(f"Error General: {e}")

    return productos

def revisar_ofertas(categoria_filtro="TODOS"):
    res = supabase.table("radares").select("*").execute()
    if not res or not res.data:
        return
    
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    filtro_web = str(categoria_filtro).upper().strip()
    
    for item in res.data:
        identificador = str(item['identificador']).strip()
        limite = float(item['precio_max'])
        url_radar = str(item['url']).strip().lower()
        
        parts = identificador.split("-")
        tienda_txt = parts[0].upper()
        cat_txt = parts[1].upper() # PERFUMES, ZAPATILLAS, SHAMPOO
        talla_txt = parts[3] if len(parts) > 3 else "Todas"
        
        # MAPEO EXACTO AL BOTÓN
        grupo_sistema = "OTROS"
        if cat_txt == "ZAPATILLAS": grupo_sistema = "ZAPATILLAS"
        elif cat_txt == "PERFUMES": grupo_sistema = "PERFUMES"
        elif cat_txt == "SHAMPOO": grupo_sistema = "CUIDADO_PERSONAL"
        elif cat_txt == "TV": grupo_sistema = "TECNOLOGIA"
        elif cat_txt == "ROPA": grupo_sistema = "ROPA"

        # BLOQUEO: Si el botón tocado no coincide con el grupo del radar, lo salta.
        if filtro_web != "TODOS" and filtro_web != grupo_sistema:
            continue

        prods = escanear_tienda(item['url'], limite)
        
        if prods:
            for p in prods:
                # Para Perfumes, guardamos su nombre real para que no se sobreescriban
                if grupo_sistema == "PERFUMES":
                    nombre_limpio = str(p['nombre']).upper().replace(" ", "_").replace("-", "_").replace("Á","A").replace("É","E").replace("Í","I").replace("Ó","O").replace("Ú","U")
                    id_registro_dashboard = f"{tienda_txt}-PERFUMES-{nombre_limpio}-{talla_txt}"
                else:
                    id_registro_dashboard = identificador
                
                try:
                    supabase.table("historial_precios").insert({"identificador": id_registro_dashboard, "precio": p['precio'], "fecha": fecha_hoy}).execute()
                except Exception:
                    pass
                
                if p['precio'] <= limite:
                    ahorro = limite - p['precio']
                    porcentaje = (ahorro / limite) * 100 if limite > 0 else 0
                    msg = (f"🔥 *¡OFERTA DETECTADA POR COBY!* 🔥\n━━━━━━━━━━━━━━━━━━━\n\n📦 *Producto:* {p['nombre']}\n🏪 *Tienda:* `{tienda_txt}`\n🏷️ *Categoría:* `{cat_txt}`\n\n💵 *Precio Actual:* `S/. {p['precio']:.2f}`\n🎯 *Tu Precio Límite:* `S/. {limite:.2f}`\n")
                    if p['precio'] < limite: msg += f"📉 *¡Te estás ahorrando:* S/. {ahorro:.2f} ({porcentaje:.1f}% menos)!\n"
                    else: msg += f"⚖️ *¡Llegó a tu precio objetivo exacto!*\n"
                    msg += f"\n🚨 _¡Aprovecha antes de que vuele el stock!_"
                    enviar_telegram(msg, p['link'], p['img'])
                    time.sleep(0.5)
