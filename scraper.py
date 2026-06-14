import os
import requests
from bs4 import BeautifulSoup
import time
import json
import re
from datetime import datetime

# ===== TUS CREDENCIALES DE TELEGRAM =====
TOKEN_REAL = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
ID_REAL = "8019752668"

HISTORIAL_FILE = "historial_precios.json"

# --- MAPA DE TALLAS FAMILIAR (FASE 1) ---
TALLAS_OBJETIVO = {
    "ninos": ["1.5", "1.5us", "1.5 us"],
    "mujer": ["5.5", "5.5us", "7", "7us", "5.5 us", "7 us"],
    "hombre": ["9.5", "9.5us", "9.5 us"]
}

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

def verificar_tallas_json(datos_item, categoria):
    """
    Filtro inteligente que escanea el stock de tallas dentro de los datos crudos.
    Retorna True si encuentra stock disponible en las tallas de la familia.
    """
    tallas_validas = TALLAS_OBJETIVO.get(categoria, [])
    if not tallas_validas:
        return True # Si no es calzado, pasa directo
        
    # Validar en estructuras tipo Falabella/Ripley
    texto_búsqueda = json.dumps(datos_item).lower()
    for talla in tallas_validas:
        # Busca si la talla figura con stock disponible o activa
        if f'"size":"{talla}"' in texto_búsqueda or f'"label":"{talla}"' in texto_búsqueda:
            if '"isoutofstock":false' in texto_búsqueda or '"stock":0' not in texto_búsqueda:
                return True
    return False

def escanear_seccion(url, limite_precio, nombre_seccion):
    print(f"🕵️‍♂️ Analizando: {url}")
    
    # Identificar la categoría familiar por el nombre de la sección
    nombre_min = nombre_seccion.lower()
    categoria = "hombre" if "hombre" in nombre_min else "mujer" if "mujer" in nombre_min else "ninos" if ("nino" in nombre_min or "niña" in nombre_min) else "general"

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
                            # Filtro nativo por texto para Adidas si menciona tallas específicas
                            texto_tarjeta = tarjeta.text.lower()
                            tallas_familia = TALLAS_OBJETIVO.get(categoria, [])
                            
                            # Si no es calzado o si encuentra la talla en stock en el HTML, avanza
                            if categoria == "general" or any(t in texto_tarjeta for t in tallas_familia) or "size" not in texto_tarjeta:
                                productos_encontrados.append({"nombre": nombre, "precio": precio_num, "texto": precio_texto})

        # 🟢 MOTOR 2: FALABELLA (Filtro JSON Profundo)
        elif "falabella.com" in url:
            script_datos = soup.find('script', id='__NEXT_DATA__')
            if script_datos:
                datos_json = json.loads(script_datos.string)
                try:
                    items = datos_json['props']['pageProps']['results']
                    for item in items:
                        nombre = item.get('displayName', '').strip()
                        precios = item.get('prices', [])
                        if precios and nombre:
                            precio_minimo = min([int(p['price'][0].replace('.', '').replace(',', '')) for p in precios if p.get('price')])
                            if precio_minimo <= limite_precio:
                                # Aplicamos el filtro de tallas familiar antes de añadirlo
                                if categoria == "general" or verificar_tallas_json(item, categoria):
                                    productos_encontrados.append({"nombre": nombre, "precio": precio_minimo, "texto": f"S/. {precio_minimo}"})
                except Exception as e:
                    print(f"⚠️ Error en JSON Falabella: {e}")

        # 🟢 MOTOR 3: RIPLEY (Filtro Javascript Profundo)
        elif "ripley.com" in url:
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
                                    precio_num = int(precio_oferta / 100)
                                    if precio_num <= limite_precio:
                                        if categoria == "general" or verificar_tallas_json(item, categoria):
                                            productos_encontrados.append({"nombre": nombre, "precio": precio_num, "texto": f"S/. {precio_num}"})
                        except Exception as e:
                            print(f"⚠️ Error en JSON Ripley: {e}")
                            
        return productos_encontrados
    except Exception as e:
        print(f"⚠️ Alerta en {nombre_seccion}: {e}")
        return []

def revisar_ofertas():
    print("🚀 Iniciando rastreador Familiar con Filtro de Tallas Inteligente...")
    if not os.path.exists("urls.txt"): return

    historial = cargar_historial()
    fecha_hoy = datetime.now().strftime("%Y-%m-%d")
    alertas_baja_precio = ""
    hubo_baja = False
    
    with open("urls.txt", "r", encoding="utf-8") as f:
        lineas = f.readlines()

    for linea in lineas:
        linea = linea.strip()
        if not linea or "," not in linea: continue
            
        try:
            partes = linea.split(",")
            url_base = partes[0].strip()
            presupuesto_max = int(partes[1].strip())
            nombre_seccion = partes[2].strip()
        except: continue
        
        print(f"\n📂 Procesando sección: {nombre_seccion}")
        
        for pagina in range(1, 3):
            url_paginada = url_base
            if pagina > 1:
                if "mifarma.com" in url_base or "inkafarma.pe" in url_base: continue 
                if "samsung.com" in url_base:
                    url_paginada = url_base.replace("?", f"page/{pagina}/?") if "?" in url_base else f"{url_base.rstrip('/')}/page/{pagina}/"
                elif "adidas.pe" in url_base or "puma.com" in url_base or "ripley.com" in url_base or "falabella.com" in url_base:
                    url_paginada = f"{url_base}{'&' if '?' in url_base else '?'}page={pagina}"
                elif "platanitos.com" in url_base:
                    url_paginada = f"{url_base}{'&' if '?' in url_base else '?'}pag={pagina}"
            
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
            time.sleep(5)
        time.sleep(5) 
    
    guardar_historial(historial)
    if hubo_baja: enviar_telegram(alertas_baja_precio)

if __name__ == "__main__":
    revisar_ofertas()
