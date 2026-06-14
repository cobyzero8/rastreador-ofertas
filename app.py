import streamlit as st
import json
import os
import pandas as pd

st.set_page_config(page_title="Radar Pro", layout="wide")

URLS_FILE = "urls.txt"
HISTORIAL_FILE = "historial_precios.json"

st.title("🕵️‍♂️ Radar Familiar Pro")

menu = st.sidebar.radio("Navegación", ["📈 Dashboard", "🛠️ Gestionar"])

if menu == "📈 Dashboard":
    # Leemos historial
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r") as f:
            data = json.load(f)
            # Leemos los links para el dashboard
            links = {}
            if os.path.exists(URLS_FILE):
                with open(URLS_FILE, "r") as f:
                    for l in f.readlines():
                        p = l.strip().split(",")
                        if len(p) >= 3: links[p[2]] = p[0]
            
            rows = []
            for id_p, hist in data.items():
                p = id_p.split("_")
                rows.append({"Tienda": p[0], "Producto": p[1], "Precio": f"S/. {list(hist.values())[-1]}", "Link": links.get(id_p, "#")})
            
            st.data_editor(pd.DataFrame(rows), column_config={"Link": st.column_config.LinkColumn()}, use_container_width=True)
    else:
        st.info("El robot aún no ha generado datos.")

elif menu == "🛠️ Gestionar":
    # Formulario para añadir artículos
    with st.form("nuevo_link"):
        c1, c2 = st.columns(2)
        tienda = c1.selectbox("Tienda", ["Adidas", "Falabella", "Marathon", "Ripley"])
        url = c2.text_input("URL")
        nombre = st.text_input("Nombre (Sin espacios)")
        talla = st.text_input("Talla")
        if st.form_submit_button("Guardar"):
            with open(URLS_FILE, "a") as f: # 'a' es para AÑADIR, no sobreescribir
                f.write(f"{url},100,{tienda}_{nombre}_{talla}\n")
            st.success("Guardado.")

    st.subheader("Enlaces actuales")
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r") as f:
            st.code(f.read())
