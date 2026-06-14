import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime
import requests

st.set_page_config(
    page_title="CobyZero8 - Radar Familiar",
    page_icon="🕵️‍♂️",
    layout="wide"
)

# ===== CREDENCIALES DEL SISTEMA =====
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
st.title("🕵️‍♂️ CobyZero8 - Radar Familiar & Comparador")
st.markdown("---")

menu = st.sidebar.selectbox("Navegación", [
    "📈 Ver Dashboard", 
    "📊 Comparador Inter-Tiendas", 
    "🛠️ Gestionar Enlaces (Anti-Caídas)",
    "🤖 Servidor del Bot Telegram"
])

# ====== VISTA 1: EL DASHBOARD ======
if menu == "📈 Ver Dashboard":
    st.subheader("📊 Monitoreo en Tiempo Real")
    datos = cargar_historial()
    
    if not datos:
        st.info("⌛ Base de datos inicializada. Esperando que el robot cargue los primeros productos filtrados.")
    else:
        lista_productos = []
        for clave, precio in datos.items():
            seccion, nombre_producto = clave.split("_", 1) if "_" in clave else ("General", clave)
            
            if isinstance(precio, dict):
                fechas_ordenadas = sorted(precio.keys())
                precio_final = precio[fechas_ordenadas[-1]] if fechas_ordenadas else 0
            else:
                precio_final = precio
                
            lista_productos.append({
                "Sección/Filtro": seccion,
                "Producto": nombre_producto,
                "Precio S/.": float(precio_final) if isinstance(precio_final, (int, float)) else precio_final
            })
        
        df = pd.DataFrame(lista_productos)
        c1, col2 = st.columns(2)
        c1.metric("📦 Productos bajo la lupa", len(df))
        col2.metric("🏪 Categorías activas", df["Sección/Filtro"].nunique())
        st.dataframe(df, use_container_width=True)

# ====== VISTA 2: COMPARADOR INTER-TIENDAS (¡NUEVO!) ======
elif menu == "📊 Comparador Inter-Tiendas":
    st.subheader("⚔️ Comparativa de Tendencias de Mercado")
    st.write("Visualiza y compara las variaciones de precios entre diferentes cadenas y secciones.")
    
    datos = cargar_historial()
    
    if not datos:
        st.info("⌛ Agrega enlaces y ejecuta el robot para poblar las gráficas comparativas.")
    else:
        # Extraemos nombres de productos únicos simplificados para cruzar datos
        productos_unicos = set()
        for clave in datos.keys():
            nombre_p = clave.split("_", 1)[1] if "_" in clave else clave
            productos_unicos.add(nombre_p)
            
        producto_buscado = st.selectbox("🔍 Selecciona un producto para cruzar precios inter-tienda:", sorted(list(productos_unicos)))
        
        if producto_buscado:
            df_comparativo = pd.DataFrame()
            
            # Buscamos coincidencias de ese producto en Falabella, Ripley o Adidas
            for clave, registro_precio in datos.items():
                if producto_buscado in clave and isinstance(registro_precio, dict):
                    tienda = clave.split("_", 1)[0] if "_" in clave else "General"
                    
                    df_tienda = pd.DataFrame(list(registro_precio.items()), columns=["Fecha", tienda])
                    df_tienda[tienda] = pd.to_numeric(df_tienda[tienda], errors='coerce')
                    
                    if df_comparativo.empty:
                        df_comparativo = df_tienda
                    else:
                        df_comparativo = pd.merge(df_comparativo, df_tienda, on="Fecha", how="outer")
            
            if not df_comparativo.empty:
                df_comparativo = df_comparativo.sort_values(by="Fecha").set_index("Fecha")
                st.markdown(f"### 📈 Curva comparativa para: *{producto_buscado}*")
                st.line_chart(df_comparativo)
                st.dataframe(df_comparativo, use_container_width=True)
            else:
                st.warning("No hay suficientes puntos de precio históricos para cruzar este producto.")

