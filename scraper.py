import os
import json
import requests
from bs4 import BeautifulSoup
import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs
from supabase import create_client, Client

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURACIÓN DE ÉLITE SEGURA ---
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
    try: requests.post(url, json=payload, timeout=10)
    except: pass

def escanear_tienda(url, limite):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9"
    }
    productos = []
    url_clean = str(url).strip().lower()

    # --- BELCORP ---
    if "tiendabelcorp" in url_clean or "cyzone" in url_clean or "lbel" in url_clean or "esika" in url_clean:
        marca = "cyzone" if "cyzone" in url_clean else "lbel" if "lbel" in url_clean else "esika"
        api_url = f"https://{marca}.tiendabelcorp.com.pe/api/catalog_system/pub/products/search"
        params = {"ft": "perfume", "_from": 0, "_to": 30, "O": "OrderByPriceASC"}
        try:
            resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False)
            if resp.status_code == 200:
                for item in resp.json():
                    img_url = item["items"][0]["images"][0]["imageUrl"] if item.get("items") and item["items"][0].get("images") else ""
                    precio = float(item["items"][0]["sellers"][0]["commertialOffer"]["Price"]) if item.get("items") else 999.0
                    productos.append({"nombre": f"{marca.upper()} - {item.get('productName','').upper()}", "precio": precio, "link": item.get("link", url), "img": img_url})
        except: pass

    # --- MIFARMA ---
    elif "mifarma" in url_clean:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        palabra_busqueda = query_params['keyword'][0] if 'keyword' in query_params else "shampoo"
        api_url = "https://www.mifarma.com.pe/api/catalog_system/pub/products/search"
        params = {"ft": palabra_busqueda, "_from": 0, "_to": 30, "O": "OrderByPriceASC"}
        try:
            resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False)
            if resp.status_code == 200:
                for item in resp.json():
                    img_url = item["items"][0]["images"][0]["imageUrl"] if item.get("items") and item["items"][0].get("images") else ""
                    precio = float(item["items"][0]["sellers"][0]["commertialOffer"]["Price"]) if item.get("items") else 999.0
                    productos.append({"nombre": f"MIFARMA - {item.get('productName','').upper()}", "precio": precio, "link": item.get("link", url), "img": img_url})
        except: pass

    # --- COMODÍN GENERAL ---
    else:
        try:
            headers_html = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36"}
            resp = requests.get(url, headers=headers_html, timeout=15, verify=False)
            soup = BeautifulSoup(resp.text, 'html.parser')
            for t in soup.find_all('div', class_=lambda x: x and ('product' in x or 'card' in x or 'item' in x)):
                tit = t.find(['h3', 'h2', 'span', 'p'], class_=re.compile(r'(title|name|nombre|producto)', re.I))
                if not tit: continue
                precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', t.text)
                valores = sorted([float(p.replace(',', '.')) for p in precios if float(p.replace(',', '.')) > 2])
                if valores:
                    a = t.find('a', href=True)
                    img = t.find('img', src=True)
                    productos.append({"nombre": tit.text.strip().upper(), "precio": valores[0], "link": urljoin(url, a['href']) if a else url, "img": img['src'] if img else ""})
        except: pass

    return productos

def revisar_ofertas(categoria_filtro="TODOS"):
    res = supabase.table("radares").select("*").execute()
    if not res or not res.data: return
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    for item in res.data:
        identificador = str(item['identificador']).strip()
        limite = float(item['precio_max'])
        url_radar = str(item['url']).strip().lower()
        
        parts = identificador.split("-")
        tienda_txt = parts[0].upper() if len(parts) > 0 else "TIENDA"
        cat_txt = parts[1].upper() if len(parts) > 1 else "OTROS"
        talla_txt = parts[3] if len(parts) > 3 else "Todas"
        
        # --- MAPEO SEMÁNTICO COINCIDENTE ---
        grupo_sistema = "OTROS"
        if "ZAPATILLA" in cat_txt or "SNEAKER" in cat_txt or "RUNNING" in cat_txt: grupo_sistema = "ZAPATILLAS"
        elif "PERFUME" in cat_txt or "FRAGANCIA" in cat_txt: grupo_sistema = "PERFUMES"
        elif cat_txt in ["SHAMPOO", "JABON", "DESODORANTE", "CUIDADO_PERSONAL", "SALUD"]: grupo_sistema = "CUIDADO_PERSONAL"
        elif cat_txt in ["TV", "TELEVISOR", "REFRIS", "SAMSUNG", "TECNOLOGIA", "ELECTRONICA", "JBL", "EQUIPOS"]: grupo_sistema = "TECNOLOGIA"
        elif cat_txt in ["CASACAS", "POLERAS", "POLOS", "BUZOS", "JEANS", "MEDIAS", "ROPA", "ABRIGO"]: grupo_sistema = "ROPA"

        # REGLA EXCLUSIVA DE BOTÓN: Si no coincide con el filtro elegido, salta este radar
        if categoria_filtro != "TODOS" and categoria_filtro != grupo_sistema:
            continue

        prods = escanear_tienda(item['url'], limite)
        if prods:
            for p in prods:
                if grupo_sistema in ["PERFUMES", "CUIDADO_PERSONAL"] or "tiendabelcorp" in url_radar:
                    nombre_limpio = str(p['nombre']).upper().replace(" ", "_").replace("-", "_").replace("Á","A").replace("É","E").replace("Í","I").replace("Ó","O").replace("Ú","U")
                    id_registro_dashboard = f"{tienda_txt}-{cat_txt}-{nombre_limpio}-{talla_txt}"
                else:
                    id_registro_dashboard = identificador
                
                try: supabase.table("historial_precios").insert({"identificador": id_registro_dashboard, "precio": p['precio'], "fecha": fecha_hoy}).execute()
                except: pass
                
                if p['precio'] <= limite:
                    ahorro = limite - p['precio']
                    porcentaje = (ahorro / limite) * 100 if limite > 0 else 0
                    msg = f"🔥 *¡OFERTA DETECTADA POR COBY ({grupo_sistema})!* 🔥\n━━━━━━━━━━━━━━━━━━━\n\n📦 *Producto:* {p['nombre']}\n🏪 *Tienda:* `{tienda_txt}`\n🏷️ *Categoría:* `{cat_txt}`\n\n💵 *Precio Actual:* `S/. {p['precio']:.2f}`\n🎯 *Tu Precio Límite:* `S/. {limite:.2f}`\n"
                    if p['precio'] < limite: msg += f"📉 *¡Te estás ahorrando:* S/. {ahorro:.2f} ({porcentaje:.1f}% menos)!\n"
                    else: msg += f"⚖️ *¡Llegó a tu precio objetivo exacto!*\n"
                    msg += f"\n🚨 _¡Aprovecha antes de que vuele el stock!_"
                    enviar_telegram(msg, p['link'], p['img'])
                    time.sleep(0.5)
