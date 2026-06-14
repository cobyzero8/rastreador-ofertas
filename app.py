import streamlit as st
import json
import os
import pandas as pd

st.set_page_config(page_title="CobyZero8 - Radar Pro", layout="wide")

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

# --- SIDEBAR: BOTÓN DE ACCIÓN RÁPIDA ---
with st.sidebar:
    st.title("⚙️ Control Maestro")
    if st.button("💥 FORZAR ESCANEO MANUAL", use_container_width=True):
        st.warning("Ejecutando proceso...")
        os.system("python scraper.py")
        st.success("Escaneo finalizado.")

# --- SECCIÓN SUPERIOR: AGREGAR ARTÍCULOS ---
st.subheader("➕ Agregar Nuevo Artículo al Radar")
with st.container(border=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        tienda = st.selectbox("Tienda", ["Adidas", "Falabella", "Marathon", "Ripley", "Puma", "Nike"])
        url = st.text_input("URL del producto")
    with col2:
        nombre = st.text_input("Nombre del artículo")
        precio = st.number_input("Precio máximo (Tope S/.)", value=100)
    with col3:
        talla = st.text_input("Talla (Ej: 9.5US, M)")
        if st.button("💾 GUARDAR Y AGREGAR", type="primary", use_container_width=True):
            nueva_linea = f"{url},{precio},{tienda}_{nombre.replace(' ', '-')}_{talla}"
            
            # Cargar y guardar al inicio (primera fila)
            if os.path.exists(URLS_FILE):
                with open(URLS_FILE, "r", encoding="utf-8") as f:
                    lineas = f.readlines()
            else:
                lineas = []
            
            lineas.insert(0, nueva_linea + "\n")
            with open(URLS_FILE, "w", encoding="utf-8") as f:
                f.writelines(lineas)
            
            st.toast("✅ Artículo agregado correctamente a la primera fila.")

st.write("---")

# --- SECCIÓN DASHBOARD ---
st.subheader("📊 Artículos bajo vigilancia")
if os.path.exists(HISTORIAL_FILE):
    with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        lista = []
        for id_prod, hist in data.items():
            parts = id_prod.split("_")
            lista.append({
                "Tienda": parts[0],
                "Producto": parts[1].replace("-", " "),
                "Talla": parts[2],
                "Precio Actual": f"S/. {list(hist.values())[-1]}"
            })
    st.table(pd.DataFrame(lista))
else:
    st.info("Aún no hay artículos rastreados.")
