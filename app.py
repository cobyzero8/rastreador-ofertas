import streamlit as st
import json
import os
import pandas as pd

st.set_page_config(page_title="CobyZero8 - Radar Pro", layout="wide")

URLS_FILE = "urls.txt"
HISTORIAL_FILE = "historial_precios.json"

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Control Maestro")
    st.info("Para forzar el escaneo, usa el botón de abajo.")
    if st.button("💥 FORZAR ESCANEO"):
        # Escribimos un flag para que el bot de GitHub lo detecte
        with open("trigger_scan.txt", "w") as f:
            f.write("run")
        st.success("✅ Trigger enviado. El robot en GitHub se activará en breve.")

    menu = st.radio("Navegación", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces"])

# --- DASHBOARD ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Radar Familiar Pro")
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
                        "Precio": f"S/. {list(hist.values())[-1]}"
                    })
                st.table(pd.DataFrame(lista))
            except:
                st.error("Error leyendo datos.")
    else:
        st.info("Presiona 'FORZAR ESCANEO' en el menú lateral.")

# --- GESTIÓN ---
elif menu == "🛠️ Gestionar Enlaces":
    st.title("🛠️ Gestionar Enlaces Pro")
    with st.container(border=True):
        col1, col2 = st.columns(2)
        tienda = col1.selectbox("Tienda", ["Adidas", "Falabella", "Marathon", "Ripley"])
        url = col2.text_input("URL exacta")
        nombre = st.text_input("Nombre (Sin espacios)")
        
        if st.button("💾 GUARDAR"):
            with open(URLS_FILE, "a") as f:
                f.write(f"{url},100,{tienda}_{nombre}_M\n")
            st.success("✅ Guardado.")
            st.rerun()

    st.subheader("📋 Lista Actual")
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r") as f:
            st.code(f.read())
