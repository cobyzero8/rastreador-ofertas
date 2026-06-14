import os
import requests
from bs4 import BeautifulSoup
import time
import json
from datetime import datetime

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
    """Revisa si el usuario envió comandos como /resumen antes de ejecutar el scraper"""
    url_updates = f"https://api.telegram.org/bot{TOKEN_REAL}/getUpdates"
    try:
        res = requests.get(url_updates, timeout=10)
        if res.status_code == 200:
            datos = res.json()
            if datos.get("ok") and datos.get("result"):
                # Agarrar el último mensaje recibido
                ultimo_update = datos["result"][-1]
                mensaje_txt = ultimo_update.get("message", {}).get("text", "")
                chat_id = str(ultimo_update.get("message", {}).get("chat", {}).get("id", ""))
                
                # Verificar que sea del dueño del radar
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
                                texto_resumen += f"🏪 *{tienda}* | {cat} | Talla: {talla} | 🚨 Tope: S/. {partes[1]}\n"
                            enviar_telegram(texto_resumen)
                        else:
                            enviar_telegram("📭 No tienes ningún enlace registrado en tu radar todavía.")
                    else:
                        enviar_telegram("⚠️ El archivo de URLs no existe en el servidor.")
                    
                    # Consumir las actualizaciones para limpiar la cola de Telegram
                    requests.get(f"{url_updates}?offset={ultimo_update['update_id'] + 1}")
    except Exception as e:
        print(f"Error procesando comandos: {e}")

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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept-Language": "es-ES,es;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8"
    }
    productos_encontrados = []
    try:
        respuesta = requests.get(url, headers=headers, timeout=15)
        if respuesta.status_code != 200:
            return []
            
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        t_low = tienda.lower()
        
        # 🏢 MOTOR 1: ADIDAS
        if "adidas" in t_low or "adidas" in url:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x) or \
                       soup.find_all('div', attrs={"data-glass-item": "product-card"}) or \
                       soup.find_all('div', class_=lambda x: x and 'grid-item' in x)
                       
            for tarjeta in tarjetas:
                tit = tarjeta.find('p') or tarjeta.find(class_=lambda x: x and 'title' in x) or tarjeta.find('span')
                prc = tarjeta.find(class_=lambda x: x and 'price' in x) or tarjeta.find(class_=lambda x: x and 'sale' in x)
                if tit and prc:
                    nombre = tit.text.strip()
                    nums = ''.join(filter(str.isdigit, prc.text.strip()))
                    if nums:
                        p_num = int(nums) / 100 if len(nums) > 4 else int(nums)
                        if p_num <= limite_precio:
                            productos_encontrados.append({"nombre": nombre, "precio": int(p_num)})

        # 🏢 MOTOR 2: FALABELLA
        elif "falabella" in t_low or "falabella" in url:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x) or \
                       soup.find_all('div', class_=lambda x: x and 'pod-details' in x) or \
                       soup.find_all('div', attrs={"id": lambda x: x and 'testId-pod-' in x})
                       
            for tarjeta in tarjetas:
                tit = tarjeta.find('b') or tarjeta.find(class_=lambda x: x and 'pod-title' in x) or tarjeta.find(class_=lambda x: x and 'title' in x)
                prc = tarjeta.find(class_=lambda x: x and 'prices' in x) or tarjeta.find(class_=lambda x: x and 'price' in x)
                if tit and prc:
                    nombre = tit.text.strip()
                    nums = ''.join(filter(str.isdigit, prc.text.strip()))
                    if nums:
                        p_num = int(nums[:4]) if len(nums) > 5 else int(nums)
                        if p_num <= limite_precio:
                            productos_encontrados.append({"nombre": nombre, "precio": int(p_num)})

        # 🏢 MOTOR 3: MARATHON
        elif "marathon" in t_low or "marathon" in url:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-item' in x) or \
                       soup.find_all('div', class_=lambda x: x and 'productCard' in x)
                       
            for tarjeta in tarjetas:
                tit = tarjeta.find('a', class_=lambda x: x and 'name' in x) or tarjeta.find(class_=lambda x: x and 'title' in x) or tarjeta.find('h3')
                prc = tarjeta.find(class_=lambda x: x and 'price' in x) or tarjeta.find(class_=lambda x: x and 'best-price' in x)
                if tit and prc:
                    nombre = tit.text.strip()
                    nums = ''.join(filter(str.isdigit, prc.text.strip()))
                    if nums:
                        p_num = int(nums) / 100 if len(nums) > 4 else int(nums)
                        if p_num <= limite_precio:
                            productos_encontrados.append({"nombre": nombre, "precio": int(p_num)})

        return productos_encontrados
    except Exception as e:
        print(f"Error escaneando {tienda}: {e}")
        return []

def revisar_ofertas():
    print("🚀 Revisando cola...")
    
    # 🔥 PASO EXTRAS: Procesar comandos de Telegram primero
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
            talla = meta[2] if len(meta) > 2 else "S_T"
            
            conteo_radares += 1
            productos = escanear_tienda(url_base, presupuesto_max, tienda, categoria, talla)
            
            for p in productos:
                nombre_limpio_prod = p['nombre'].replace(" ", "_").replace(",", "").replace("\n", "")
                id_producto = f"{tienda}_{categoria}_{talla}_{nombre_limpio_prod}"
                precio_actual = p['precio']
                
                es_nuevo = id_producto not in historial
                if es_nuevo:
                    historial[id_producto] = {}
                
                historial[id_producto][fecha_hoy] = precio_actual
                
                if es_nuevo or (list(historial[id_producto].values())[-1] > precio_actual):
                    alertas_enviar.append(
                        f"🏪 *Tienda:* {tienda.upper()}\n"
                        f"📦 *Producto:* `{p['nombre']}`\n"
                        f"👟 *Talla:* {talla}\n"
                        f"💰 *Precio Oferta:* S/. {precio_actual}\n"
                        f"🎯 *Tu Tope:* S/. {presupuesto_max}\n"
                        f"🔗 [Ir al enlace]({url_base})\n"
                    )
        except Exception as e:
            continue
            
    guardar_historial(historial)
    
    # 🔥 SIEMPRE mandará respuesta al gatillar el botón para que sepas que se ejecutó con éxito
    if alertas_enviar:
        enviar_telegram("🔥 *¡El Radar encontró rebajas dentro de tu presupuesto!* 🔥\n\n" + "\n".join(alertas_enviar))
    else:
        enviar_telegram(f"✅ *Radar ejecutado con éxito.*\nSe revisaron `{conteo_radares}` enlaces, pero los precios en las tiendas siguen volando por encima de tus topes establecidos. ¡Seguimos vigilando en piloto automático!")

if __name__ == "__main__":
    revisar_ofertas()
