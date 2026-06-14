import streamlit as st
import json
import os
import pandas as pd
from datetime import datetime

st.set_page_config(
    page_title="CobyZero8 - Radar App",
    page_icon="🕵️‍♂️",
    layout="wide"
)

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

# --- DISEÑO DE LA INTERFAZ ---
st.title("🕵️‍♂️ CobyZero8 - Radar & Panel de Control")
st.markdown("---")

# Menú lateral para navegar en la App
menu = st.sidebar.selectbox("Navegación", ["📈 Ver Dashboard", "📊 Gráficos de Tendencia", "🛠️ Gestionar Enlaces (Anti-Caídas)"])

# ====== VISTA 1: EL DASHBOARD ======
if menu == "📈 Ver Dashboard":
    st.subheader("📊 Monitoreo en Tiempo Real")
    datos = cargar_historial()
    
    if not datos:
        st.info("⌛ Esperando la primera carrera del robot para mostrar el catálogo.")
    else:
        lista_productos = []
        for clave, precio in datos.items():
            if "_" in clave:
                seccion, nombre_producto = clave.split("_", 1)
            else:
                seccion, nombre_producto = "General", clave
            
            # Si el historial guarda un diccionario con fechas, tomamos el último precio conocido
            if isinstance(precio, dict):
                ultimo_par de_fechas = sorted(precio.keys())[-1]
                precio_final = precio[ultimo_par_de_fechas]
            else:
                precio_final = precio
                
            lista_productos.append({
                "Tienda/Sección": seccion,
                "Producto": nombre_producto,
                "Precio S/.": float(precio_final) if isinstance(precio_final, (int, float)) else precio_final
            })
        
        df = pd.DataFrame(lista_productos)
        
        col1, col2 = st.columns(2)
        col1.metric("📦 Productos bajo la lupa", len(df))
        col2.metric("🏪 Tiendas activas", df["Tienda/Sección"].nunique())
        
        st.dataframe(df, use_container_width=True)

# ====== VISTA 2: GRÁFICOS DE TENDENCIA (¡LO NUEVO!) ======
elif menu == "📊 Gráficos de Tendencia":
    st.subheader("📉 Análisis de Historial de Precios")
    st.write("Selecciona un producto para verificar si su precio actual es una verdadera oferta o si está inflado.")
    
    datos = cargar_historial()
    
    if not datos:
        st.info("⌛ No hay datos históricos suficientes para dibujar tendencias.")
    else:
        # Extraer lista limpia de productos disponibles para el selector
        opciones_productos = list(datos.keys())
        producto_seleccionado = st.selectbox("🔍 Selecciona el producto a analizar:", opciones_productos)
        
        if producto_seleccionado:
            registro_precio = datos[producto_seleccionado]
            
            # Verificamos si los datos tienen estructura de fechas (Evolución Temporal)
            if isinstance(registro_precio, dict):
                # Creamos la tabla de tiempos
                df_tiempo = pd.DataFrame(list(registro_precio.items()), columns=["Fecha", "Precio (S/.)"])
                df_tiempo = df_tiempo.sort_values(by="Fecha")
                
                # Renderizar métricas clave de análisis
                precios_numericos = pd.to_numeric(df_tiempo["Precio (S/.)"], errors='coerce')
                precio_min = precios_numericos.min()
                precio_max = precios_numericos.max()
                precio_actual = precios_numericos.iloc[-1]
                
                c1, c2, c3 = st.columns(3)
                c1.metric("💰 Precio Actual", f"S/. {precio_actual}")
                c2.metric("🟢 El más bajo registrado", f"S/. {precio_min}")
                c3.metric("🔴 El más alto registrado", f"S/. {precio_max}")
                
                # Validar de forma inteligente el estado de la oferta
                if precio_actual <= precio_min and precio_min != precio_max:
                    st.success("🔥 ¡Ganga confirmada! Este producto está en su punto histórico más bajo.")
                elif precio_actual >= precio_max and precio_min != precio_max:
                    st.error("⚠️ Alerta: El precio está inflado. Te sugerimos esperar a que baje.")
                else:
                    st.info("⚖️ Precio estable: Se mantiene dentro del promedio habitual de mercado.")
                
                # Dibujar gráfico de líneas interactivo
                st.markdown("#### 📈 Evolución del precio en el tiempo")
                st.line_chart(df_tiempo.set_index("Fecha")["Precio (S/.)"])
            else:
                # Si el JSON solo tiene un precio plano (primer registro), creamos una simulación base inicial
                fecha_hoy = datetime.now().strftime("%Y-%m-%d")
                st.warning("📊 El robot acaba de registrar este producto por primera vez. La línea de tendencia se irá dibujando automáticamente de forma diaria en las siguientes ejecuciones.")
                
                c1, c2 = st.columns(2)
                c1.metric("💰 Precio Inicial", f"S/. {registro_precio}")
                c2.metric("📅 Registrado el", fecha_hoy)

# ====== VISTA 3: GESTIÓN DE ENLACES ======
elif menu == "🛠️ Gestionar Enlaces (Anti-Caídas)":
    st.subheader("🔗 Administrador Remoto de URLs")
    st.write("Si una página cambia de dirección o se actualiza, edítala o cámbiala aquí desde tu celular.")
    
    lineas_actuales = cargar_urls()
    
    with st.form("form_url"):
        st.markdown("### ➕ Registrar / Actualizar Enlace")
        nueva_url = st.text_input("Pegar URL de la tienda:")
        nuevo_limite = st.number_input("Presupuesto Máximo (S/.)", min_value=1, value=200)
        nuevo_nombre = st.text_input("Nombre de la sección (Ej: Adidas_Zapatillas_Outlet):")
        
        boton_guardar = st.form_submit_button("Guardar en el Sistema")
        
        if boton_guardar and nueva_url and nuevo_nombre:
            nombre_limpio = nuevo_nombre.replace(" ", "_")
            nueva_linea = f"{nueva_url},{nuevo_limite},{nombre_limpio}"
            
            lineas_filtradas = [l for l in lineas_actuales if not l.endswith(nombre_limpio)]
            lineas_filtradas.append(nueva_linea)
            
            guardar_urls(lineas_filtradas)
            st.success(f"✅ ¡Enlace de '{nombre_limpio}' guardado con éxito!")
            st.rerun()

    st.markdown("### 📋 Enlaces actualmente activos en tu Robot")
    for i, linea in enumerate(lineas_actuales):
        partes = linea.split(",")
        if len(partes) == 3:
            col_info, col_btn = st.columns([8, 2])
            col_info.code(f"📍 {partes[2]} | Máx: S/. {partes[1]}\n🔗 {partes[0][:60]}...")
            if col_btn.button("🗑️ Borrar", key=f"del_{i}"):
                lineas_actuales.pop(i)
                guardar_urls(lineas_actuales)
                st.warning("Enlace eliminado.")
                st.rerun()
