import os
import requests
from bs4 import BeautifulSoup
import time
import json
import re
from datetime import datetime

# ===== CREDENCIALES =====
TOKEN_REAL = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
ID_REAL = "8019752668"
HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

TALLAS_OBJETIVO = {
    "ninos": ["1.5", "1.5us", "1.5 us"],
    "mujer": ["5.5", "5.5us", "7", "7us", "5.5 us", "7 us"],
    "hombre": ["9.5", "9.5us", "9.5 us"]
}

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN_REAL}/sendMessage"
    payload = {"chat_id": ID_REAL, "text": mensaje, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except Exception as e: print(f"Error Telegram: {e}")

def cargar_historial():
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def guardar_historial(historial):
    try:
        with open(HISTORIAL_FILE, "w", encoding="utf-8") as f: json.dump(historial, f, indent=4)
    except Exception as e: print(f"Error guardando historial: {e}")

def verificar_tallas_json(datos_item, categoria):
    tallas_validas = TALLAS_OBJETIVO.get(categoria, [])
    if not tallas_validas: return True
    texto_busqueda = json.dumps(datos_item).lower()
    for talla in tallas_validas:
        if f'"size":"{talla}"' in texto_busqueda or f'"label":"{talla}"' in texto_busqueda:
            if '"isoutofstock":false' in texto_busqueda or '"stock":0' not in texto_busqueda:
                return True
    return False

# === 🧠 PROCESADOR AUTOMÁTICO DE COMANDOS ANTES DEL ESCANEO ===
def procesar_comandos_telegram():
    print("📥 Revisando si el usuario dejó órdenes en Telegram...")
    url_get_updates = f"https://api.telegram.org/bot{TOKEN_REAL}/getUpdates"
    try:
        res = requests.get(url_get_updates, timeout=10).json()
        if res.get("ok") and res.get("result"):
            for update in res["result"]:
                msg = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                texto = msg.get("text", "").strip().lower()
                
                if chat_id == ID_REAL:
                    if texto in ["/start", "/ayuda", "hola"]:
                        enviar_telegram(
                            "🤖 *Radar Familiar Autónomo v4.0*\n\n"
                            "He recibido tu orden. Estoy programado para escanear de forma automática 4 veces al día.\n"
                            "Comandos válidos:\n"
                            "🔹 `/resumen` : Te enviaré el estado de las colas de monitoreo."
                        )
                    elif texto == "/resumen":
                        historial = cargar_historial()
                        if not os.path.exists(URLS_FILE): return
                        with open(URLS_FILE, "r", encoding="utf-8") as f:
                            urls_activas = f.readlines()
                        
                        reporte = "📋 *Estado de Monitoreo Familiar Activo:*\n\n"
                        for u in urls_activas:
                            p = u.strip().split(",")
                            if len(p) == 3:
                                reporte += f"🔸 `{p[2]}` (Tope: S/. {p[1]})\n"
                        
                        reporte += "\n💡 _Monitoreo automático en ejecución..._"
                        enviar_telegram(reporte)
            
            # Limpiamos las actualizaciones consumidas para que no se repitan
            if res["result"]:
                last_id = res["result"][-1]["update_id"]
                requests.get(f"{url_get_updates}?offset={last_id + 1}")
    except Exception as e:
        print(f"Error en escucha del Bot: {e}")

def escanear_seccion(url, limite_precio, nombre_seccion):
    nombre_min = nombre_seccion.lower()
    categoria = "hombre" if "hombre" in nombre_min else "mujer" if "mujer" in nombre_min else "ninos" if ("nino" in nombre_min or "niña" in nombre_min) else "general"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    productos_encontrados = []
    try:
        respuesta = requests.get(url, headers=headers, timeout=15)
        if respuesta.status_code != 200: return []
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        
        if "adidas" in url:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x) or soup.find_all('div', attrs={"data-glass-item": "product-card"})
            for tarjeta in tarjetas:
                titulo_reg = tarjeta.find(class_=lambda x: x and 'title' in x) or tarjeta.find('p')
                precio_reg = tarjeta.find(class_=lambda x: x and 'price' in x) or tarjeta.find(class_=lambda x: x and 'sale' in x)
                if titulo_reg and precio_reg:
                    nombre = titulo_reg.text.strip()
                    numeros = ''.join(filter(str.isdigit, precio_reg.text.strip()))
                    if numeros:
                        precio_num = int(numeros)
                        if precio_num <= limite_precio:
                            if categoria == "general" or any(t in tarjeta.text.lower() for t in TALLAS_OBJETIVO.get(categoria, [])):
                                productos_encontrados.append({"nombre": nombre, "precio": precio_num, "texto": f"S/. {precio_num}"})
                                
        elif "falabella.com" in url:
            script_datos = soup.find('script', id='__NEXT_DATA__')
            if script_datos:
                items = json.loads(script_datos.string)['props']['pageProps']['results']
                for item in items:
                    nombre = item.get('displayName', '').strip()
                    precios = item.get('prices', [])
                    if precios and nombre:
                        precio_minimo = min([int(p['price'][0].replace('.', '').replace(',', '')) for p in precios if p.get('price')])
                        if precio_minimo <= limite_precio and (categoria == "general" or verificar_tallas_json(item, categoria)):
                            productos_encontrados.append({"nombre": nombre, "precio": precio_minimo, "texto": f"S/. {precio_minimo}"})

        elif "ripley.com" in url:
            scripts = soup.find_all('script')
            for s in scripts:
                if s.string and "__PRELOADED_STATE__" in s.string:
                    texto_json = re.search(r'window\.__PRELOADED_STATE__\s*=\s*({.*?});', s.string)
                    if texto_json:
                        items = json.loads(texto_json.group(1)).get('products', [])
                        for item in items:
                            nombre = item.get('name', '').strip()
                            precio_oferta = item.get('prices', {}).get('offer', 0) or item.get('prices', {}).get('card', 0)
                            if precio_oferta and nombre:
                                precio_num = int(precio_oferta / 100)
                                if precio_num <= limite_precio and (categoria == "general" or verificar_tallas_json(item, categoria)):
                                    productos_encontrados.append({"nombre": nombre, "precio": precio_num, "texto": f"S/. {precio_num}"})
        return productos_encontrados
    except: return []

