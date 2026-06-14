import streamlit as st
import json
import os
import pandas as pd
from scraper import revisar_ofertas

st.set_page_config(page_title="CobyZero8 - Radar Pro", layout="wide")

URLS_FILE = "urls.txt"
HISTORIAL_FILE = "historial_precios.json"

with st.sidebar:
    st.title("⚙️ Control Maestro")
    if st.button("💥 FORZAR ESCANEO", use_container_width=True):
        status = st.empty()
        with st.spinner("🚀 Ejecutando rastreo..."):
            try:
                revisar_ofertas()
                status.success("✅ Escaneo completado.")
                st.rerun()
            except Exception as e:
                status.error(f"❌ Error: {str(e)}")
    
    menu = st.radio("Navegación", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces"])

# --- DASHBOARD BLINDADO ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Radar Familiar Pro")
    
    # 1. Leer URLs de forma segura
    link_map = {}
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r") as f:
            for line in f.readlines():
                p = line.strip().split(",")
                # Validamos que la línea tenga al menos 3 partes
                if len(p) >= 3:
                    link_map[p[2]] = p[0]

    # 2. Leer historial de forma segura
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r") as f:
            try:
                data = json.load(f)
                rows = []
                for id_prod, hist in data.items():
                    parts = id_prod.split("_")
                    # Acceso seguro a partes de la lista
                    tienda = parts[0] if len(parts) > 0 else "N/A"
                    nombre = parts[1].replace("-", " ") if len(parts) > 1 else "N/A"
                    
                    rows.append({
                        "Tienda": tienda,
                        "Producto": nombre,
                        "Precio": f"S/. {list(hist.values())[-1]}",
                        "Link": link_map.get(id_prod, "#")
                    })
                
                if rows:
                    st.data_editor(pd.DataFrame(rows), column_config={"Link": st.column_config.LinkColumn()}, hide_index=True, use_container_width=True)
                else:
                    st.warning("No hay datos procesados aún.")
            except:
                st.error("Archivo de historial dañado.")

# --- GESTIÓN ---
else:
    st.title("🛠️ Gestionar Enlaces")
    with st.container(border=True):
        c1, c2 = st.columns(2)
        tienda = c1.selectbox("Tienda", ["Adidas", "Falabella", "Marathon", "Ripley"])
        url = c2.text_input("URL exacta")
        nombre = st.text_input("Nombre (Sin espacios)")
        talla = st.text_input("Talla")
        
        if st.button("💾 GUARDAR"):
            if nombre and url:
                with open(URLS_FILE, "a") as f:
                    f.write(f"{url},100,{tienda}_{nombre}_{talla}\n")
                st.toast("✅ Guardado.")
                st.rerun()
