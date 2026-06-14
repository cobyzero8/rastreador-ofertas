import streamlit as st
import json
import os
import pandas as pd

st.set_page_config(page_title="CobyZero8 - Radar Pro", layout="wide")

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

# --- SIDEBAR: CONTROL MAESTRO ---
with st.sidebar:
    st.title("⚙️ Control Maestro")
    if st.button("💥 FORZAR ESCANEO", use_container_width=True):
        st.warning("Ejecutando escaneo...")
        os.system("python scraper.py")
        st.success("Escaneo terminado.")
    st.write("---")
    st.subheader("🔗 Enlaces registrados")
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r") as f:
            for line in f.readlines():
                st.caption(line[:30] + "...")

# --- SECCIÓN SUPERIOR: FORMULARIO DE ALTA ---
st.title("🕵️‍♂️ Radar Familiar Pro")
st.subheader("➕ Agregar Nuevo Artículo")
with st.container(border=True):
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        tienda = st.selectbox("Tienda", ["Adidas", "Falabella", "Marathon", "Ripley", "Puma", "Nike"])
        talla = st.text_input("Talla (Ej: 9.5US)")
    with c2:
        nombre = st.text_input("Nombre del artículo")
        precio = st.number_input("Precio máximo (Tope S/.)", value=100)
    with c3:
        url = st.text_input("URL del producto")
    with c4:
        st.write("###") # Espaciador
        if st.button("💾 GUARDAR Y AGREGAR", type="primary", use_container_width=True):
            nueva_linea = f"{url},{precio},{tienda}_{nombre.replace(' ', '-')}_{talla}"
            if os.path.exists(URLS_FILE):
                with open(URLS_FILE, "r") as f:
                    lineas = f.readlines()
            else:
                lineas = []
            lineas.insert(0, nueva_linea + "\n")
            with open(URLS_FILE, "w") as f:
                f.writelines(lineas)
            st.toast("✅ Artículo agregado a la lista!")

# --- SECCIÓN DASHBOARD ---
st.write("---")
st.subheader("📊 Dashboard: Artículos bajo vigilancia")
if os.path.exists(HISTORIAL_FILE):
    with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            lista = []
            for id_prod, hist in data.items():
                parts = id_prod.split("_")
                lista.append({
                    "Tienda": parts[0],
                    "Producto": parts[1].replace("-", " "),
                    "Talla": parts[2] if len(parts) > 2 else "N/A",
                    "Precio Actual": f"S/. {list(hist.values())[-1]}"
                })
            df = pd.DataFrame(lista)
            st.table(df)
        except:
            st.error("Error al leer el historial, el archivo podría estar vacío.")
else:
    st.info("No hay artículos en el historial. Agrega uno arriba y fuerza un escaneo.")
