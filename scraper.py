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

def enviar_telegram_con_botones(mensaje, url_tienda, tienda_nombre):
    """Envía un reporte premium con botones interactivos directamente al chat"""
    url = f"https://api.telegram.org/bot{TOKEN_REAL}/sendMessage"
    
    # Intentar generar enlace de carrito rápido para Adidas
    url_carrito = url_tienda
    if "adidas" in tienda_nombre.lower():
        # Truco de prefijo de carrito directo para Adidas
        url_carrito = url_tienda.replace(".pe/casacas", ".pe/cart") # Enlace de asistencia o redirección limpia
    
    # Estructura de botones interactivos de Telegram
    teclado = {
        "inline_keyboard": [
            [
                {"text": "🛒 Ir a la Tienda Ahora", "url": url_tienda},
                {"text": "⚡ Añadir a la Cesta", "url": url_carrito}
            ],
            [
                {"text": "🔄 Volver a Escanear Todo", "callback_data": "forzar_escaneo"}
            ]
        ]
    }
    
    payload = {
        "chat_id": ID_REAL,
        "text": mensaje,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps(teclado)
    }
    
    try:
        res = requests.post(url, json=payload, timeout=10)
        print(f"Estado Telegram (Botones): {res.status_code}")
    except Exception as e:
        print(f"Error Telegram Botones: {e}")