# ====== VISTA 3: GESTIÓN DE ENLACES ======
elif menu == "🛠️ Gestionar Enlaces (Anti-Caídas)":
    st.subheader("🔗 Administrador Remoto de URLs")
    lineas_actuales = cargar_urls()
    
    with st.form("form_url"):
        st.markdown("### ➕ Registrar Enlace Familiar Seguro")
        st.write("*Recuerda incluir 'Hombre', 'Mujer' o 'Niños' en el nombre para activar los filtros automáticos.*")
        nueva_url = st.text_input("Pegar URL de la tienda:")
        nuevo_limite = st.number_input("Presupuesto Máximo (S/.)", min_value=1, value=250)
        nuevo_nombre = st.text_input("Nombre de la sección (Ej: Adidas_Zapatillas_Hombre):")
        boton_guardar = st.form_submit_button("Guardar en el Radar")
        
        if boton_guardar and nueva_url and nuevo_nombre:
            nombre_limpio = nuevo_nombre.replace(" ", "_")
            nueva_linea = f"{nueva_url},{nuevo_limite},{nombre_limpio}"
            lineas_filtradas = [l for l in lineas_actuales if not l.endswith(nombre_limpio)]
            lineas_filtradas.append(nueva_linea)
            guardar_urls(lineas_filtradas)
            st.success(f"✅ ¡Enlace '{nombre_limpio}' indexado!")
            st.rerun()

    st.markdown("### 📋 Radares en Cola de Escaneo")
    for i, linea in enumerate(lineas_actuales):
        partes = linea.split(",")
        if len(partes) == 3:
            col_info, col_btn = st.columns([8, 2])
            col_info.code(f"📍 {partes[2]} | Alerta si baja de: S/. {partes[1]}\n🔗 {partes[0][:60]}...")
            if col_btn.button("🗑️ Borrar", key=f"del_{i}"):
                lineas_actuales.pop(i)
                guardar_urls(lineas_actuales)
                st.rerun()

# ====== VISTA 4: CONTROL DE COMANDOS DEL BOT ======
elif menu == "🤖 Servidor del Bot Telegram":
    st.subheader("🧠 Centro de Respuesta del Bot Interactiva")
    
    if st.button("🔄 Sincronizar y Responder mensajes de Telegram", type="primary"):
        url_get_updates = f"https://api.telegram.org/bot{TOKEN_REAL}/getUpdates"
        try:
            res = requests.get(url_get_updates, timeout=10).json()
            if res.get("ok") and res.get("result"):
                ultimos_mensajes = res["result"]
                st.success(f"📥 {len(ultimos_mensajes)} paquetes de datos sincronizados.")
                
                ultimo_update = ultimos_mensajes[-1]
                msg = ultimo_update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                texto_recibido = msg.get("text", "").strip().lower()
                
                if chat_id == ID_REAL:
                    if texto_recibido in ["/start", "/ayuda", "hola"]:
                        menu_bot = (
                            "🕵️‍♂️ *¡Hola! Soy Coby Radar Familiar* 🤖\n\n"
                            "Estoy listo para vigilar los precios de la familia. Comandos disponibles:\n"
                            "🔹 `/resumen` : Lista de ofertas validadas en stock.\n"
                            "🔹 `/ayuda` : Muestra este menú."
                        )
                        enviar_respuesta_telegram(menu_bot)
                        
                    elif texto_recibido == "/resumen":
                        datos = cargar_historial()
                        urls_activas = cargar_urls()
                        
                        if not datos:
                            # PARCHE INTELIGENTE: Si el JSON está vacío, le muestra las tiendas que está vigilando
                            reporte = "📭 *Historial de ofertas vacío por hoy.*\n\n"
                            reporte += "📍 *Radares activos esperando rebajas:*\n"
                            for u in urls_activas:
                                p = u.split(",")
                                if len(p) == 3:
                                    reporte += f"🔸 `{p[2]}` (Máx: S/. {p[1]})\n"
                            reporte += "\n💡 _Ejecuta el rastreador en GitHub para buscar nuevas rebajas con tus tallas familiares._"
                            enviar_respuesta_telegram(reporte)
                        else:
                            reporte = "📋 *Resumen de Precios en el Radar:* \n\n"
                            for item, precio in datos.items():
                                nombre_limpio = item.replace("_", " ")
                                p_f = precio[sorted(precio.keys())[-1]] if isinstance(precio, dict) else precio
                                reporte += f"📦 *{nombre_limpio}*\n💰 Precio: S/. {p_f}\n\n"
                            enviar_respuesta_telegram(reporte)
                        st.info("✅ Respuesta enviada con éxito a Telegram.")
                else:
                    st.error("⚠️ Chat ID no autorizado.")
            else:
                st.info("☕ No hay peticiones nuevas en cola.")
        except Exception as e:
            st.error(f"Error en servidor del bot: {e}")
