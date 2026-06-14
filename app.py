import streamlit as st
import pandas as pd
import json
import os

st.set_page_config(page_title="Radar Pro - Panel", layout="wide")

st.title("🕵️‍♂️ Radar Familiar Pro")

# Navegación
menu = st.sidebar.radio("Navegación", ["📈 Dashboard", "🛠️ Configuración"])

if menu == "📈 Dashboard":
    st.subheader("📊 Artículos bajo vigilancia")
    if os.path.exists("historial_precios.json"):
        with open("historial_precios.json", "r") as f:
            data = json.load(f)
            
            # Cargamos enlaces para el cruce
            links = {}
            if os.path.exists("urls.txt"):
                with open("urls.txt", "r") as f:
                    for l in f.readlines():
                        p = l.strip().split(",")
                        if len(p) >= 3: links[p[2]] = p[0]

            rows = []
            for id_prod, hist in data.items():
                p = id_prod.split("_")
                rows.append({
                    "Producto": p[1].replace("-", " "),
                    "Precio": f"S/. {list(hist.values())[-1]}",
                    "Link": links.get(id_prod, "#")
                })
            
            if rows:
                df = pd.DataFrame(rows)
                st.data_editor(df, column_config={"Link": st.column_config.LinkColumn()}, use_container_width=True)
            else:
                st.info("El robot aún no ha escaneado datos.")

elif menu == "🛠️ Configuración":
    st.subheader("➕ Agregar Nuevo Producto")
    with st.form("nuevo"):
        nombre = st.text_input("Nombre (Sin espacios)")
        url = st.text_input("URL")
        if st.form_submit_button("Guardar"):
            with open("urls.txt", "a") as f:
                f.write(f"{url},100,Tienda_{nombre}_M\n")
            st.success("Guardado.")
