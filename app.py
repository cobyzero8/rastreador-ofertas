import streamlit as st
import json
import os
import pandas as pd

st.set_page_config(
    page_title="CobyZero8 - Radar Familiar",
    page_icon="🕵️‍♂️",
    layout="wide"
)

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

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

st.title("🕵️‍♂️ CobyZero8 - Radar Familiar & Comparador")
st.markdown("---")

menu = st.sidebar.selectbox("Navegación", [
    "📈 Ver Dashboard", 
    "📊 Comparador Inter-Tiendas", 
    "🛠️ Gestionar Enlaces (Anti-Caídas)"
])

if menu == "📈 Ver Dashboard":
    st.subheader("📊 Monitoreo en Tiempo Real")
    datos = cargar_historial()
    
    if not datos:
        st.info("⌛ Base de datos inicializada. Esperando datos del robot.")
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

elif menu == "📊 Comparador Inter-Tiendas":
    st.subheader("⚔️ Comparativa de Tendencias de Mercado")
    datos = cargar_historial()
    
    if not datos:
        st.info("⌛ No hay datos históricos suficientes.")
    else:
        productos_unicos = set()
        for clave in datos.keys():
            nombre_p = clave.split("_", 1)[1] if "_" in clave else clave
            productos_unicos.add(nombre_p)
            
        producto_buscado = st.selectbox("🔍 Selecciona un producto:", sorted(list(productos_unicos)))
        
        if producto_buscado:
            df_comparativo = pd.DataFrame()
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
                st.line_chart(df_comparativo)
                st.dataframe(df_comparativo, use_container_width=True)

elif menu == "🛠️ Gestionar Enlaces (Anti-Caídas)":
    st.subheader("🔗 Administrador Remoto de URLs")
    lineas_actuales = cargar_urls()
    
    with st.form("form_url"):
        st.markdown("### ➕ Registrar Enlace Familiar Seguro")
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
