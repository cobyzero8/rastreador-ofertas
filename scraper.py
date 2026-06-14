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
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error Telegram: {e}")

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

def procesar_comandos_telegram():
    print("📥 Consultando órdenes pendientes en Telegram...")
    url_get_updates = f"https://api.github.com" # Dummy check para limpiar cola rápida si es necesario
    url_tg = f"https://api.telegram.org/bot{TOKEN_REAL}/getUpdates"
    try:
        res = requests.get(url_tg, timeout=10).json()
        if res.get("ok") and res.get("result"):
            for update in res["result"]:
                msg = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                texto = msg.get("text", "").strip().lower()
                
                if chat_id == ID_REAL and texto == "/resumen":
                    if not os.path.exists(URLS_FILE):
                        enviar_telegram("📭 Radar sin enlaces registrados.")
                        return
                    with open(URLS_FILE, "r", encoding="utf-8") as f:
                        urls_activas = f.readlines()
                    
                    reporte = "📋 *Radares Activos en el Sistema Pro:*\n\n"
                    for u in urls_activas:
                        p = u.strip().split(",")
                        if len(p) == 3:
                            meta = p[2].split("_")
                            tienda = meta[0] if len(meta) > 0 else "General"
                            cat = meta[1] if len(meta) > 1 else "Filtro"
                            talla = meta[2] if len(meta) > 2 else "Todas"
                            reporte += f"🔸 *{tienda}* | {cat.replace('_',' ')} (Talla: {talla}) ➡️ Tope: `S/. {p[1]}`\n"
                    
                    reporte += "\n⚡ _Robot ejecutado bajo demanda desde el Panel Pro._"
                    enviar_telegram(reporte)
            
            if res["result"]:
                last_id = res["result"][-1]["update_id"]
                requests.get(f"{url_tg}?offset={last_id + 1}")
    except Exception as e:
        print(f"Error procesando comandos: {e}")

def escanear_tienda(url, limite_precio, tienda, categoria, talla_buscada):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    productos_encontrados = []
    try:
        respuesta = requests.get(url, headers=headers, timeout=15)
        if respuesta.status_code != 200:
            return []
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        
        # 💥 EXTRACCIÓN DINÁMICA DE PRUEBA (Mantenemos la base estable de Adidas)
        if "adidas" in url.lower():
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x) or soup.find_all('div', attrs={"data-glass-item": "product-card"})
            for tarjeta in tarjetas:
                titulo_reg = tarjeta.find('p') or tarjeta.find(class_=lambda x: x and 'title' in x)
                precio_reg = tarjeta.find(class_=lambda x: x and 'price' in x)
                if titulo_reg and precio_reg:
                    nombre = titulo_reg.text.strip()
                    numeros = ''.join(filter(str.isdigit, precio_reg.text.strip()))
                    if numeros:
                        precio_num = int(numeros)
                        # Si el precio es menor o igual al presupuesto familiar
                        if precio_num <= limite_precio:
                            productos_encontrados.append({
                                "nombre": nombre,
                                "precio": precio_num
                            })
        return productos_encontrados
    except Exception as e:
        print(f"Error escaneando {tienda}: {e}")
        return []

def revisar_ofertas():
    print("🚀 Iniciando control cronometrado...")
    procesar_comandos_telegram()
    
    if not os.path.exists(URLS_FILE):
        print("No hay urls.txt")
        return
    historial = cargar_historial()
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    
    with open(URLS_FILE, "r", encoding="utf-8") as f:
        lineas = f.readlines()

    alertas_enviar = []

    for linea in lineas:
        linea = linea.strip()
        if not linea or "," not in linea:
            continue
        try:
            partes = linea.split(",")
            url_base = partes[0].strip()
            presupuesto_max = int(partes[1].strip())
            identificador = partes[2].strip() # Formato: Tienda_Categoria_Talla
            
            meta = identificador.split("_")
            tienda = meta[0] if len(meta) > 0 else "General"
            categoria = meta[1] if len(meta) > 1 else "General"
            talla = meta[2] if len(meta) > 2 else "S_T"
            
            productos = escanear_tienda(url_base, presupuesto_max, tienda, categoria, talla)
            
            for p in productos:
                # Nombre de clave único para la base de datos
                nombre_limpio_prod = p['nombre'].replace(" ", "_").replace(",", "")
                id_producto = f"{tienda}_{categoria}_{talla}_{nombre_limpio_prod}"
                precio_actual = p['precio']
                
                # Revisar si es una caída histórica o producto nuevo en oferta
                es_nuevo = id_producto not in historial
                
                if es_nuevo:
                    historial[id_producto] = {}
                
                # Guardamos el precio de hoy
                historial[id_producto][fecha_hoy] = precio_actual
                
                # Si es nuevo o bajó de precio respecto a la última fecha, disparamos alerta de Telegram
                if es_nuevo:
                    alertas_enviar.append(
                        f"🚨 *¡OFERTA DETECTADA EN {tienda.upper()}!*\n"
                        f"📦 Producto: `{p['nombre']}`\n"
                        f"👟 Talla: *{talla}*\n"
                        f"💰 Precio actual: *S/. {precio_actual}*\n"
                        f"🎯 Presupuesto tope: S/. {presupuesto_max}\n"
                    )
        except Exception as e:
            print(f"Error en línea: {e}")
            continue
            
    guardar_historial(historial)
    
    # Enviar alertas acumuladas si existen
    if alertas_enviar:
        enviar_telegram("🔥 ¡Atención! El Radar detectó rebajas que entran en tu presupuesto:\n\n" + "\n".join(alertas_enviar))
    
    print("🏁 Ciclo completado con éxito.")

if __name__ == "__main__":
    revisar_ofertas()
                             
