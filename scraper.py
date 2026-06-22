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

# --- CONFIGURACIÓN DE ÉLITE ---
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY")
if not SUPABASE_KEY:
    try:
        import streamlit as st
        if "SUPABASE_KEY" in st.secrets:
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

def escanear_tienda(url, limite, palabra_clave=""):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Connection": "keep-alive"
    }
    productos = []
    url_clean = str(url).strip().lower()

    # =========================================================
    # 🧪 MOTOR 1: BELCORP (ESIKA / CYZONE / LBEL) - PERFUMES
    # =========================================================
    if any(k in url_clean for k in ["tiendabelcorp", "cyzone", "lbel", "esika"]):
        marca = "cyzone" if "cyzone" in url_clean else "lbel" if "lbel" in url_clean else "esika"
        api_url = f"https://{marca}.tiendabelcorp.com.pe/api/catalog_system/pub/products/search"
        params = {"ft": "perfume", "_from": 0, "_to": 20, "O": "OrderByPriceASC"}
        
        try:
            resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False)
            if resp.status_code in [200, 206]:
                for item in resp.json():
                    nombre = item.get("productName", "Perfume Belcorp")
                    link_completo = item.get("link", url)
                    img_url = ""
                    precio = 999.0
                    
                    items_in = item.get("items", [])
                    if items_in:
                        imgs = items_in[0].get("images", [])
                        if imgs: img_url = imgs[0].get("imageUrl", "")
                        sellers = items_in[0].get("sellers", [])
                        if sellers:
                            precio = float(sellers[0].get("commertialOffer", {}).get("Price", 999.0))
                            
                    if 0 < precio < 999.0:
                        productos.append({"nombre": f"{marca.upper()} - {nombre.upper()}", "precio": precio, "link": link_completo, "img": img_url})
        except Exception as e:
            print(f"Error Belcorp: {e}")

    # =========================================================
    # 🧼 MOTOR 2: MIFARMA / INKAFARMA - CUIDADO PERSONAL
    # =========================================================
    elif "mifarma" in url_clean or "inkafarma" in url_clean:
        dom = "mifarma" if "mifarma" in url_clean else "inkafarma"
        
        # Estrategia Multi-búsqueda: Intenta con la marca, luego con genéricos
        busquedas = [palabra_clave, "shampoo", "cuidado personal"]
        for kw in busquedas:
            if not kw: continue
            kw_clean = kw.strip().replace(" ", "%20")
            api_url = f"https://www.{dom}.com.pe/api/catalog_system/pub/products/search?ft={kw_clean}&_from=0&_to=20"
            
            try:
                resp = requests.get(api_url, headers=headers, timeout=15, verify=False)
                if resp.status_code in [200, 206]:
                    data = resp.json()
                    for item in data:
                        precio = 999.0
                        items_in = item.get("items", [])
                        if items_in and items_in[0].get("sellers"):
                            precio = float(items_in[0]["sellers"][0].get("commertialOffer", {}).get("Price", 999.0))
                        
                        if 0 < precio < 999.0:
                            img_url = items_in[0]["images"][0]["imageUrl"] if items_in[0].get("images") else ""
                            productos.append({
                                "nombre": f"{dom.upper()} - {item.get('productName', '').upper()}",
                                "precio": precio,
                                "link": item.get("link", url),
                                "img": img_url
                            })
                    if productos: break # Si encontró con esta palabra, deja de buscar
            except Exception as e:
                continue

    # =========================================================
    # 👟 MOTOR 3: COMODÍN HTML (PLATANITOS, ROPA, TV)
    # =========================================================
    else:
        try:
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            if resp.status_code in [200, 206]:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for t in soup.find_all(['div', 'article', 'li'], class_=lambda x: x and any(k in x.lower() for k in ['product', 'card', 'item', 'vitrine', 'grid'])):
                    tit = t.find(['h3', 'h2', 'span', 'p', 'h1'], class_=re.compile(r'(title|name|nombre|producto)', re.I))
                    if not tit: continue
                    
                    precios = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', t.text)
                    valores = sorted([float(p.replace(',', '.')) for p in precios if float(p.replace(',', '.')) > 2])
                    if valores:
                        a = t.find('a', href=True)
                        img = t.find('img', src=True)
                        productos.append({
                            "nombre": tit.text.strip().upper(), 
                            "precio": valores[0], 
                            "link": urljoin(url, a['href']) if a else url, 
                            "img": img['src'] if img else ""
                        })
        except Exception as e:
            print(f"Error HTML: {e}")

    return productos

