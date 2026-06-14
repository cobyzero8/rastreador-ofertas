import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime
import requests

st.set_page_config(
    page_title="CobyZero8 - Radar App",
    page_icon="🕵️‍♂️",
    layout="wide"
)

# ===== MISMAS CREDENCIALES DEL SISTEMA =====
TOKEN_REAL = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
ID_REAL = "8019752668"
HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

# --- FUNCIONES DE CONTROL DE DATOS ---
def cargar_historial():
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

def cargar_urls():
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            return [linea.strip() for linea in f.readlines() if linea.strip() and "," in linea]
    return []

def guardar_urls(lista_lineas):
    with open(URLS_FILE, "w", encoding="utf-8") as f:
        for linea in lista_lineas:
            f.write(f"{linea}\n")

def enviar_respuesta_telegram(texto):
    url = f"https://api.telegram.org/bot{TOKEN_REAL}/sendMessage"
    payload = {"chat_id": ID_REAL, "text": texto, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except Exception as e: print(f"Error: {e}")

# --- DISEÑO DE LA INTERFAZ ---
st.title("🕵️‍♂️ CobyZero8 - Radar & Panel de Control")
st.markdown("---")

# Menú lateral ampliado para control del Bot interactivo
menu = st.sidebar.selectbox("Navegación", [
    "📈 Ver Dashboard", 
    "📊 Gráficos de Tendencia", 
    "🛠️ Gestionar Enlaces (Anti-Caídas)",
    "🤖 Servidor del Bot Telegram"
])

# ====== VISTA 1: EL DASHBOARD ======
if menu == "📈 Ver Dashboard":
    st.subheader("📊 Monitoreo en Tiempo Real")
    datos = cargar_historial()
    
    if not datos:
        st.info("⌛ Esperando la primera carrera del robot para mostrar el catálogo.")
    else:
        lista_productos = []
        for clave, precio in datos.items():
            seccion, nombre_producto = clave.split("_", 1) if "_" in clave else ("General", clave)
            
            if isinstance(precio, dict):
                ultimo_par_de_fechas = sorted(precio.keys())[-1]
                precio_final = precio[ultimo_par_de_fechas]
            else:
                precio_final = precio
                
            lista_productos.append({
                "Tienda/Sección": seccion,
                "Producto": nombre_producto,
                "Precio S/.": float(precio_final) if isinstance(precio_final, (int, float)) else precio_final
            })
        
        df = pd.DataFrame(lista_productos)
        c1, c2 = st.columns(2)
        c1.metric("📦 Productos bajo la lupa", len(df))
        c2.metric("🏪 Tiendas activas", df["Tienda/Sección"].nunique())
        st.dataframe(df, use_container_width=True)

# ====== VISTA 2: GRÁFICOS DE TENDENCIA ======
elif menu == "📊 Gráficos de Tendencia":
    st.subheader("📉 Análisis de Historial de Precios")
    datos = cargar_historial()
    
    if not datos:
        st.info("⌛ No hay datos históricos suficientes.")
    else:
        producto_seleccionado = st.selectbox("🔍 Selecciona el producto a analizar:", list(datos.keys()))
        if producto_seleccionado:
            registro_precio = datos[producto_seleccionado]
            if isinstance(registro_precio, dict):
                df_tiempo = pd.DataFrame(list(registro_precio.items()), columns=["Fecha", "Precio (S/.)"]).sort_values(by="Fecha")
                precios_numericos = pd.to_numeric(df_tiempo["Precio (S/.)"], errors='coerce')
                precio_min, precio_max, precio_actual = precios_numericos.min(), precios_numericos.max(), precios_numericos.iloc[-1]
                
                c1, c2, c3 = st.columns(3)
                c1.metric("💰 Precio Actual", f"S/. {precio_actual}")
                c2.metric("🟢 El más bajo", f"S/. {precio_min}")
                c3.metric("🔴 El más alto", f"S/. {precio_max}")
                
                if precio_actual <= precio_min and precio_min != precio_max:
                    st.success("🔥 ¡Ganga confirmada! Punto histórico más bajo.")
                elif precio_actual >= precio_max and precio_min != precio_max:
                    st.error("⚠️ Alerta: El precio está inflado.")
                else:
                    st.info("⚖️ Precio estable dentro del promedio.")
                st.line_chart(df_tiempo.set_index("Fecha")["Precio (S/.)"])

# ====== VISTA 3: GESTIÓN DE ENLACES ======
elif menu == "🛠️ Gestionar Enlaces (Anti-Caídas)":
    st.subheader("🔗 Administrador Remoto de URLs")
    lineas_actuales = cargar_urls()
    
    with st.form("form_url"):
        st.markdown("### ➕ Registrar / Actualizar Enlace")
        nueva_url = st.text_input("Pegar URL de la tienda:")
        nuevo_limite = st.number_input("Presupuesto Máximo (S/.)", min_value=1, value=200)
        nuevo_nombre = st.text_input("Nombre de la sección (Ej: Adidas_Zapatillas_Hombre):")
        boton_guardar = st.form_submit_button("Guardar en el Sistema")
        
        if boton_guardar and nueva_url and nuevo_nombre:
            nombre_limpio = nuevo_nombre.replace(" ", "_")
            nueva_linea = f"{nueva_url},{nuevo_limite},{nombre_limpio}"
            lineas_filtradas = [l for l in lineas_actuales if not l.endswith(nombre_limpio)]
            lineas_filtradas.append(nueva_linea)
            guardar_urls(lineas_filtradas)
            st.success(f"✅ ¡Enlace de '{nombre_limpio}' guardado!")
            st.rerun()

    st.markdown("### 📋 Enlaces actualmente activos")
    for i, linea in enumerate(lineas_actuales):
        partes = linea.split(",")
        if len(partes) == 3:
            col_info, col_btn = st.columns([8, 2])
            col_info.code(f"📍 {partes[2]} | Máx: S/. {partes[1]}\n🔗 {partes[0][:60]}...")
            if col_btn.button("🗑️ Borrar", key=f"del_{i}"):
                lineas_actuales.pop(i)
                guardar_urls(lineas_actuales)
                st.rerun()

# ====== VISTA 4: CONTROL DE COMANDOS DEL BOT (¡LO NUEVO!) ======
elif menu == "🤖 Servidor del Bot Telegram":
    st.subheader("🧠 Centro de Respuesta del Bot Interactiva")
    st.write("Esta sección procesa las peticiones que le haces a tu bot por chat.")
    
    # Botón técnico para jalar mensajes pendientes de Telegram (Polling manual simulado de bajo consumo)
    if st.button("🔄 Sincronizar y Responder mensajes de Telegram", type="primary"):
        url_get_updates = f"https://api.telegram.org/bot{TOKEN_REAL}/getUpdates"
        try:
            res = requests.get(url_get_updates, timeout=10).json()
            if res.get("ok") and res.get("result"):
                ultimos_mensajes = res["result"]
                st.success(f"📥 Se encontraron {len(ultimos_mensajes)} interacciones recientes.")
                
                # Procesamos el último mensaje recibido para evitar spam
                ultimo_update = ultimos_mensajes[-1]
                msg = ultimo_update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                texto_recibido = msg.get("text", "").strip().lower()
                
                if chat_id == ID_REAL:
                    if texto_recibido in ["/start", "/ayuda", "hola"]:
                        menu_bot = (
                            "🕵️‍♂️ *¡Hola! Soy Coby Radar Familiar* 🤖\n\n"
                            "Estoy a tus órdenes. Puedes usar estos comandos desde el chat:\n"
                            "🔹 `/resumen` : Te envío la lista de precios actuales en un segundo.\n"
                            "🔹 `/ayuda` : Muestra este menú informativo."
                        )
                        enviar_respuesta_telegram(menu_bot)
                        st.info("✅ Menú de ayuda enviado a tu chat.")
                        
                    elif texto_recibido == "/resumen":
                        datos = cargar_historial()
                        if not datos:
                            enviar_respuesta_telegram("📭 El historial está vacío por ahora.")
                        else:
                            reporte = "📋 *Resumen Actual del Radar Coby:* \n\n"
                            for item, precio in datos.items():
                                nombre_limpio = item.replace("_", " ")
                                if isinstance(precio, dict):
                                    u_f = sorted(precio.keys())[-1]
                                    p_f = precio[u_f]
                                else:
                                    p_f = precio
                                reporte += f"📦 *{nombre_limpio}*\n💰 Precio: S/. {p_f}\n\n"
                            
                            enviar_respuesta_telegram(reporte)
                            st.info("✅ Reporte de resumen enviado a tu Telegram.")
                    else:
                        st.warning(f"Comando desconocido: {texto_recibido}")
                else:
                    st.error("⚠️ Intento de acceso de un Chat ID no autorizado.")
            else:
                st.info("☕ No hay comandos nuevos pendientes en el chat de Telegram.")
        except Exception as e:
            st.error(f"Error procesando el bot: {e}")
