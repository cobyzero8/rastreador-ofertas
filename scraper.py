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

# CONFIGURACIÓN
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_publishable_LG-EavkoMBYDSCS0xsCccQ_1062w4zq"
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
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/123.0.0.0 Safari/537.36"}
        resp = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(resp.text, 'html.parser')
        productos = []
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
    except: return []

def revisar_ofertas():
    res = supabase.table("radares").select("*").execute()
    if not res.data:
        return
    
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    for item in res.data:
        identificador = item['identificador']
        limite = float(item['precio_max'])
        prods = escanear_tienda(item['url'], limite)
        
        if prods:
            # Tomamos el precio más bajo encontrado en la página para el historial
            precio_actual = prods[0]['precio']
            
            # 📈 REGISTRO AUTOMÁTICO EN LA NUEVA TABLA DE SUPABASE
            try:
                supabase.table("historial_precios").insert({
                    "identificador": identificador,
                    "precio": precio_actual,
                    "fecha": fecha_hoy
                }).execute()
            except: pass
            
            # Si el precio destruye tu tope, dispara la alerta a Telegram
            for p in prods:
                if p['precio'] <= limite:
                    msg = f"🛍️ *OFERTA ENCONTRADA*\n📦 {p['nombre']}\n💵 S/. {p['precio']:.2f}"
                    enviar_telegram(msg, p['link'], p['img'])