def revisar_ofertas(categoria_filtro="TODOS"):
    res = supabase.table("radares").select("*").execute()
    if not res or not res.data: return "Sin radares activos."
    
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    filtro_web = str(categoria_filtro).upper().strip()
    total_procesados = 0
    
    for item in res.data:
        identificador = str(item['identificador']).strip()
        limite = float(item['precio_max'])
        
        parts = identificador.split("-")
        tienda_txt = parts[0].upper()
        cat_txt = parts[1].upper().strip()
        talla_txt = parts[3] if len(parts) > 3 else "Todas"
        
        # ENGRANAJE DE MAPEO PARA EL BOTÓN
        grupo_sistema = "OTROS"
        if any(k in cat_txt for k in ["ZAPATILLA", "SNEAKER", "RUNNING", "CALZADO"]): grupo_sistema = "ZAPATILLAS"
        elif any(k in cat_txt for k in ["PERFUME", "FRAGANCIA"]): grupo_sistema = "PERFUMES"
        elif any(k in cat_txt for k in ["SHAMPOO", "JABON", "DESODORANTE", "SALUD", "CUIDADO"]): grupo_sistema = "CUIDADO_PERSONAL"
        elif any(k in cat_txt for k in ["TV", "TELEVISOR", "TECNOLOGIA"]): grupo_sistema = "TECNOLOGIA"
        elif any(k in cat_txt for k in ["CASACAS", "POLOS", "ROPA"]): grupo_sistema = "ROPA"

        if filtro_web != "TODOS" and filtro_web != grupo_sistema:
            continue

        # Pasamos parts[2] (el nombre) como palabra clave para Mifarma
        prods = escanear_tienda(item['url'], limite, parts[2])
        
        if prods:
            for p in prods:
                nombre_limpio = str(p['nombre']).upper().replace(" ", "_").replace("-", "_").replace("Á","A").replace("É","E").replace("Í","I").replace("Ó","O").replace("Ú","U")
                
                # Normalizamos el identificador final
                if grupo_sistema == "PERFUMES": id_reg = f"{tienda_txt}-PERFUMES-{nombre_limpio}-{talla_txt}"
                elif grupo_sistema == "CUIDADO_PERSONAL": id_reg = f"{tienda_txt}-SHAMPOO-{nombre_limpio}-{talla_txt}"
                else: id_reg = f"{tienda_txt}-{grupo_sistema}-{nombre_limpio}-{talla_txt}"
                
                try:
                    supabase.table("historial_precios").insert({"identificador": id_reg, "precio": p['precio'], "fecha": fecha_hoy}).execute()
                    total_procesados += 1
                except Exception:
                    pass
                
                if p['precio'] <= limite:
                    ahorro = limite - p['precio']
                    porcentaje = (ahorro / limite) * 100 if limite > 0 else 0
                    msg = (f"🔥 *¡OFERTA DETECTADA POR COBY ({grupo_sistema})!* 🔥\n━━━━━━━━━━━━━━━━━━━\n\n📦 *Producto:* {p['nombre']}\n🏪 *Tienda:* `{tienda_txt}`\n🏷️ *Categoría:* `{cat_txt}`\n\n💵 *Precio Actual:* `S/. {p['precio']:.2f}`\n🎯 *Tu Precio Límite:* `S/. {limite:.2f}`\n")
                    if p['precio'] < limite: msg += f"📉 *¡Te estás ahorrando:* S/. {ahorro:.2f} ({porcentaje:.1f}% menos)!\n"
                    msg += f"\n🚨 _¡Aprovecha antes de que vuele el stock!_"
                    enviar_telegram(msg, p['link'], p['img'])
                    time.sleep(0.3)
                    
    return f"Éxito: Se inyectaron {total_procesados} productos al tablero."
