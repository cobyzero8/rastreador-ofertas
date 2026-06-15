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
            
            # Buscamos elementos de precio evitando confundirlos con etiquetas de porcentaje
            precios_tags = tarjeta.find_all(class_=re.compile(r'(price|sale|oferta|current)', re.I)) or tarjeta.find_all(lambda tag: tag.name in ['span', 'div'] and 'S/.' in tag.text)
            
            # Buscar explícitamente si hay un porcentaje de descuento visual en la tarjeta
            pct_tag = tarjeta.find(text=re.compile(r'%\s*(OFF|descuento)?', re.I)) or tarjeta.find(class_=re.compile(r'(discount|porcentaje|pct)', re.I))
            porcentaje_txt = "N/A"
            if pct_tag:
                match_pct = re.search(r'(\d+)\s*%', pct_tag.text if hasattr(pct_tag, 'text') else str(pct_tag))
                if match_pct:
                    porcentaje_txt = f"{match_pct.group(1)}%"

            link_tag = tarjeta.find('a', href=True) or (tarjeta if tarjeta.name == 'a' and tarjeta.has_attr('href') else None)
            link_articulo = url_base
            if link_tag and link_tag['href']:
                link_articulo = urljoin(url_base, link_tag['href'])

            if tit and precios_tags:
                nombre_prod = tit.text.strip().replace("\n", "").replace(",", "")
                
                valores_precios = []
                for p_tag in precios_tags:
                    texto_p = p_tag.text.strip()
                    # Si contiene el símbolo de porcentaje, lo ignoramos para que no contamine los números de precio
                    if "%" in texto_p:
                        continue
                    nums = ''.join(filter(str.isdigit, texto_p))
                    if nums:
                        p_num = int(nums) / 100 if len(nums) > 4 and ("adidas" in t_low or "marathon" in t_low) else int(nums[:4]) if len(nums) > 5 else int(nums)
                        valores_precios.append(int(p_num))
                
                if not valores_precios:
                    continue
                
                # Ordenamos los precios detectados: el menor será el precio de oferta y el mayor el original
                valores_precios = sorted(list(set(valores_precios)))
                precio_descuento = valores_precios[0]
                precio_actual_lista = valores_precios[-1] if len(valores_precios) > 1 else precio_descuento

                if precio_descuento <= limite_precio:
                    talla_check = str(talla_buscada).upper().strip()
                    if talla_check and talla_check not in ["TODAS", "N/A", ""]:
                        patron = r'\b' + re.escape(talla_check) + r'\b'
                        if not re.search(patron, tarjeta.text.upper()):
                            continue
                    
                    productos_encontrados.append({
                        "nombre": nombre_prod, 
                        "precio_original": precio_actual_lista,
                        "precio_descuento": precio_descuento,
                        "porcentaje": porcentaje_txt,
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
        try:
            presupuesto_max = int(partes[1].strip())
        except ValueError:
            presupuesto_max = 100
            
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
            precio_actual = p['precio_descuento']
            
            if id_producto not in historial:
                historial[id_producto] = {}
                
            historial[id_producto][fecha_hoy] = precio_actual
            precios_previos = list(historial[id_producto].values())
            
            if len(precios_previos) == 1 or (len(precios_previos) > 1 and precio_actual < precios_previos[-2]):
                encontrado_oferta = True
                
                # REPORTE MEJORADO CON PRECIO ORIGINAL, PORCENTAJE Y PRECIO DE DESCUENTO
                reporte = (
                    f"🚨 *¡OFERTÓN DETECTADO EN {tienda.upper()}!* 🚨\n\n"
                    f"📦 *Producto:* `{p['nombre']}`\n"
                    f"👟 *Talla:* {talla}\n"
                    f"💰 *Precio Regular:* S/. {p['precio_original']}\n"
                    f"📉 *Descuento:* {p['porcentaje']}\n"
                    f"🔥 *PRECIO CON DESCUENTO:* S/. {p['precio_descuento']}\n"
                    f"🎯 *Tu Límite Asignado:* S/. {presupuesto_max}\n\n"
                    f"🔗 *LINK DIRECTO DE COMPRA:* {p['link']}"
                )
                enviar_telegram(reporte)
                
    with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, indent=4)
        
    if not encontrado_oferta:
        enviar_telegram(f"✅ *Escaneo completado.*\nSe revisaron `{conteo_radares}` radares. No se encontraron rebajas adicionales por debajo del límite. 🫡")
