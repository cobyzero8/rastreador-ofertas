import streamlit as st
import json
import os
import pandas as pd
from scraper import revisar_ofertas # Importamos la función directamente

st.set_page_config(page_title="CobyZero8 - Radar Pro", layout="wide")

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Control Maestro")
    
    # Botón con feedback profesional
    if st.button("💥 FORZAR ESCANEO", use_container_width=True):
        status = st.empty() # Contenedor para mensajes
        with st.spinner("🚀 Ejecutando rastreo... esto tardará unos segundos."):
            try:
                revisar_ofertas()
                st.success("✅ ¡Escaneo terminado con éxito!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Falló el escaneo: {e}")
    
    st.write("---")
    menu = st.radio("Navegación", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces"])

# --- DASHBOARD ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Radar Familiar Pro")
    st.subheader("📊 Dashboard: Artículos bajo vigilancia")
    
    # Cargamos links para el botón de compra
    links = {}
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r") as f:
            for line in f.readlines():
                parts = line.strip().split(",")
                if len(parts) >= 3: links[parts[2]] = parts[0]

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
                        "Precio": f"S/. {list(hist.values())[-1]}",
                        "Link": links.get(id_prod, "#")
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
                    st.info("No hay datos todavía. Presiona 'FORZAR ESCANEO'.")
            except Exception as e:
                st.error(f"Error al leer historial: {e}")
    else:
        st.info("Presiona 'FORZAR ESCANEO' para iniciar.")

# --- GESTIÓN ---
elif menu == "🛠️ Gestionar Enlaces":
    st.title("🛠️ Gestionar Enlaces Pro")
    with st.container(border=True):
        c1, c2 = st.columns(2)
        tienda = c1.selectbox("Tienda", ["Adidas", "Falabella", "Marathon", "Ripley"])
        url = c2.text_input("URL del producto")
        c3, c4 = st.columns(2)
        nombre = c3.text_input("Nombre (Sin espacios)")
        talla = c4.text_input("Talla (Ej: 9.5US)")
        
        if st.button("💾 GUARDAR", type="primary"):
            if nombre and url:
                linea = f"{url},100,{tienda}_{nombre.replace(' ', '-')}_{talla}\n"
                with open(URLS_FILE, "a") as f:
                    f.write(linea)
                st.toast("✅ ¡Artículo guardado!")
                st.rerun()
            else:
                st.error("Completa Nombre y URL.")

    st.subheader("📋 Enlaces Activos")
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r") as f:
            st.code(f.read())