def enviar_telegram(mensaje):
    """Envía mensajes de texto simples sin botones (como confirmaciones de estado)"""
    url = f"https://api.telegram.org/bot{TOKEN_REAL}/sendMessage"
    payload = {"chat_id": ID_REAL, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error Telegram Simple: {e}")

def procesar_comandos_telegram():
    url_updates = f"https://api.telegram.org/bot{TOKEN_REAL}/getUpdates"
    try:
        res = requests.get(url_updates, timeout=10)
        if res.status_code == 200:
            datos = res.json()
            if datos.get("ok") and datos.get("result"):
                ultimo_update = datos["result"][-1]
                
                # Procesar si presionaron el botón interactivo de re-escanear o enviaron texto
                callback_query = ultimo_update.get("callback_query", {})
                message_data = ultimo_update.get("message", {})
                
                mensaje_txt = message_data.get("text", "")
                callback_data = callback_query.get("data", "")
                chat_id = str(message_data.get("chat", {}).get("id", "")) or str(callback_query.get("from", {}).get("id", ""))
                
                if chat_id == ID_REAL and (mensaje_txt in ["/resumen", "/start"] or callback_data == "forzar_escaneo"):
                    if callback_data == "forzar_escaneo":
                        enviar_telegram("🔄 _Iniciando escaneo bajo demanda solicitado desde tu botón de Telegram..._")
                    
                    if os.path.exists(URLS_FILE):
                        with open(URLS_FILE, "r", encoding="utf-8") as f:
                            lineas = [l.strip() for l in f.readlines() if l.strip() and "," in l]
                        
                        if lineas and mensaje_txt:
                            texto_resumen = "📋 *Tus Radares Activos actualmente:*\n\n"
                            for l in lineas:
                                partes = l.split(",")
                                meta = partes[2].split("_")
                                tienda = meta[0] if len(meta) > 0 else "General"
                                cat = meta[1] if len(meta) > 1 else "Ropa"
                                talla = meta[2] if len(meta) > 2 else "Todas"
                                texto_resumen += f"🏪 *{tienda.upper()}* | {cat.replace('-', ' ')} | Talla: {talla} | 🚨 Tope: S/. {partes[1]}\n"
                            enviar_telegram(texto_resumen)
                    
                    # Confirmar acción del botón para quitar el reloj de Telegram
                    if callback_data == "forzar_escaneo":
                        url_answer = f"https://api.telegram.org/bot{TOKEN_REAL}/answerCallbackQuery"
                        requests.post(url_answer, json={"callback_query_id": callback_query["id"], "text": "Escaneando tiendas..."}, timeout=5)
                    
                    requests.get(f"{url_updates}?offset={ultimo_update['update_id'] + 1}")
    except Exception as e:
        print(f"Error comandos con botones: {e}")

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
            tit = tarjeta.find(['p', 'b', 'h3', 'div', 'a'], class_=re.compile(r'(title|name|heading|pod-title)', re.I)) or tarjeta.find('p') or tarjeta.find('b')
            prc = tarjeta.find(class_=re.compile(r'(price|sale|oferta|current)', re.I)) or tarjeta.find(lambda tag: tag.name in ['span', 'div'] and 'S/.' in tag.text)
            
            if tit and prc:
                nombre = tit.text.strip().replace("\n", "").replace(",", "")
                text_precio = prc.text.strip()
                
                nums = ''.join(filter(str.isdigit, text_precio))
                if not nums:
                    continue
                    
                p_num = int(nums) / 100 if len(nums) > 4 and ("adidas" in t_low or "marathon" in t_low) else int(nums[:4]) if len(nums) > 5 else int(nums)
                
                if p_num <= limite_precio:
                    texto_tarjeta = tarjeta.text.upper()
                    talla_check = str(talla_buscada).upper().strip()
                    
                    if talla_check and talla_check not in ["TODAS", "S_T", "ST", "ANY"]:
                        patron = r'\b' + re.escape(talla_check) + r'\b'
                        if not re.search(patron, texto_tarjeta):
                            continue
                    
                    productos_encontrados.append({"nombre": nombre, "precio": int(p_num)})
                    
        return productos_encontrados
    except Exception as e:
        print(f"Error procesando {tienda}: {e}")
        return []

def revisar_ofertas():
    print("🚀 Ejecutando Radar con Botones de Compra Express...")
    procesar_comandos_telegram()
    
    if not os.path.exists(URLS_FILE):
        return
        
    historial = cargar_historial()
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    with open(URLS_FILE, "r", encoding="utf-8") as f:
        lineas = f.readlines()

    conteo_radares = 0
    encontrado_alguna_oferta = False

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
                nombre_key = "".join(c for c in p['nombre'] if c.isalnum() or c=='_')[:30]
                id_producto = f"{tienda}_{categoria}_{talla}_{nombre_key}"
                precio_actual = p['precio']
                
                es_nuevo = id_producto not in historial
                if es_nuevo:
                    historial[id_producto] = {}
                
                historial[id_producto][fecha_hoy] = precio_actual
                precios_previos = list(historial[id_producto].values())
                
                if es_nuevo or (len(precios_previos) > 1 and precio_actual < precios_previos[-2]):
                    encontrado_alguna_oferta = True
                    
                    # Mensaje Premium individual por oferta con sus respectivos botones
                    reporte_oferta = (
                        f"🚨 *¡OFERTÓN DETECTADO EN {tienda.upper()}!* 🚨\n\n"
                        f"📦 *Producto:* `{p['nombre']}`\n"
                        f"👟 *Talla Pedida:* {talla}\n"
                        f"💰 *PRECIO ACTUAL:* S/. {precio_actual}\n"
                        f"🎯 *Tu Límite:* S/. {presupuesto_max}\n\n"
                        f"⚡ _Dale clic a los botones de abajo para ir directo al grano sin buscar en Google._"
                    )
                    enviar_telegram_con_botones(reporte_oferta, url_base, tienda)
        except Exception as e:
            continue
            
    guardar_historial(historial)
    
    # Mensaje de confirmación general si lo forzó manualmente y no hay rebajas
    if not encontrado_alguna_oferta:
        enviar_telegram(f"✅ *Radar de Tiendas completado.*\nRevisé tus `{conteo_radares}` enlaces activos. Los precios siguen estables. ¡Sigo vigilando en las sombras! 🫡")

if __name__ == "__main__":
    revisar_ofertas()
