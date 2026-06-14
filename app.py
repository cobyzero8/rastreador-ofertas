import streamlit as st
import json
import os
import pandas as pd

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="CobyZero8 - Radar Pro", layout="wide")
HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

# --- LÓGICA DE ESCANEO (INTEGRADA) ---
def ejecutar_escaneo():
    try:
        # Aquí llamaríamos a tu función de scraping real
        # Por ahora, simulamos la ejecución para no bloquear la app
        from scraper import revisar_ofertas
        revisar_ofertas()
        return True
    except Exception as e:
        st.error(f"Error técnico: {e}")
        return False

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Control Maestro")
    if st.button("💥 FORZAR ESCANEO", use_container_width=True):
        with st.spinner("🚀 Ejecutando rastreo..."):
            if ejecutar_escaneo():
                st.success("✅ Escaneo terminado.")
                st.rerun()
            else:
                st.error("❌ Falló el escaneo.")

    st.write("---")
    menu = st.radio("Navegación", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces"])

# --- DASHBOARD ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Radar Familiar Pro")
    st.subheader("📊 Dashboard: Artículos bajo vigilancia")
    
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Leer URLs para cruzar información
            urls_map = {}
            if os.path.exists(URLS_FILE):
                with open(URLS_FILE, "r") as f:
                    for l in f.readlines():
                        p = l.strip().split(",")
                        if len(p) >= 3: urls_map[p[2]] = p[0]

            lista = []
            for id_prod, hist in data.items():
                parts = id_prod.split("_")
                lista.append({
                    "Tienda": parts[0],
                    "Producto": parts[1].replace("-", " "),
                    "Talla": parts[2] if len(parts) > 2 else "N/A",
                    "Precio": f"S/. {list(hist.values())[-1]}",
                    "Link": urls_map.get(id_prod, "#")
                })
            
            if lista:
                df = pd.DataFrame(lista)
                st.data_editor(
                    df,
                    column_config={"Link": st.column_config.LinkColumn("Compra Directa")},
                    hide_index=True,
                    use_container_width=True
                )
            else:
                st.info("Aún no se han detectado ofertas.")
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
        talla = c4.text_input("Talla")
        
        if st.button("💾 GUARDAR", type="primary"):
            linea = f"{url},100,{tienda}_{nombre.replace(' ', '-')}_{talla}\n"
            with open(URLS_FILE, "a") as f:
                f.write(linea)
            st.success("✅ Guardado.")
            st.rerun()
