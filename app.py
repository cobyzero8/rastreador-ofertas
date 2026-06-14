import streamlit as st
import json
import os
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Radar Pro - Panel Central", layout="wide")

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"
TOKEN_REAL = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
ID_REAL = "8019752668"

# --- FUNCIONES DEL ROBOT (SCRAPER INTEGRADO NATIVAMENTE) ---
def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TOKEN_REAL}/sendMessage"
    payload = {"chat_id": ID_REAL, "text": mensaje, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        st.sidebar.error(f"Error Telegram: {e}")

def escanear_tienda(url, limite_precio, tienda, categoria, talla_buscada):
    productos_encontrados = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        respuesta = requests.get(url, headers=headers, timeout=15)
        if respuesta.status_code != 200:
            return []
            
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        t_low = tienda.lower()
        tarjetas = []
        
        # Selectores robustos según la tienda
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
            
            if tit and prc:
                nombre = tit.text.strip().replace("\n", "").replace(",", "")
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
                    
                    productos_encontrados.append({"nombre": nombre, "precio": int(p_num)})
        return productos_encontrados
    except:
        return []

def ejecutar_escaneo_completo():
    if not os.path.exists(URLS_FILE):
        return False, "No tienes ningún enlace registrado para escanear."
        
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
        return False, "El archivo urls.txt está vacío."

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
        productos = escanear_tienda(url_base, presupuesto_max, tienda, categoria, talla)
        
        for p in productos:
            nombre_key = "".join(c for c in p['nombre'] if c.isalnum() or c=='_')[:30]
            id_producto = f"{tienda}_{categoria}_{talla}_{nombre_key}"
            precio_actual = p['precio']
            
            if id_producto not in historial:
                historial[id_producto] = {}
                
            historial[id_producto][fecha_hoy] = precio_actual
            precios_previos = list(historial[id_producto].values())
            
            # Si es nuevo o bajó de precio con respecto a la última vez
            if len(precios_previos) == 1 or (len(precios_previos) > 1 and precio_actual < precios_previos[-2]):
                encontrado_oferta = True
                reporte = (
                    f"🚨 *¡OFERTÓN EN {tienda.upper()}!* 🚨\n\n"
                    f"📦 *Producto:* `{p['nombre']}`\n"
                    f"👟 *Talla:* {talla}\n"
                    f"💰 *PRECIO:* S/. {precio_actual}\n"
                    f"🎯 *Tope:* S/. {presupuesto_max}\n"
                )
                enviar_telegram(reporte)
                
    with open(HISTORIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(historial, f, indent=4)
        
    if not encontrado_oferta:
        enviar_telegram(f"✅ *Escaneo manual completado.*\nSe revisaron `{conteo_radares}` radares. Todo sigue igual. 🫡")
        
    return True, f"Escaneo completado. Se revisaron {conteo_radares} enlaces."


# --- SIDEBAR: INTERFAZ MÁSTER ---
with st.sidebar:
    st.title("⚙️ Control Maestro")
    
    # CONTENEDOR DINÁMICO PARA EL FEEDBACK DEL ESCANEO
    status_placeholder = st.empty()
    
    if st.button("💥 FORZAR ESCANEO", use_container_width=True):
        status_placeholder.info("⏳ Ejecutando escaneo en vivo... Por favor espera.")
        # Llamamos directo a la función nativa sin os.system
        exito, mensaje = ejecutar_escaneo_completo()
        if exito:
            status_placeholder.success(f"✅ {mensaje}")
            st.rerun()
        else:
            status_placeholder.error(f"❌ Error: {mensaje}")
            
    st.write("---")
    menu = st.radio("Navegación", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces"])


# --- PESTAÑA 1: DASHBOARD DE OFERTAS ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Radar Familiar Pro")
    st.subheader("📊 Dashboard: Artículos bajo vigilancia")
    
    # Generar mapeo de links basado en urls.txt para que SIEMPRE salgan las URLs reales
    links_mapeados = {}
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            for line in f.readlines():
                p = line.strip().split(",")
                if len(p) >= 3:
                    # Guardamos la URL usando la combinación Tienda_Nombre_Talla
                    links_mapeados[p[2]] = p[0]

    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                lista = []
                for id_prod, hist in data.items():
                    parts = id_prod.split("_")
                    
                    # Generamos la clave para buscar su link original
                    clave_buscar = f"{parts[0]}_{parts[1]}_{parts[2]}" if len(parts) > 2 else id_prod
                    link_final = links_mapeados.get(clave_buscar, "#")
                    
                    lista.append({
                        "Tienda": parts[0],
                        "Producto": parts[1].replace("-", " "),
                        "Talla": parts[2] if len(parts) > 2 else "N/A",
                        "Precio": f"S/. {list(hist.values())[-1]}",
                        "Link de Compra": link_final
                    })
                
                df = pd.DataFrame(lista)
                if not df.empty:
                    st.data_editor(
                        df,
                        column_config={"Link de Compra": st.column_config.LinkColumn("Compra Directa")},
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("El historial está vacío. Ejecuta un escaneo.")
            except Exception as e:
                st.error(f"Error procesando historial: {e}")
    else:
        st.info("No hay datos históricos disponibles. Registra tus enlaces y presiona 'FORZAR ESCANEO'.")


# --- PESTAÑA 2: GESTIONAR ENLACES (MÁXIMA INFORMACIÓN) ---
elif menu == "🛠️ Gestionar Enlaces":
    st.title("🛠️ Gestionar Enlaces Pro")
    
    with st.container(border=True):
        st.write("### 📝 Registrar nuevo artículo")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            tienda = st.selectbox("Tienda", ["Adidas", "Falabella", "Marathon", "Ripley", "Puma", "Nike"])
            nombre = st.text_input("Nombre del producto (Usa guiones: Ej: Zapatilla-Nike-Retro)")
        with c2:
            url = st.text_input("URL exacta del producto")
            talla = st.text_input("Talla (Ej: 9.5US o M)")
        with c3:
            precio_max = st.number_input("Precio máximo aceptable (Tope S/.)", value=150, min_value=1)
            st.write("###")
            if st.button("💾 GUARDAR ARTÍCULO", type="primary", use_container_width=True):
                if nombre and url:
                    # GUARDADO CON 'a' (APPEND) PARA ASEGURAR QUE NUNCA SE BORREN LOS ANTERIORES
                    nombre_limpio = nombre.replace(" ", "-")
                    nueva_linea = f"{url},{precio_max},{tienda}_{nombre_limpio}_{talla}\n"
                    
                    with open(URLS_FILE, "a", encoding="utf-8") as f:
                        f.write(nueva_linea)
                        
                    st.toast("✅ ¡Artículo guardado de forma permanente!")
                    st.rerun()
                else:
                    st.error("❌ Por favor, ingresa obligatoriamente el Nombre y la URL.")

    st.write("---")
    st.subheader("📋 Lista de Radares Configurados Activos")
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            lineas = f.read()
            if lineas.strip():
                st.code(lineas)
            else:
                st.info("No tienes ningún artículo en tu lista de monitoreo.")
    else:
        st.info("Aún no se ha creado el archivo de configuración de enlaces.")
