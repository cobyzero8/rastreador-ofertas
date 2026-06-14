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
        st.warning("Ejecutando escaneo... revisa tu Telegram.")
        os.system("python scraper.py")
        st.success("Escaneo terminado.")
    st.write("---")
    menu = st.radio("Navegación", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces Pro"])

# --- LÓGICA DE DICCIONARIO DE LINKS ---
def obtener_links():
    links = {}
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r") as f:
            for line in f.readlines():
                parts = line.strip().split(",")
                if len(parts) >= 3:
                    links[parts[2]] = parts[0]
    return links

# --- PANTALLAS ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Radar Familiar Pro")
    st.subheader("📊 Dashboard: Artículos bajo vigilancia")
    
    links = obtener_links()
    
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
                        "Link": links.get(id_prod, "No disponible")
                    })
                
                df = pd.DataFrame(lista)
                st.data_editor(
                    df,
                    column_config={"Link": st.column_config.LinkColumn("Compra Directa")},
                    hide_index=True,
                    use_container_width=True
                )
            except:
                st.error("Error al leer los datos. Asegúrate de ejecutar el escaneo.")
    else:
        st.info("No hay datos históricos. Por favor, ve a 'Gestionar Enlaces' y añade un producto.")

elif menu == "🛠️ Gestionar Enlaces Pro":
    st.title("🛠️ Gestionar Enlaces Pro")
    
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
            st.write("###") 
            if st.button("💾 GUARDAR Y AGREGAR", type="primary", use_container_width=True):
                nueva_linea = f"{url},{precio},{tienda}_{nombre.replace(' ', '-')}_{talla}"
                lineas = []
                if os.path.exists(URLS_FILE):
                    with open(URLS_FILE, "r") as f:
                        lineas = f.readlines()
                lineas.insert(0, nueva_linea + "\n")
                with open(URLS_FILE, "w") as f:
                    f.writelines(lineas)
                st.toast("✅ Artículo guardado!")
                st.rerun()

    st.subheader("📋 Lista de Enlaces Activos")
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r") as f:
            for line in f.readlines():
                st.code(line.strip())
