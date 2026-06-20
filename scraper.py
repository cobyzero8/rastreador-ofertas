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
    # Camuflaje ultra-pesado para evitar bloqueos nocturnos/vespertinos
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Connection": "keep-alive"
    }
    productos = []
    url_clean = str(url).strip().lower()

    # =========================================================
    # 🧪 BLOQUE BELCORP (ESIKA / CYZONE / LBEL)
    # =========================================================
    if "tiendabelcorp" in url_clean or "cyzone" in url_clean or "lbel" in url_clean or "esika" in url_clean:
        marca = "cyzone" if "cyzone" in url_clean else "lbel" if "lbel" in url_clean else "esika"
        api_url = f"https://{marca}.tiendabelcorp.com.pe/api/catalog_system/pub/products/search"
        params = {"ft": "perfume", "_from": 0, "_to": 20, "O": "OrderByPriceASC"}
        
        resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False)
        if resp.status_code != 200:
            raise Exception(f"La tienda {marca.upper()} respondió con código {resp.status_code} (Posible Bloqueo de IP).")
            
        items = resp.json()
        for item in items:
            nombre = item.get("productName", "Perfume Belcorp")
            link_completo = item.get("link", url)
            img_url = ""
            precio = 999.0
            
            items_in = item.get("items", [])
            if items_in:
                imgs = items_in[0].get("images", [])
                if imgs: 
                    img_url = imgs[0].get("imageUrl", "")
                sellers = items_in[0].get("sellers", [])
                if sellers:
                    oferta = sellers[0].get("commertialOffer", {})
                    precio = float(oferta.get("Price", 999.0))
                    
            if precio < 999.0 and precio > 0:
                productos.append({"nombre": f"{marca.upper()} - {nombre.upper()}", "precio": precio, "link": link_completo, "img": img_url})

    # =========================================================
    # 🧼 BLOQUE MIFARMA
    # =========================================================
    elif "mifarma" in url_clean:
        api_url = "https://www.mifarma.com.pe/api/catalog_system/pub/products/search"
        params = {"ft": "shampoo", "_from": 0, "_to": 20, "O": "OrderByPriceASC"}
        
        resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False)
        if resp.status_code != 200:
            raise Exception(f"Mifarma respondió con código {resp.status_code} (Filtro Anti-Bot).")
            
        items = resp.json()
        for item in items:
            nombre = item.get("productName", "Mifarma")
            link_completo = item.get("link", url)
            img_url = ""
            precio = 999.0
            
            items_in = item.get("items", [])
            if items_in:
                imgs = items_in[0].get("images", [])
                if imgs: 
                    img_url = imgs[0].get("imageUrl", "")
                sellers = items_in[0].get("sellers", [])
                if sellers:
                    oferta = sellers[0].get("commertialOffer", {})
                    precio = float(oferta.get("Price", 999.0))
                    
            if precio < 999.0 and precio > 0:
                productos.append({"nombre": f"MIFARMA - {nombre.upper()}", "precio": precio, "link": link_completo, "img": img_url})

    # =========================================================
    # 👟 COMODÍN GENERAL HTML
    # =========================================================
    else:
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        if resp.status_code != 200:
            raise Exception(f"El enlace general respondió con código {resp.status_code}")
            
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

    return productos

def revisar_ofertas(categoria_filtro="TODOS"):
    res = supabase.table("radares").select("*").execute()
    if not res or not res.data:
        return "No hay radares configurados en Supabase."
    
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    filtro_web = str(categoria_filtro).upper().strip()
    total_procesados = 0
    
    for item in res.data:
        identificador = str(item['identificador']).strip()
        limite = float(item['precio_max'])
        url_radar = str(item['url']).strip().lower()
        
        parts = identificador.split("-")
        tienda_txt = parts[0].upper()
        cat_txt = parts[1].upper()
        talla_txt = parts[3] if len(parts) > 3 else "Todas"
        
        grupo_sistema = "OTROS"
        if cat_txt == "ZAPATILLAS": grupo_sistema = "ZAPATILLAS"
        elif cat_txt == "PERFUMES": grupo_sistema = "PERFUMES"
        elif cat_txt == "SHAMPOO": grupo_sistema = "CUIDADO_PERSONAL"

        if filtro_web != "TODOS" and filtro_web != grupo_sistema:
            continue

        # Aquí dejamos que el error suba a la app para saber qué pasa
        prods = escanear_tienda(item['url'], limite)
        
        if prods:
            for p in prods:
                if grupo_sistema == "PERFUMES":
                    nombre_limpio = str(p['nombre']).upper().replace(" ", "_").replace("-", "_").replace("Á","A").replace("É","E").replace("Í","I").replace("Ó","O").replace("Ú","U")
                    id_registro_dashboard = f"{tienda_txt}-PERFUMES-{nombre_limpio}-{talla_txt}"
                elif grupo_sistema == "CUIDADO_PERSONAL":
                    nombre_limpio = str(p['nombre']).upper().replace(" ", "_").replace("-", "_").replace("Á","A").replace("É","E").replace("Í","I").replace("Ó","O").replace("Ú","U")
                    id_registro_dashboard = f"{tienda_txt}-SHAMPOO-{nombre_limpio}-{talla_txt}"
                else:
                    id_registro_dashboard = identificador
                
                try:
                    supabase.table("historial_precios").insert({"identificador": id_registro_dashboard, "precio": p['precio'], "fecha": fecha_hoy}).execute()
                    total_procesados += 1
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
                    time.sleep(0.3)
                    
    return f"Éxito: Se escanearon los enlaces y se inyectaron {total_procesados} sub-productos nuevos al historial."
