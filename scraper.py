import os
import requests
from bs4 import BeautifulSoup
import time
import json
import re

# ===== TUS CREDENCIALES DE TELEGRAM =====
TOKEN_REAL = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
ID_REAL = "8019752668"

HISTORIAL_FILE = "historial_precios.json"

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN_REAL}/sendMessage"
    payload = {
        "chat_id": ID_REAL,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Error al enviar a Telegram: {e}")

def cargar_historial():
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

def guardar_historial(historial):
    try:
        with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
            json.dump(historial, f, indent=4)
    except Exception as e:
        print(f"Error al guardar historial: {e}")

def escanear_seccion(url, limite_precio, nombre_seccion):
    print(f"🕵️‍♂️ Analizando: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Referer": "https://www.google.com/"
    }
    
    productos_encontrados = []
    
    try:
        respuesta = requests.get(url, headers=headers, timeout=20)
        if respuesta.status_code != 200:
            print(f"⚠️ Servidor respondió con código {respuesta.status_code} en {nombre_seccion}")
            return []
            
        html_puro = respuesta.text
        soup = BeautifulSoup(html_puro, 'html.parser')
        
        # 🟢 MOTOR 1: ADIDAS
        if "adidas" in url:
            tarjetas = soup.find_all('div', class_=lambda x: x and 'product-card' in x)
            for tarjeta in tarjetas:
                titulo_reg = tarjeta.find(class_=lambda x: x and 'title' in x)
                precio_reg = tarjeta.find(class_=lambda x: x and 'price' in x)
                if titulo_reg and precio_reg:
                    nombre = titulo_reg.text.strip()
                    precio_texto = precio_reg.text.strip()
                    numeros = ''.join(filter(str.isdigit, precio_texto))
                    if numeros:
                        precio_num = int(numeros)
                        if precio_num <= limite_precio:
                            productos_encontrados.append({"nombre": nombre, "precio": precio_num, "texto": precio_texto})

        # 🟢 MOTOR 2: FALABELLA (Inyección de datos crudos estructurados)
        elif "falabella.com" in url:
            script_datos = soup.find('script', id='__NEXT_DATA__')
            if script_datos:
                datos_json = json.loads(script_datos.string)
                try:
                    items = datos_json['props']['pageProps']['results']
                    for item in items:
                        nombre = item.get('displayName', '').strip()
                        # Buscamos el precio más bajo disponible (oferta o tarjeta)
                        precios = item.get('prices', [])
                        if precios and nombre:
                            precio_minimo = min([int(p['price'][0].replace('.', '').replace(',', '')) for p in precios if p.get('price')])
                            if precio_minimo <= limite_precio:
                                productos_encontrados.append({"nombre": nombre, "precio": precio_minimo, "texto": f"S/. {precio_minimo}"})
                except Exception as e:
                    print(f"⚠️ Error procesando JSON interno de Falabella: {e}")

        # 🟢 MOTOR 3: RIPLEY
        elif "ripley.com" in url:
            # Ripley inyecta sus productos en una variable global de javascript llamada __PRELOADED_STATE__
            scripts = soup.find_all('script')
            for s in scripts:
                if s.string and "__PRELOADED_STATE__" in s.string:
                    texto_json = re.search(r'window\.__PRELOADED_STATE__\s*=\s*({.*?});', s.string)
                    if texto_json:
                        datos_json = json.loads(texto_json.group(1))
                        try:
                            items = datos_json.get('products', [])
                            for item in items:
                                nombre = item.get('name', '').strip()
                                precio_oferta = item.get('prices', {}).get('offer', 0) or item.get('prices', {}).get('card', 0)
                                if precio_oferta and nombre:
                                    precio_num = int(precio_oferta / 100) # Ripley guarda decimales pegados
                                    if precio_num <= limite_precio:
                                        productos_encontrados.append({"nombre": nombre, "precio": precio_num, "texto": f"S/. {precio_num}"})
                        except Exception as e:
                            print(f"⚠️ Error decodificando productos de Ripley: {e}")
                            
        return productos_encontrados
    except Exception as e:
        print(f"⚠️ Alerta de conexión en {nombre_seccion}: {e}")
        return []

def revisar_ofertas():
    print("🚀 Iniciando rastreador Multi-Retailer Avanzado (Falabella/Ripley/Adidas)...")
    
    if not os.path.exists("urls.txt"):
        print("Error: No existe urls.txt")
        return

    historial = cargar_historial()
    alertas_baja_precio = ""
    hubo_baja = False
    
    with open("urls.txt", "r", encoding="utf-8") as f:
        lineas = f.readlines()

    for linea in lineas:
        linea = linea.strip()
        if not linea or "," not in linea:
            continue
            
        try:
            partes = linea.split(",")
            url_base = partes[0].strip()
            presupuesto_max = int(partes[1].strip())
            nombre_seccion = partes[2].strip()
        except Exception as e:
            print(f"⚠️ Saltando línea inválida en urls.txt: {linea}. Error: {e}")
            continue
        
        print(f"\n📂 Procesando sección: {nombre_seccion}")
        
        for pagina in range(1, 3):
            url_paginada = url_base
            
            if pagina > 1:
                if "mifarma.com" in url_base or "inkafarma.pe" in url_base:
                    continue 
                
                if "samsung.com" in url_base:
                    url_paginada = url_base.replace("?", f"page/{pagina}/?") if "?" in url_base else f"{url_base.rstrip('/')}/page/{pagina}/"
                elif "adidas.pe" in url_base or "puma.com" in url_base or "ripley.com" in url_base or "falabella.com" in url_base:
                    conector = "&" if "?" in url_base else "?"
                    url_paginada = f"{url_base}{conector}page={pagina}"
                elif "platanitos.com" in url_base:
                    conector = "&" if "?" in url_base else "?"
                    url_paginada = f"{url_base}{conector}pag={pagina}"
            
            productos = escanear_seccion(url_paginada, presupuesto_max, f"{nombre_seccion}_P{pagina}")
            
            for p in productos:
                id_producto = f"{nombre_seccion}_{p['nombre']}"
                precio_actual = p['precio']
                
                if id_producto in historial:
                    precio_anterior = historial[id_producto]
                    
                    if precio_actual < precio_anterior:
                        hubo_baja = True
                        alertas_baja_precio += (
                            f"📉 *¡BAJÓ DE PRECIO INMEDIATO!* 📉\n"
                            f"📦 *Producto:* {p['nombre']}\n"
                            f"💰 *Antes:* S/. {precio_anterior} ➡️ *Ahora:* {p['texto']}\n"
                            f"🏷️ *Sección:* {nombre_seccion} (Pág. {pagina})\n"
                            f"🔗 [Ir a la Oferta]({url_paginada})\n\n"
                            f"--- \n\n"
                        )
                
                historial[id_producto] = precio_actual
            
            time.sleep(5) # Pausa técnica anti-bloqueo entre páginas
        time.sleep(5) 
    
    guardar_historial(historial)
    
    if hubo_baja:
        enviar_telegram(alertas_baja_precio)
    else:
        print("\nEl robot terminó con éxito. Todo el catálogo multi-retailer está analizado.")

if __name__ == "__main__":
    revisar_ofertas()
