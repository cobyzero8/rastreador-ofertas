import streamlit as st
import json
import os
import pandas as pd
from scraper import revisar_ofertas # Importamos directo

st.set_page_config(page_title="CobyZero8 - Radar Pro", layout="wide")

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

# --- SIDEBAR: CONTROL MAESTRO ---
with st.sidebar:
    st.title("⚙️ Control Maestro")
    if st.button("💥 FORZAR ESCANEO", use_container_width=True):
        with st.spinner("🚀 Ejecutando rastreo..."):
            try:
                revisar_ofertas()
                st.success("✅ Escaneo terminado con éxito.")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Falló el escaneo: {e}")
    
    st.write("---")
    menu = st.radio("Navegación", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces"])

# --- LÓGICA DE DICCIONARIO ---
def obtener_datos_configurados():
    datos = {}
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r") as f:
            for line in f.readlines():
                parts = line.strip().split(",")
                if len(parts) >= 3:
                    # ID es Tienda_Nombre_Talla
                    datos[parts[2]] = {"url": parts[0]}
    return datos

# --- PANTALLA: DASHBOARD ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Radar Familiar Pro")
    st.subheader("📊 Dashboard: Artículos bajo vigilancia")
    
    config = obtener_datos_configurados()
    
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                lista = []
                for id_prod, hist in data.items():
                    parts = id_prod.split("_")
                    # Buscamos la URL original que registraste
                    link_info = config.get(id_prod, {"url": "#"})
                    
                    lista.append({
                        "Tienda": parts[0],
                        "Producto": parts[1].replace("-", " "),
                        "Talla": parts[2] if len(parts) > 2 else "N/A",
                        "Precio": f"S/. {list(hist.values())[-1]}",
                        "Link": link_info["url"]
                    })
                
                df = pd.DataFrame(lista)
                if not df.empty:
                    st.data_editor(
                        df,
                        column_config={"Link": st.column_config.LinkColumn("Compra Directa")},
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("Presiona 'FORZAR ESCANEO' para obtener datos.")
            except:
                st.error("Error al procesar el archivo de historial.")
    else:
        st.info("No hay datos históricos. Agrega productos y presiona 'FORZAR ESCANEO'.")

# --- PANTALLA: GESTIÓN ---
elif menu == "🛠️ Gestionar Enlaces":
    st.title("🛠️ Gestionar Enlaces Pro")
    with st.container(border=True):
        c1, c2 = st.columns(2)
        tienda = c1.selectbox("Tienda", ["Adidas", "Falabella", "Marathon", "Ripley"])
        url = c2.text_input("URL del producto")
        c3, c4 = st.columns(2)
        nombre = c3.text_input("Nombre (Sin espacios)")
        talla = c4.text_input("Talla")
        
        if st.button("💾 GUARDAR", type="primary"):
            linea = f"{url},100,{tienda}_{nombre.replace(' ', '-')}_{talla}\n"
            with open(URLS_FILE, "a") as f:
                f.write(linea)
            st.success("✅ Guardado correctamente.")
            st.rerun()
