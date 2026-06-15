import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import random
import time
from urllib.parse import urljoin
from supabase import create_client, Client

SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_publishable_LG-EavkoMBYDSCS0xsCccQ_1062w4zq"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HISTORIAL_FILE = "historial_precios.json"
CUPONES_FILE = "cupones.json"
TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

# --- MEJORA 2: MODO CAMUFLAJE - POOL DE IDENTIDADES HUMANAS AVANZADAS ---
USER_AGENTS_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0"
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

# --- MEJORA 1: EL RECEPTOR DE ENLACES (Escuchar comandos desde tu celular) ---
def revisar_comandos_telegram():
    url_updates = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/getUpdates"
    try:
        res = requests.get(url_updates, timeout=10).json()
        if not res.get("ok", False): return
        for update in res.get("result", []):
            msg = update.get("message", {})
            text = msg.get("text", "")
            if text.startswith("/guardar "):
                # Formato esperado: /guardar URL Talla: X Tope: N
                partes = text.replace("/guardar ", "").split(" ")
                if len(partes) >= 1:
                    url_input = partes[0].strip()
                    talla_input = "TODAS"
                    tope_input = 100
                    
                    # Extraer parámetros si existen
                    for idx, p in enumerate(partes):
                        if "talla:" in p.lower() and idx + 1 < len(partes): talla_input = partes[idx+1].upper()
                        if "tope:" in p.lower() and idx + 1 < len(partes): tope_input = int(partes[idx+1])
                    
                    # Deducir tienda de manera dinámica
                    tienda_deducida = "OTRA"
                    for t in ["adidas", "falabella", "marathon", "ripley", "puma", "nike", "esika", "plazavea"]:
                        if t in url_input.lower(): tienda_deducida = t.upper()
                        
                    nuevo_id = f"{tienda_deducida}-GUSTOS-PRODUCTO_TEL-{talla_input}"
                    
                    # Registrar de forma indestructible en Supabase desde el celular
                    try: supabase.table("radares").delete().eq("identificador", nuevo_id).execute()
                    except: pass
                    supabase.table("radares").insert({"url": url_input, "precio_max": tope_input, "identificador": nuevo_id}).execute()
                    
                    # Confirmar al celular del usuario
                    url_send = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
                    requests.post(url_send, json={"chat_id": CHAT_ID_TELEGRAM, "text": f"✅ *¡Radar Guardado desde tu Celular!*\n🏢 Tienda: `{tienda_deducida}`\n🎯 Tope: `S/. {tope_input}`\n📂 ID: `{nuevo_id}`", "parse_mode": "Markdown"})
    except: pass

def escanear_tienda(url_base, limite_precio, tienda, talla_buscada, item_id):
    productos_encontrados = []
    headers = {
        "User-Agent": random.choice(USER_AGENTS_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }
    try:
        # --- MEJORA 2: CAMUFLAJE - PAUSA ALEATORIA EVITA BLOQUEOS ---
        time.sleep(random.uniform(1.5, 3.5))
        respuesta = requests.get(url_base, headers=headers, timeout=15)
        if respuesta.status_code != 200: return []
            
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        tarjetas = soup.find_all('div', class_=lambda x: x and ('product' in x or 'item' in x or 'card' in x or 'grid' in x or 'tile' in x)) or [soup]

        for tarjeta in tarjetas:
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
                
                # Calcular caída porcentual para la MEJORA 3
                caida_agresiva = False
                if precio_original > precio_descuento and precio_descuento > 0:
                    porcentaje_off = ((precio_original - precio_descuento) / precio_original) * 100
                    if porcentaje_off >= 30.0: caida_agresiva = True # Caída flotante detectada

                # Condicional de éxito: Precio tope, o tiene combo, o tiene caída agresiva (>30%)
                if (precio_descuento > 0 and precio_descuento <= limite_precio) or tiene_combo or caida_agresiva:
                    item_dict = {
                        "nombre": nombre_prod, 
                        "precio_original": (precio_original if precio_original > 0 else precio_descuento), 
                        "precio_descuento": precio_descuento, 
                        "link": url_base, 
                        "foto": link_foto, 
                        "es_combo": tiene_combo,
                        "es_agresiva": caida_agresiva
                    }
                    productos_encontrados.append(item_dict)
            except: pass
        return productos_encontrados
    except: return []

def revisar_ofertas():
    # Escuchar comandos entrantes del celular primero
    revisar_comandos_telegram()
    
    try:
        res_s = supabase.table("radares").select("*").execute()
        lineas = res_s.data if res_s.data else []
    except: return
    if not lineas: return

    historial = {}
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f: historial = json.load(f)
        except: historial = {}
            
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    hora_actual = str(datetime.now().hour)
    
    # MEJORA 4: Registrar hora en las estadísticas comerciales
    log_horas = historial.get("LOG_HORARIOS_OFERTAS", {})
    
    for item in lineas:
        meta = item["identificador"].strip().split("-")
        tienda, categoria, talla = meta[0], meta[1], meta[3] if len(meta)>3 else "Todas"
        
        productos = escanear_tienda(url_base=item["url"], limite_precio=float(item["precio_max"]), tienda=tienda, talla_buscada=talla, item_id=item["id"])
        
        for p in productos:
            id_producto = f"{tienda}-{categoria}-{''.join(c for c in p['nombre'] if c.isalnum())[:15]}-{talla}"
            if id_producto not in historial: historial[id_producto] = {}
            
            precios_anteriores = [v for k, v in historial[id_producto].items() if isinstance(v, (int, float))]
            
            # --- MEJORA 3: LÓGICA DE ALERTA POR CAÍDA PORCENTUAL FLOTANTE ---
            if p.get("es_agresiva", False):
                header_mensaje = "🚨 *[ALERTA RADICAL - CAÍDA FLOTANTE >30%]* 🚨"
                alert_estafa = "🔥 *REMATÓN CRÍTICO:* _El producto cayó más del 30% respecto a su precio normal. Ignoramos tu tope porque esto es un regalo de la tienda._"
                log_horas[hora_actual] = log_horas.get(hora_actual, 0) + 1
            elif p.get("es_combo", False):
                header_mensaje = "🎁 *¡ALERTA DE REGALO / COMBO DETECTADO!* 🎁"
                alert_estafa = "🔥 *BENEFICIO EXCLUSIVO:* _Texto de regalo detectado (2x1, Gratis o combos). Verificalo._"
                log_horas[hora_actual] = log_horas.get(hora_actual, 0) + 1
            else:
                header_mensaje = "🛍️ *¡OFERTAS DE CATÁLOGO DETECTADAS!* 🛍️"
                alert_estafa = "✅ *OFERTA EN LISTA RECOMENDADA*"
                log_horas[hora_actual] = log_horas.get(hora_actual, 0) + 1

            tendencia_txt = "🆕 *TENDENCIA:* Elemento detectado en el barrido de lista."
            if len(precios_anteriores) >= 1 and p['precio_descuento'] > 0:
                ultimo_p = precios_anteriores[-1]
                if p['precio_descuento'] < ultimo_p: tendencia_txt = "📉 *TENDENCIA:* ¡Bajón de precio en catálogo! 🎯"
                else: tendencia_txt = "📊 *TENDENCIA:* Precio estable en el catálogo."

            if p['precio_descuento'] > 0:
                historial[id_producto][fecha_hoy] = p['precio_descuento']
                
            ahorro_soles = p['precio_original'] - p['precio_descuento']
            barra_grafica = generar_barra_descuento(p['precio_original'], p['precio_descuento'])
            
            reporte = (
                f"{header_mensaje}\n"
                f"———————————————————\n\n