def revisar_ofertas():
    print("🚀 Ejecutando ciclo de control...")
    procesar_comandos_telegram() # <-- AQUÍ EL BOT ESCUCHA SOLO
    
    if not os.path.exists(URLS_FILE): return
    historial = cargar_historial()
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    alertas_baja_precio = ""
    hubo_baja = False
    
    with open(URLS_FILE, "r", encoding="utf-8") as f:
        lineas = f.readlines()

    for linea in lineas:
        linea = linea.strip()
        if not linea or "," not in linea: continue
        try:
            partes = linea.split(",")
            if not partes[1].strip().isdigit(): continue
            url_base = partes[0].strip()
            presupuesto_max = int(partes[1].strip())
            nombre_seccion = partes[2].strip()
        except: continue
        
        for pagina in range(1, 3):
            url_paginada = url_base
            if pagina > 1:
                url_paginada = f"{url_base}{'&' if '?' in url_base else '?'}page={pagina}"
            
            productos = escanear_seccion(url_paginada, presupuesto_max, nombre_seccion)
            for p in productos:
                id_producto = f"{nombre_seccion}_{p['nombre']}"
                precio_actual = p['precio']
                
                if id_producto in historial:
                    registro_previo = historial[id_producto]
                    if not isinstance(registro_previo, dict):
                        historial[id_producto] = {"2026-06-13": registro_previo}
                        registro_previo = historial[id_producto]
                    fechas_ordenadas = sorted(registro_previo.keys())
                    precio_anterior = registro_previo[fechas_ordenadas[-1]]
                    
                    if precio_actual < precio_anterior:
                        hubo_baja = True
                        alertas_baja_precio += (
                            f"📉 *¡OFERTA FAMILIAR VALIDADA!* 📉\n"
                            f"📦 *Producto:* {p['nombre']}\n"
                            f"💰 *Antes:* S/. {precio_anterior} ➡️ *Ahora:* {p['texto']}\n"
                            f"🏷️ *Sección:* {nombre_seccion}\n"
                            f"🔗 [Ir a la Oferta]({url_paginada})\n\n"
                            f"--- \n\n"
                        )
                else:
                    historial[id_producto] = {}
                historial[id_producto][fecha_hoy] = precio_actual
            time.sleep(2)
    
    guardar_historial(historial)
    if hubo_baja: enviar_telegram(alertas_baja_precio)
    print("🏁 Fin del proceso.")

if __name__ == "__main__":
    revisar_ofertas()
       
                             
