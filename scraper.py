import os
import json
import requests
from bs4 import BeautifulSoup
import re
import random
import time
from datetime import datetime
from urllib.parse import urljoin
from supabase import create_client, Client

# --- CONFIGURACIÓN DE ÉLITE ---
# RECUERDA: Cambiar esta clave por tu "service_role" secreta en GitHub para saltar el bloqueo RLS de Supabase
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_secret_UNSyaeXMv0nHZT4Ipih0-g__t6fxuJc" 

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
    except: 
        pass

import requests
import re

def escanear_tienda(url, limite):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-PE,es;q=0.9"
        }
        productos = []

        # =========================================================
        # 🕵️‍♂️ DETECCIÓN MAPA 1: TIENDAS BELCORP (CYZONE, LBEL, ESIKA)
        # =========================================================
        if "tiendabelcorp.com.pe" in url:
            # Extraemos la marca (cyzone, lbel o esika) directamente desde la URL
            marca = "cyzone" if "cyzone" in url else "lbel" if "lbel" in url else "esika"
            
            # API Oculta de Belcorp para traer los productos directo en formato limpio JSON
            api_url = f"https://api.tiendabelcorp.com.pe/v2/products/search/{marca}/PE"
            params = {
                "category": "perfumes",
                "page": 1,
                "pageSize": 24,
                "sort": "price_asc"
            }
            
            resp = requests.get(api_url, headers=headers, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                # Recorremos la lista interna de productos de Belcorp
                for p in data.get("products", []):
                    nombre = p.get("name", "Perfume Belcorp")
                    # Buscamos el precio de oferta actual
                    precio = float(p.get("price", {}).get("value", 999))
                    link_rel = p.get("urlKey", "")
                    link_completo = f"https://{marca}.tiendabelcorp.com.pe/{link_rel}/p"
                    img_url = p.get("images", [{}])[0].get("url", "")
                    
                    productos.append({
                        "nombre": f"{marca.upper()} - {nombre}",
                        "precio": precio,
                        "link": link_completo,
                        "img": img_url
                    })

        # =========================================================
        # 🕵️‍♂️ DETECCIÓN MAPA 2: TIENDA NATURA PERÚ
        # =========================================================
        elif "natura.com.pe" in url:
            # Determinamos si busca masculinos o femeninos basado en tu link
            tipo_perfume = "perfumeria-masculina" if "perfumeria-masculina" in url else "perfumeria-femenina"
            
            # API Oculta de Natura (VTEX Intelligent Search)
            api_url = "https://www.natura.com.pe/_v/segment/graphql/v1"
            
            # Consulta inteligente estructurada para simular el catálogo de Natura
            query_json = {
                "operationName": "productSearch",
                "variables": {
                    "query": tipo_perfume,
                    "page": 1,
                    "count": 20,
                    "sort": "OrderByPriceASC"
                },
                "extensions": {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": "b06828980b62e49c1ee91a27e7ca4a206a4b11f67f39420063f2563f8d380e2f"
                    }
                }
            }
            
            resp = requests.post(api_url, headers=headers, json=query_json, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", {}).get("productSearch", {}).get("products", [])
                
                for item in items:
                    nombre = item.get("productName", "Perfume Natura")
                    link_rel = item.get("linkText", "")
                    link_completo = f"https://www.natura.com.pe/{link_rel}/p"
                    img_url = item.get("items", [{}])[0].get("images", [{}])[0].get("imageUrl", "")
                    
                    # Extraer el precio neto del sistema de pagos
                    sellers = item.get("items", [{}])[0].get("sellers", [{}])
                    precio = float(sellers[0].get("commertialOffer", {}).get("Price", 999)) if sellers else 999
                    
                    productos.append({
                        "nombre": f"NATURA - {nombre}",
                        "precio": precio,
                        "link": link_completo,
                        "img": img_url
                    })

        # =========================================================
        # 👟 COMODÍN: TU LÓGICA ORIGINAL PARA MARATHON, ADIDAS, ETC.
        # =========================================================
        else:
            from bs4 import BeautifulSoup
            from urllib.parse import urljoin
            
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
    except Exception as e:
        # Retorna vacío de forma segura si el link falla
        return []

# --- MOTOR DE REVISIÓN Y ENVIOS OPTIMIZADO ---
def revisar_ofertas():
    res = supabase.table("radares").select("*").execute()
    if not res.data:
        return
    
    fecha_hoy = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    for item in res.data:
        identificador = item['identificador']
        limite = float(item['precio_max'])
        url_radar = item['url']
        
        # Extraemos la metadata del identificador base creado en la web
        parts = identificador.split("-")
        tienda_txt = parts[0].upper() if len(parts) > 0 else "TIENDA"
        cat_txt = parts[1].upper() if len(parts) > 1 else "OTROS"
        talla_txt = parts[3] if len(parts) > 3 else "Todas"
        
        # Escaneamos la tienda capturando los productos reales
        prods = escanear_tienda(url_radar, limite)
        
        if prods:
            # Recorremos todos los productos que devolvió el escaneo de esa URL
            for p in prods:
                # Verificamos si el precio del producto cumple tu precio tope (Tope S/. 500)
                if p['precio'] <= limite:
                    
                    # 🚀 MEJORA CLAVE: Si es catálogo (Natura/Belcorp) creamos un identificador 
                    # dinámico único para que CADA perfume aparezca con su propio nombre real en el Dashboard
                    if "natura" in url_radar or "tiendabelcorp" in url_radar:
                        nombre_limpio = p['nombre'].upper().replace(" ", "_").replace("-", "_")
                        id_registro_dashboard = f"{tienda_txt}-{cat_txt}-{nombre_limpio}-{talla_txt}"
                    else:
                        # Para zapatillas tradicionales mantiene tu identificador exacto del radar
                        id_registro_dashboard = identificador
                    
                    # 1. Inyectamos de forma segura el registro en la tabla historial_precios de Supabase
                    try:
                        supabase.table("historial_precios").insert({
                            "identificador": id_registro_dashboard,
                            "precio": p['precio'],
                            "fecha": fecha_hoy
                        }).execute()
                    except:
                        pass
                    
                    # 2. Calculamos métricas para el mensaje premium de Telegram
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
                    
                    # 3. Envío seguro al bot de Telegram
                    enviar_telegram(msg, p['link'], p['img'])
                    
                    # Un pequeño respiro de medio segundo para no saturar la API de Telegram
                    time.sleep(0.5)
