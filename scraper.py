import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import random
from urllib.parse import urljoin
from supabase import create_client, Client

SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_publishable_LG-EavkoMBYDSCS0xsCccQ_1062w4zq"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HISTORIAL_FILE = "historial_precios.json"
CUPONES_FILE = "cupones.json"
TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

USER_AGENTS_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
]

PALABRAS_COMBOS = ["GRATIS", "2X1", "3X2", "REGALO", "LLEVATE", "COMBO", "PROMOCION", "INCLUYE"]

def generar_barra_descuento(precio_orig, precio_desc):
    try:
        if precio_orig <= 0: return ""
        porcentaje = ((precio_orig - precio_desc) / precio_orig) * 100
        if porcentaje <= 0: return ""
        bloques = int(round(porcentaje / 10))
        barra = "█" * max(1, min(bloques, 10))
        return f"`[{barra.ljust(10, '░')}]` *¡{porcentaje:.0f}% Real OFF!*"
    except: return ""

def enviar_telegram_con_foto_y_botones(mensaje, url_compra, url_foto):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendPhoto"
    reply_markup = {"inline_keyboard": [[{"text": "🛒 Ir al Catálogo / Comprar", "url": url_compra}]]}
    foto_final = url_foto if url_foto and url_foto.startswith("http") else "https://images.unsplash.com/photo-1555529669-e69e7aa0ba9a?q=80&w=500"
    try: requests.post(url, json={"chat_id": CHAT_ID_TELEGRAM, "photo": foto_final, "caption": mensaje, "parse_mode": "Markdown", "reply_markup": json.dumps(reply_markup)}, timeout=10)
    except: pass

def escanear_tienda(url_base, limite_precio, tienda, talla_buscada, item_id):
    productos_encontrados = []
    headers = {
        "User-Agent": random.choice(USER_AGENTS_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }
    try:
        respuesta = requests.get(url_base, headers=headers, timeout=15)
        if respuesta.status_code != 200:
            return []
            
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        tarjetas = soup.find_all('div', class_=lambda x: x and ('product' in x or 'item' in x or 'card' in x or 'grid' in x or 'tile' in x)) or [soup]

        for tarjeta in tarjetas:
            # --- ESTRUCTURA GENERAL DE EXCEPCIÓN COMPLETAMENTE LOGRADA Y REPARADA EN LA LÍNEA 68 ---
            try:
                texto_tarjeta = tarjeta.text.upper()
                
                tit = tarjeta.find(['p', 'b', 'h1', 'h2', 'h3', 'span', 'a'])
                if not tit: continue
                nombre_prod = re.sub(r'\s+', ' ', tit.text.strip().replace(",", ""))
                if len(nombre_prod) < 4: continue
                
                img_tag = tarjeta.find('img', src=True)
                link_foto = urljoin(url_base, img_tag['src']) if img_tag else ""
                
                precios = re.findall(r'(?:S/\.?\s*|\$\s*)(\d+[\.,]\d{2}|\d+)', tarjeta.text)
                valores = sorted(list(set([float(p.replace(',', '.')) for p in precios if float(p.replace(',', '.')) > 2])))
                
                precio_descuento = valores[0] if valores else 0.0
                precio_original = valores[-1] if valores else 0.0

                tiene_combo = any(palabra in texto_tarjeta for palabra in PALABRAS_COMBOS)
                
                if (precio_descuento > 0 and precio_descuento <= limite_precio) or tiene_combo:
                    item_dict = {"nombre": nombre_prod, "precio_original": (precio_original if precio_original > 0 else precio_descuento), "precio_descuento": precio_descuento, "link": url_base, "foto": link_foto, "es_combo": tiene_combo}
                    productos_encontrados.append(item_dict)
            except:
                pass
        return productos_encontrados
    except: 
        return []

def simular_rastreo_cupones_global(tiendas_usuario):
    banco = {
        "ADIDAS": [{"codigo": "ADI2026", "descuento": "20% OFF", "detalle": "En calzado running"}],
        "FALABELLA": [{"codigo": "FALA15", "descuento": "15% OFF", "detalle": "Exclusivo App CMR"}],
        "MARATHON": [{"codigo": "RUNNER10", "descuento": "S/. 30 Menos", "detalle": "Por compras de S/. 250"}]
    }
    cupones_filtrados = {k: v for k, v in banco.items() if k in tiendas_usuario}
    with open(CUPONES_FILE, "w", encoding="utf-8") as f: json.dump(cupones_filtrados, f, indent=4)

def revisar_ofertas():
    try:
        res_s = supabase.table("radares").select("*").execute()
        lineas = res_s.data if res_s.data else []
    except: return
    if not lineas: return

    tiendas_activas = set([item["identificador"].split("-")[0].upper() for item in lineas])
    try: simular_rastreo_cupones_global(tiendas_activas)
    except: pass

    historial = {}
    if os.path.exists(HISTORIAL_FILE):
        try: 
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f: historial = json.load(f)
        except: historial = {}
            
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    hora_actual = datetime.now().hour
    es_madrugada = (hora_actual >= 23 or hora_actual <= 5)

    for item in lineas:
        meta = item["identificador"].strip().split("-")
        tienda, categoria, talla = meta[0], meta[1], meta[3] if len(meta)>3 else "Todas"
        
        productos = escanear_tienda(url_base=item["url"], limite_precio=float(item["precio_max"]), tienda=tienda, talla_buscada=talla, item_id=item["id"])
        
        for p in productos:
            id_producto = f"{tienda}-{categoria}-{''.join(c for c in p['nombre'] if c.isalnum())[:15]}-{talla}"
            if id_producto not in historial: historial[id_producto] = {}
            
            precios_anteriores = [v for k, v in historial[id_producto].items() if isinstance(v, (int, float))]
            precio_promedio = sum(precios_anteriores) / len(precios_anteriores) if precios_anteriores else p['precio_original']
            
            if precios_anteriores and p['precio_descuento'] > (precio_promedio * 1.05):
                alert_estafa = "⚠️ *ALERTA:* _Falsa oferta detectada (Precio inflado)._"
            else:
                alert_estafa = "✅ *OFERTA EN LISTA RECOMENDADA*"
