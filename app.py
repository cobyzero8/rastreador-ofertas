import streamlit as st
import json
import os
import pandas as pd

st.set_page_config(page_title="CobyZero8 - Radar Pro", layout="wide")

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

# Funciones de utilidad
def cargar_urls():
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            return [linea.strip() for linea in f.readlines() if linea.strip() and "," in linea]
    return []

st.title("🕵️‍♂️ Radar Familiar Pro - CobyZero8")

# Botón de FORZAR ESCANEO (Siempre visible)
if st.button("💥 FORZAR ESCANEO MANUAL AHORA"):
    st.warning("Ejecutando proceso de rastreo... verifica tu Telegram.")
    # Esto activará tu script scraper.py
    os.system("python scraper.py") 
    st.success("Escaneo terminado.")

menu = st.sidebar.selectbox("Navegación", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces Pro"])

if menu == "📈 Ver Dashboard":
    st.subheader("📊 Artículos bajo vigilancia")
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            lista = []
            for id_prod, hist in data.items():
                tienda, cat, talla, nombre = id_prod.split("_", 3)
                lista.append({
                    "Tienda": tienda, 
                    "Producto": nombre.replace("_", " "), 
                    "Precio Actual": list(hist.values())[-1]
                })
            df = pd.DataFrame(lista)
            st.table(df) # Tabla simple para no colgar el navegador
    else:
        st.info("Aún no hay datos. Agrega enlaces en la pestaña de Gestión.")

elif menu == "🛠️ Gestionar Enlaces Pro":
    st.subheader("🔗 Enlaces Activos")
    urls = cargar_urls()
    for u in urls:
        st.code(u) # Aquí verás tus artículos actuales para verificar que existen
        
    st.write("---")
    st.subheader("➕ Agregar nuevo artículo")
    c1, c2 = st.columns(2)
    tienda = c1.selectbox("Tienda", ["Adidas", "Falabella", "Marathon", "Ripley"])
    url_input = c2.text_input("Pega aquí el LINK del producto (con el filtro de talla ya hecho)")
    
    if st.button("GUARDAR ENLACE"):
        nueva_linea = f"{url_input},100,{tienda}_General_M"
        urls.append(nueva_linea)
        with open(URLS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(urls))
        st.success("Guardado. Ahora presiona FORZAR ESCANEO.")
