import os
import requests
from bs4 import BeautifulSoup
import time
import json
from datetime import datetime
import re

TOKEN_REAL = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
ID_REAL = "8019752668"
HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN_REAL}/sendMessage"
    payload = {"chat_id": ID_REAL, "text": mensaje, "parse_mode": "Markdown"}
    try:
        res = requests.post(url, json=payload, timeout=10)
        print(f"Estado Telegram: {res.status_code}")
    except Exception as e:
        print(f"Error Telegram: {e}")

def procesar_comandos_telegram():
    url_updates = f"https://api.telegram.org/bot{TOKEN_REAL}/getUpdates"
    try:
        res = requests.get(url_updates, timeout=10)
        if res.status_code == 200:
            datos = res.json()
            if datos.get("ok") and datos.get("result"):
                ultimo_update = datos["result"][-1]
                mensaje_txt = ultimo_update.get("message", {}).get("text", "")
                chat_id = str(ultimo_update.get("message", {}).get("chat", {}).get("id", ""))
                
                if chat_id == ID_REAL and mensaje_txt in ["/resumen", "/start"]:
                    if os.path.exists(URLS_FILE):
                        with open(URLS_FILE, "r", encoding="utf-8") as f:
                            lineas = [l.strip() for l in f.readlines() if l.strip() and "," in l]
                        
                        if lineas:
                            texto_resumen = "📋 *Tus Radares Activos actualmente:*\n\n"
                            for l in lineas:
                                partes = l.split(",")
                                meta = partes[2].split("_")
                                tienda = meta[0] if len(meta) > 0 else "General"
                                cat = meta[1] if len(meta) > 1 else "Ropa"
                                talla = meta[2] if len(meta) > 2 else "Todas"
                                texto_resumen += f"🏪 *{tienda.upper()}* | {cat.replace('-', ' ')} | Talla: {talla} | 🚨 Tope: S/. {partes[1]}\n"
                            enviar_telegram(texto_resumen)
                        else:
                            enviar_telegram("📭 No tienes ningún enlace registrado en tu radar todavía.")
                    
                    requests.get(f"{url_updates}?offset={ultimo_update['update_id'] + 1}")
    except Exception as e:
        print(f"Error comandos: {e}")

def cargar_historial():
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def guardar_historial(historial):
    with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, indent=4)

def escanear_tienda(url, limite_precio, tienda, categoria, talla_buscada):
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
        "Accept-Language": "es-PE,es-ES;q=0.9,es;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    productos_encontrados = []
    try:
        respuesta = requests.get(url, headers=headers, timeout=15)
        if respuesta.status_code != 200:
            return []
            
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        t_low = tienda.lower()
        
        # --- SELECTORES MAESTROS POR TIENDA ---
        tarjetas = []
        
        if "adidas" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x) or soup.find_all('div', attrs={"data-glass-item": "product-card"})
        elif "falabella" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x) or soup.find_all('div', class_=lambda x: x and 'pod-details' in x)
        elif "marathon" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-item' in x) or soup.find_all('div', class_=lambda x: x and 'productCard' in x)
        elif "ripley" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'catalog-product' in x) or soup.find_all('a', class_='ProductCard__ProductLink')
        elif "platanitos" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product' in x) or soup.find_all('div', class_='col-xs-6')
        elif "puma" in t_low or "nike" in t_low:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-grid' in x) or soup.find_all('div', class_=lambda x: x and 'item' in x)

        for tarjeta in tarjetas:
            # Extracción genérica adaptable de Título y Precio
            tit = tarjeta.find(['p', 'b', 'h3', 'div', 'a'], class_=re.compile(r'(title|name|heading|pod-title)', re.I)) or tarjeta.find('p') or tarjeta.find('b')
            prc = tarjeta.find(class_=re.compile(r'(price|sale|oferta|current)', re.I)) or tarjeta.find(lambda tag: tag.name in ['span', 'div'] and 'S/.' in tag.text)
            
            if tit and prc:
                nombre = tit.text.strip().replace("\n", "").replace(",", "")
                text_precio = prc.text.strip()
                
                # Extraer números limpios del precio
                nums = ''.join(filter(str.isdigit, text_precio))
                if not nums:
                    continue
                    
                p_num = int(nums) / 100 if len(nums) > 4 and ("adidas" in t_low or "marathon" in t_low) else int(nums[:4]) if len(nums) > 5 else int(nums)
                
                if p_num <= limite_precio:
                    # 👟 FILTRO INTELIGENTE DE TALLA EN TEXTO O CONTENEDOR
                    texto_tarjeta = tarjeta.text.upper()
                    talla_check = str(talla_buscada).upper().strip()
                    
                    # Si el usuario especificó una talla (no es TODAS o S_T)
                    if talla_check and talla_check not in ["TODAS", "S_T", "ST", "ANY"]:
                        # Verificamos si la talla exacta se menciona dentro de la tarjeta del producto
                        # Agrega límites de palabra para evitar que "S" coincida dentro de "SMART"
                        patron = r'\b' + re.escape(talla_check) + r'\b'
                        if not re.search(patron, texto_tarjeta):
                            continue # Si no está su talla disponible, saltamos este producto
                    
                    productos_encontrados.append({"nombre": nombre, "precio": int(p_num)})
                    
        return productos_encontrados
    except Exception as e:
        print(f"Error procesando {tienda}: {e}")
        return []

