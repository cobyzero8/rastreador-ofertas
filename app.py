import streamlit as st
import json
import os
import pandas as pd

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
menu = st.sidebar.selectbox("Navegación", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces (Anti-Caídas)"])

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
            
            lista_productos.append({
                "Tienda/Sección": seccion,
                "Producto": nombre_producto,
                "Precio S/.": float(precio) if isinstance(precio, (int, float)) else precio
            })
        
        df = pd.DataFrame(lista_productos)
        
        col1, col2 = st.columns(2)
        col1.metric("📦 Productos bajo la lupa", len(df))
        col2.metric("🏪 Tiendas activas", df["Tienda/Sección"].nunique())
        
        st.dataframe(df, use_container_width=True)

# ====== VISTA 2: GESTIÓN DE ENLACES ======
elif menu == "🛠️ Gestionar Enlaces (Anti-Caídas)":
    st.subheader("🔗 Administrador Remoto de URLs")
    st.write("Si una página cambia de dirección o se actualiza, edítala o cámbiala aquí desde tu celular.")
    
    lineas_actuales = cargar_urls()
    
    # Formulario para AGREGAR o REEMPLAZAR un enlace
    with st.form("form_url"):
        st.markdown("### ➕ Registrar / Actualizar Enlace")
        nueva_url = st.text_input("Pegar URL de la tienda:")
        nuevo_limite = st.number_input("Presupuesto Máximo (S/.)", min_value=1, value=200)
        nuevo_nombre = st.text_input("Nombre de la sección (Ej: Adidas_Zapatillas_Outlet):")
        
        boton_guardar = st.form_submit_button("Guardar en el Sistema")
        
        if boton_guardar and nueva_url and nuevo_nombre:
            # Reemplazar espacios por guiones bajos para no romper el historial
            nombre_limpio = nuevo_nombre.replace(" ", "_")
            nueva_linea = f"{nueva_url},{nuevo_limite},{nombre_limpio}"
            
            # Filtramos si ya existía una sección con ese nombre para actualizarla
            lineas_filtradas = [l for l in lineas_actuales if not l.endswith(nombre_limpio)]
            lineas_filtradas.append(nueva_linea)
            
            guardar_urls(lineas_filtradas)
            st.success(f"✅ ¡Enlace de '{nombre_limpio}' guardado con éxito! El robot lo leerá en su próxima vuelta.")
            st.rerun()

    # Mostrar lista actual con opción de borrar enlaces caídos
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
