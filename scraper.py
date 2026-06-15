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

USER_AGENTS_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
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

def revisar_comandos_telegram():
    url_updates = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/getUpdates"
    try:
        res = requests.get(url_updates, timeout=10).json()
        if not res.get("ok", False): return
        for update in res.get("result", []):
            msg = update.get("message", {})
            text = msg.get("text", "")
            if text.startswith("/guardar "):
                partes = text.replace("/guardar ", "").split(" ")
                if len(partes) >= 1:
                    url_input = partes[0].strip()
                    talla_input = "TODAS"
                    tope_input = 100
                    for idx, p in enumerate(partes):
                        if "talla:" in p.lower() and idx + 1 < len(partes): talla_input = partes[idx+1].upper()
                        if "tope:" in p.lower() and idx + 1 < len(partes): tope_input = int(partes[idx+1])
                    tienda_deducida = "OTRA"
                    for t in ["adidas", "falabella", "marathon", "ripley", "puma", "nike", "esika", "plazavea"]:
                        if t in url_input.lower(): tienda_deducida = t.upper()
                    nuevo_id = f"{tienda_deducida}-GUSTOS-PRODUCTO_TEL-{talla_input}"
                    try: supabase.table("radares").delete().eq("identificador", nuevo_id).execute()
                    except: pass
                    supabase.table("radares").insert({"url": url_input, "precio_max": tope_input, "identificador": nuevo_id}).execute()
                    url_send = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
                    requests.post(url_send, json={"chat_id": CHAT_ID_TELEGRAM, "text": f"✅ *¡Radar Guardado desde tu Celular!*\n🏢 Tienda: `{tienda_deducida}`\n🎯 Tope: `S/. {tope_input}`", "parse_mode": "Markdown"})
    except: pass

def escanear_tienda(url_base, limite_precio, tienda, talla_buscada, item_id):
    productos_encontrados = []
    headers = {
        "User-Agent": random.choice(USER_AGENTS_POOL),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }
    try:
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
                caida_agresiva = False
                if precio_original > precio_descuento and precio_descuento > 0:
                    porcentaje_off = ((precio_original - precio_descuento) / precio_original) * 100
                    if porcentaje_off >= 30.0: caida_agresiva = True
                if (precio_descuento > 0 and precio_descuento <= limite_precio) or tiene_combo or caida_agresiva:
                    item_dict = {"nombre": nombre_prod, "precio_original": (precio_original if precio_original > 0 else precio_descuento), "precio_descuento": precio_descuento, "link": url_base, "foto": link_foto, "es_combo": tiene_combo, "es_agresiva": caida_agresiva}
                    productos_encontrados.append(item_dict)
            except: pass
        return productos_encontrados
    except: return []

def simular_rastreo_cupones_global(tiendas_usuario):
    banco = {
        "ADIDAS": [{"codigo": "ADI2026", "descuento": "20% OFF", "detalle": "En calzado running"}],
        "FALABELLA": [{"codigo": "FALA15", "descuento": "15% OFF", "detalle": "Exclusivo App CMR"}],
        "MARATHON": [{"codigo": "RUNNER10", "descuento": "S/. 30 Menos", "detalle": "Por compras de S/. 250"}]
    }
    cupones_filtrados = {k: v for k, v in banco.items() if k in tiendas_usuario}
    with open(CUPONES_FILE, "w", encoding="utf-8") as f: json.dump(cupones_filtrados, f, indent=4)

def revisar_ofertas():
    revisar_comandos_telegram()
    try:
        res_s = supabase.table("radares").select("*").execute()
        lineas = res_s.data if res_s.data else
