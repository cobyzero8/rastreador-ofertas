import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
from urllib.parse import urljoin

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"
TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
    payload = {"chat_id": CHAT_ID_TELEGRAM, "text": mensaje, "parse_mode": "Markdown", "disable_web_page_preview": False}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def escanear_tienda(url_base, limite_precio, tienda, talla_buscada):
    productos_encontrados = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        respuesta = requests.get(url_base, headers=headers, timeout=15)
        if respuesta.status_code != 200:
            return []
            
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        t_low = tienda.lower()
        tarjetas = []
        
        if "adidas" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x) or soup.find_all('div', attrs={"data-glass-item": "product-card"})
        elif "falabella" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x) or soup.find_all('div', class_=lambda x: x and 'pod-details' in x)
        elif "marathon" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-item' in x) or soup.find_all('div', class_=lambda x: x and 'productCard' in x)
        elif "ripley" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'catalog-product' in x) or soup.find_all('a', class_='ProductCard__ProductLink')
        else:
            tarjetas = soup.find_all('div', class_=lambda x: x and ('product' in x or 'item' in x or 'card' in x))

        for tarjeta in tarjetas:
            tit = tarjeta.find(['p', 'b', 'h3', 'div', 'a'], class_=re.compile(r'(title|name|heading|pod-title)', re.I)) or tarjeta.find('p')
            prc = tarjeta.find(class_=re.compile(r'(price|sale|oferta|current)', re.I)) or tarjeta.find(lambda tag: tag.name in ['span', 'div'] and 'S/.' in tag.text)
            
            # --- DETECCIÓN DEL LINK COMPLETO DEL ARTÍCULO ---
            link_tag = tarjeta.find('a', href=True) or (tarjeta if tarjeta.name == 'a' and tarjeta.has_attr('href') else None)
            link_articulo = url_base
            if link_tag and link_tag['href']:
                # urljoin junta la URL base con el link relativo (ej: /producto/123 -> https://tienda.com/producto/123)
                link_articulo = urljoin(url_base, link_tag['href'])

            if tit and prc:
                nombre_prod = tit.text.strip().replace("\n", "").replace(",", "")
                text_precio = prc.text.strip()
                
                nums = ''.join(filter(str.isdigit, text_precio))
                if not nums:
                    continue
                    
                p_num = int(nums) / 100 if len(nums) > 4 and ("adidas" in t_low or "marathon" in t_low) else int(nums[:4]) if len(nums) > 5 else int(nums)
                
                if p_num <= limite_precio:
                    talla_check = str(talla_buscada).upper().strip()
                    if talla_check and talla_check not in ["TODAS", "N/A", ""]:
                        patron = r'\b' + re.escape(talla_check) + r'\b'
                        if not re.search(patron, tarjeta.text.upper()):
                            continue
                    
                    productos_encontrados.append({
                        "nombre": nombre_prod, 
                        "precio": int(p_num),
                        "link": link_articulo
                    })
        return productos_encontrados
    except:
        return []

def revisar_ofertas():
    if not os.path.exists(URLS_FILE):
        return
        
    historial = {}
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                historial = json.load(f)
        except:
            historial = {}
            
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    with open(URLS_FILE, "r", encoding="utf-8") as f:
        lineas = [l.strip() for l in f.readlines() if l.strip() and "," in l]

    if not lineas:
        return

    conteo_radares = 0
    encontrado_oferta = False

    for linea in lineas:
        partes = linea.split(",")
        if len(partes) < 3:
            continue
            
        url_base = partes[0].strip()
        presupuesto_max = int(partes[1].strip())
        identificador = partes[2].strip()
        
        meta = identificador.split("_")
        tienda = meta[0] if len(meta) > 0 else "General"
        categoria = meta[1] if len(meta) > 1 else "General"
        talla = meta[2] if len(meta) > 2 else "Todas"
        
        conteo_radares += 1
        productos = escanear_tienda(url_base, presupuesto_max, tienda, talla)
        
        for p in productos:
            nombre_key = "".join(c for c in p['nombre'] if c.isalnum() or c=='_')[:30]
            id_producto = f"{tienda}_{categoria}_{talla}_{nombre_key}"
            precio_actual = p['precio']
            
            if id_producto not in historial:
                historial[id_producto] = {}
                
            historial[id_producto][fecha_hoy] = precio_actual
            precios_previos = list(historial[id_producto].values())
            
            # Si el producto es nuevo o bajó de precio respecto al registro anterior
            if len(precios_previos) == 1 or (len(precios_previos) > 1 and precio_actual < precios_previos[-2]):
                encontrado_oferta = True
                
                # REPORTE PROFESIONAL CON LA INFORMACIÓN COMPLETA Y EL LINK DIRECTO
                reporte = (
                    f"🚨 *¡OFERTÓN DETECTADO EN {tienda.upper()}!* 🚨\n\n"
                    f"📦 *Producto:* `{p['nombre']}`\n"
                    f"👟 *Talla:* {talla}\n"
                    f"💰 *PRECIO ACTUAL:* S/. {precio_actual}\n"
                    f"🎯 *Precio Máximo:* S/. {presupuesto_max}\n\n"
                    f"🔗 *LINK DIRECTO DE COMPRA:* {p['link']}"
                )
                enviar_telegram(reporte)
                
    with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, indent=4)
        
    if not encontrado_oferta:
        enviar_telegram(f"✅ *Escaneo completado.*\nSe revisaron `{conteo_radares}` radares. No se encontraron ofertas nuevas por debajo del tope asignado. 🫡")
