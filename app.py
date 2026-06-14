import streamlit as st
import json
import os
import pandas as pd
import requests

st.set_page_config(page_title="CobyZero8 - Radar Familiar Pro", page_icon="🕵️‍♂️", layout="wide")

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

# INICIALIZACIÓN DE ESTADO
if "reset_key" not in st.session_state:
    st.session_state.reset_key = 0

def cargar_urls():
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            return [linea.strip() for linea in f.readlines() if linea.strip() and "," in linea]
    return []

def guardar_urls(lista_lineas):
    with open(URLS_FILE, "w", encoding="utf-8") as f:
        for linea in lista_lineas:
            f.write(f"{linea}\n")

st.title("🕵️‍♂️ CobyZero8 - Radar Familiar Pro")

menu = st.sidebar.selectbox("Navegación", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces Pro"])

if menu == "📈 Ver Dashboard":
    st.subheader("📊 Monitoreo de Ofertas")
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            lista = []
            for id_prod, hist in data.items():
                tienda, cat, talla, nombre = id_prod.split("_", 3)
                lista.append({"Tienda": tienda, "Producto": nombre.replace("_", " "), "Precio": list(hist.values())[-1]})
            st.dataframe(pd.DataFrame(lista), use_container_width=True)

elif menu == "🛠️ Gestionar Enlaces Pro":
    st.subheader("🔗 Administrador Avanzado")
    suffix = str(st.session_state.reset_key)
    
    c1, c2 = st.columns(2)
    tienda = c1.selectbox("Tienda", ["Adidas", "Falabella", "Marathon"], key="t_"+suffix)
    seccion = c2.text_input("Sección", value="Zapatillas", key="s_"+suffix)
    url = st.text_input("URL", value="", key="u_"+suffix)
    c3, c4 = st.columns(2)
    precio = c3.number_input("Tope", value=100, key="p_"+suffix)
    talla = c4.text_input("Talla", value="M", key="talla_"+suffix)

    if st.button("🚀 AÑADIR AL RADAR", type="primary"):
        if url and seccion:
            lineas = cargar_urls()
            nueva_linea = f"{url},{precio},{tienda}_{seccion}_{talla}"
            lineas.insert(0, nueva_linea)
            guardar_urls(lineas)
            st.session_state.reset_key += 1
            st.rerun()
