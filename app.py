import streamlit as st
import json
import os
import pandas as pd

st.set_page_config(page_title="CobyZero8 - Radar Pro", layout="wide")

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

# Cambia esto:
with open("urls.txt", "r") as f:
# Por esto (ruta absoluta):
script_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(script_dir, "urls.txt")
with open(file_path, "r") as f:

# --- DASHBOARD ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Radar Familiar Pro")
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
                        "Precio": f"S/. {list(hist.values())[-1]}"
                    })
                st.table(pd.DataFrame(lista))
            except:
                st.error("Error al leer el historial.")
    else:
        st.info("No hay artículos en el historial.")

# --- GESTIÓN DE ENLACES ---
elif menu == "🛠️ Gestionar Enlaces":
    st.title("🛠️ Gestionar Enlaces Pro")
    
    with st.container(border=True):
        st.write("### 📝 Datos del Artículo")
        # Layout en 2 filas
        c1, c2, c3 = st.columns(3)
        with c1:
            tienda = st.selectbox("Tienda", ["Adidas", "Falabella", "Marathon", "Ripley", "Puma", "Nike"])
            nombre = st.text_input("Nombre del producto (sin espacios)")
        with c2:
            url = st.text_input("URL del artículo")
            talla = st.text_input("Talla (Ej: 9.5US)")
        with c3:
            precio = st.number_input("Precio máximo (Tope S/.)", value=100)
            st.write("###") 
            if st.button("💾 GUARDAR ARTÍCULO", type="primary", use_container_width=True):
                if nombre and url:
                    # Guardamos el formato: URL,PRECIO,ID_PRODUCTO
                    # El ID es: Tienda_Nombre_Talla
                    nueva_linea = f"{url},{precio},{tienda}_{nombre.replace(' ', '-')}_{talla}\n"
                    with open(URLS_FILE, "a") as f:
                        f.write(nueva_linea)
                    st.toast("✅ ¡Artículo guardado exitosamente!")
                    st.rerun()
                else:
                    st.error("Por favor completa al menos el nombre y la URL.")

    st.subheader("📋 Enlaces Activos")
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r") as f:
            st.code(f.read())
