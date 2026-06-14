import streamlit as st
import json
import os
import pandas as pd

st.set_page_config(page_title="Radar Pro - Panel Central", layout="wide")

URLS_FILE = "urls.txt"
HISTORIAL_FILE = "historial_precios.json"

# --- SIDEBAR: CONTROL MAESTRO ---
with st.sidebar:
    st.header("⚙️ Control Maestro")
    
    # FORZAR ESCANEO (Sin importar archivos, solo un trigger)
    if st.button("🚀 FORZAR ESCANEO", use_container_width=True):
        with st.spinner("Ejecutando proceso de fondo..."):
            # Escribimos un archivo 'trigger' que tu script de robot debe detectar
            with open("trigger_scan.txt", "w") as f:
                f.write("run")
            st.success("✅ ¡Orden enviada!")
            st.rerun()

    st.write("---")
    menu = st.radio("Navegación", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces"])

# --- DASHBOARD ---
if menu == "📈 Ver Dashboard":
    st.title("📈 Dashboard de Ofertas")
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r") as f:
            data = json.load(f)
            
            # Cargar links para el cruce de datos
            links = {}
            if os.path.exists(URLS_FILE):
                with open(URLS_FILE, "r") as f:
                    for l in f.readlines():
                        p = l.strip().split(",")
                        if len(p) >= 3: links[p[2]] = p[0]
            
            rows = []
            for id_prod, hist in data.items():
                p = id_prod.split("_")
                rows.append({
                    "Tienda": p[0], 
                    "Producto": p[1].replace("-", " "), 
                    "Precio": f"S/. {list(hist.values())[-1]}", 
                    "Link": links.get(id_prod, "#")
                })
            
            if rows:
                st.data_editor(pd.DataFrame(rows), column_config={"Link": st.column_config.LinkColumn()}, use_container_width=True)
            else:
                st.info("Aún no hay datos.")
    else:
        st.info("El robot aún no ha generado datos. Presiona 'FORZAR ESCANEO'.")

# --- GESTIÓN ---
elif menu == "🛠️ Gestionar Enlaces":
    st.title("🛠️ Gestionar Enlaces")
    with st.form("nuevo_link"):
        c1, c2 = st.columns(2)
        tienda = c1.selectbox("Tienda", ["Adidas", "Falabella", "Marathon", "Ripley"])
        url = c2.text_input("URL exacta")
        nombre = st.text_input("Nombre (Sin espacios)")
        talla = st.text_input("Talla")
        
        if st.form_submit_button("💾 GUARDAR"):
            with open(URLS_FILE, "a") as f:
                f.write(f"{url},100,{tienda}_{nombre}_{talla}\n")
            st.success("¡Guardado!")
            st.rerun()

    st.subheader("📋 Enlaces actuales")
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r") as f:
            st.code(f.read())