def revisar_ofertas():
    print("🚀 Ejecutando Radar Completo...")
    procesar_comandos_telegram()
    
    if not os.path.exists(URLS_FILE):
        return
        
    historial = cargar_historial()
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    with open(URLS_FILE, "r", encoding="utf-8") as f:
        lineas = f.readlines()

    alertas_enviar = []
    conteo_radares = 0

    for linea in lineas:
        linea = linea.strip()
        if not linea or "," not in linea:
            continue
        try:
            partes = linea.split(",")
            url_base = partes[0].strip()
            presupuesto_max = int(partes[1].strip())
            identificador = partes[2].strip()
            
            meta = identificador.split("_")
            tienda = meta[0] if len(meta) > 0 else "General"
            categoria = meta[1] if len(meta) > 1 else "General"
            talla = meta[2] if len(meta) > 2 else "Todas"
            
            conteo_radares += 1
            productos = escanear_tienda(url_base, presupuesto_max, tienda, categoria, talla)
            
            for p in productos:
                # Normalizar nombre para la clave del JSON
                nombre_key = "".join(c for c in p['nombre'] if c.isalnum() or c=='_')[:30]
                id_producto = f"{tienda}_{categoria}_{talla}_{nombre_key}"
                precio_actual = p['precio']
                
                es_nuevo = id_producto not in historial
                if es_nuevo:
                    historial[id_producto] = {}
                
                historial[id_producto][fecha_hoy] = precio_actual
                
                # Alerta si es nuevo o si el precio de hoy bajó comparado con el anterior histórico
                precios_previos = list(historial[id_producto].values())
                if es_nuevo or (len(precios_previos) > 1 and precio_actual < precios_previos[-2]):
                    alertas_enviar.append(
                        f"🏪 *TIENDA:* {tienda.upper()}\n"
                        f"📦 *Producto:* `{p['nombre']}`\n"
                        f"👟 *Talla Solicitada:* {talla}\n"
                        f"💰 *PRECIO REBAJADO:* S/. {precio_actual}\n"
                        f"🎯 *Tu Tope:* S/. {presupuesto_max}\n"
                        f"🔗 [Abrir Oferta en la Tienda]({url_base})\n"
                        f"⚡ _¡Corre antes que se agote!_\n"
                    )
        except Exception as e:
            continue
            
    guardar_historial(historial)
    
    # Envío del reporte estético final
    if alertas_enviar:
        enviar_telegram("🔥 *¡ATENCIÓN! CAZAMOS LIQUIDACIONES REALES!* 🔥\n\n" + "\n" + "—"*15 + "\n\n".join(alertas_enviar))
    else:
        enviar_telegram(f"✅ *Radar General Corriendo con éxito.*\nSe escanearon `{conteo_radares}` rutas para todas las tiendas de tu lista. Los precios se mantienen estables. ¡Piloto automático vigilando! 🫡")

if __name__ == "__main__":
    revisar_ofertas()
