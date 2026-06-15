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
        
        # Selectores de bloques de producto
        if "adidas" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x) or soup.find_all('div', attrs={"data-glass-item": "product-card"})
        elif "falabella" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x) or soup.find_all('div', class_=lambda x: x and 'pod-details' in x)
        elif "marathon" in t_low or "triathlon" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and ('product-item' in x or 'productCard' in x or 'item' in x))
        elif "ripley" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'catalog-product' in x) or soup.find_all('a', class_='ProductCard__ProductLink')
        else:
            tarjetas = soup.find_all('div', class_=lambda x: x and ('product' in x or 'item' in x or 'card' in x or 'pod' in x))

        # Si no detecta tarjetas individuales, analizamos el cuerpo entero (para páginas de un solo producto)
        if not tarjetas:
            tarjetas = [soup]

        for tarjeta in tarjetas:
            # 1. Buscar Título
            tit = tarjeta.find(['p', 'b', 'h1', 'h3', 'div', 'a'], class_=re.compile(r'(title|name|heading|pod-title|productName)', re.I)) or tarjeta.find('p')
            if not tit:
                continue
            nombre_prod = tit.text.strip().replace("\n", "").replace(",", "")
            if not nombre_prod or len(nombre_prod) < 4:
                continue

            # 2. Buscar Porcentaje de Descuento (ej: -61%)
            pct_tag = tarjeta.find(text=re.compile(r'-\d+%\s*|%\s*OFF', re.I)) or tarjeta.find(class_=re.compile(r'(discount|porcentaje|badge|pct)', re.I))
            porcentaje_txt = "N/A"
            if pct_tag:
                match_pct = re.search(r'(-\d+%|\d+%)', pct_tag.text if hasattr(pct_tag, 'text') else str(pct_tag))
                if match_pct:
                    porcentaje_txt = match_pct.group(1)

            # 3. Extraer todos los precios limpios con Regex (Maneja S/.109.90 o S/. 109,90)
            texto_tarjeta = tarjeta.text
            # Buscamos patrones de precio como S/. 109.90 o S/ 279.90
            precios_encontrados = re.findall(r'(?:S/\.?\s*)(\d+[\.,]\d{2}|\d+)', texto_tarjeta)
            
            valores_limpios = []
            for p_str in precios_encontrados:
                # Cambiamos comas por puntos y lo pasamos a número decimal (float)
                p_limpio = p_str.replace(',', '.')
                try:
                    val = float(p_limpio)
                    # Filtro inteligente para ignorar números sospechosos (como el % de las cuotas)
                    if val > 5 and val not in valores_limpios:
                        valores_limpios.append(val)
                except:
                    continue

            if not valores_limpios:
                continue

            # El menor siempre será el precio con oferta, el mayor el regular
            valores_limpios = sorted(valores_limpios)
            precio_descuento = valores_limpios[0]
            precio_original = valores_limpios[-1] if len(valores_limpios) > 1 else precio_descuento

            # 4. Capturar Link del artículo
            link_tag = tarjeta.find('a', href=True) or (tarjeta if tarjeta.name == 'a' and tarjeta.has_attr('href') else None)
            link_articulo = url_base
            if link_tag and link_tag['href']:
                link_articulo = urljoin(url_base, link_tag['href'])

            # Filtro de talla si aplica
            talla_check = str(talla_buscada).upper().strip()
            if talla_check and talla_check not in ["TODAS", "N/A", ""]:
                patron = r'\b' + re.escape(talla_check) + r'\b'
                if not re.search(patron, tarjeta.text.upper()):
                    continue

            if precio_descuento <= limite_precio:
                productos_encontrados.append({
                    "nombre": nombre_prod, 
                    "precio_original": precio_original,
                    "precio_descuento": precio_descuento,
                    "porcentaje": porcentaje_txt,
                    "link": link_articulo
                })
                
        return productos_encontrados
    except Exception as e:
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
    enviados_en_este_ciclo = set() # Sistema estricto anti-duplicados

    for linea in lineas:
        partes = linea.split(",")
        if len(partes) < 3:
            continue
            
        url_base = partes[0].strip()
        try:
            presupuesto_max = float(partes[1].strip())
        except ValueError:
            presupuesto_max = 100.0
            
        identificador = partes[2].strip()
        
        meta = identificador.split("_")
        tienda = meta[0] if len(meta) > 0 else "General"
        categoria = meta[1] if len(meta) > 1 else "General"
        talla = meta[2] if len(meta) > 2 else "Todas"
        
        conteo_radares += 1
        productos = escanear_tienda(url_base, presupuesto_max, tienda, talla)
        
        for p in productos:
            # Crear una clave única por nombre abreviado para evitar duplicados en la base de datos
            nombre_key = "".join(c for c in p['nombre'] if c.isalnum() or c=='_')[:25]
            id_producto = f"{tienda}_{categoria}_{talla}_{nombre_key}"
            precio_actual = p['precio_descuento']
            
            # Control anti-duplicados en el mismo envío de Telegram
            if id_producto in enviados_en_este_ciclo:
                continue
                
            if id_producto not in historial:
                historial[id_producto] = {}
                
            historial[id_producto][fecha_hoy] = precio_actual
            precios_previos = list(historial[id_producto].values())
            
            if len(precios_previos) == 1 or (len(precios_previos) > 1 and precio_actual < precios_previos[-2]):
                encontrado_oferta = True
                enviados_en_este_ciclo.add(id_producto)
                
                reporte = (
                    f"🚨 *¡OFERTÓN DETECTADO EN {tienda.upper()}!* 🚨\n\n"
                    f"📦 *Producto:* `{p['nombre']}`\n"
                    f"👟 *Talla:* {talla}\n"
                    f"💰 *Precio Regular:* S/. {p['precio_original']:.2f}\n"
                    f"📉 *Descuento:* {p['porcentaje']}\n"
                    f"🔥 *PRECIO CON DESCUENTO:* S/. {p['precio_descuento']:.2f}\n"
                    f"🎯 *Tu Límite Asignado:* S/. {presupuesto_max:.2f}\n\n"
                    f"🔗 *LINK DIRECTO DE COMPRA:* {p['link']}"
                )
                enviar_telegram(reporte)
                
    with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, indent=4)
        
    if not encontrado_oferta:
        enviar_telegram(f"✅ *Escaneo completado.*\nSe revisaron `{conteo_radares}` radares. Los precios se mantienen estables. 🫡")
