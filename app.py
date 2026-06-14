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
    # Placeholder para mensajes de estado
    status_placeholder = st.empty()
    
    if st.button("💥 FORZAR ESCANEO", use_container_width=True):
        status_placeholder.info("⏳ Ejecutando escaneo, por favor espera...")
        # Ejecutamos y capturamos el resultado
        resultado = os.system("python scraper.py")
        if resultado == 0:
            status_placeholder.success("✅ Escaneo terminado con éxito.")
        else:
            status_placeholder.error("❌ Error en el escaneo. Revisa los logs.")
    
    st.write("---")
    menu = st.radio("Navegación", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces Pro"])

# --- LÓGICA DE DICCIONARIO ---
def obtener_datos_configurados():
    datos = {}
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r") as f:
            for line in f.readlines():
                parts = line.strip().split(",")
                if len(parts) >= 3:
                    # partes[2] es el ID (Tienda_Nombre_Talla), partes[0] es la URL
                    datos[parts[2]] = {"url": parts[0], "precio_tope": parts[1]}
    return datos

# --- PANTALLAS ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Radar Familiar Pro")
    st.subheader("📊 Dashboard: Artículos bajo vigilancia")
    
    config = obtener_datos_configurados()
    
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                lista = []
                for id_prod, hist in data.items():
                    parts = id_prod.split("_")
                    # Buscamos la URL configurada para este ID
                    link_info = config.get(id_prod, {"url": "#"})
                    
                    lista.append({
                        "Tienda": parts[0],
                        "Producto": parts[1].replace("-", " "),
                        "Talla": parts[2] if len(parts) > 2 else "N/A",
                        "Precio": f"S/. {list(hist.values())[-1]}",
                        "Link": link_info["url"]
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
                    st.info("Ejecuta un escaneo para poblar el dashboard.")
            except:
                st.error("Error al procesar el historial.")
    else:
        st.info("No hay datos históricos. Agrega productos y presiona 'FORZAR ESCANEO'.")

elif menu == "🛠️ Gestionar Enlaces Pro":
    st.title("🛠️ Gestionar Enlaces Pro")
    
    with st.container(border=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            tienda = st.selectbox("Tienda", ["Adidas", "Falabella", "Marathon", "Ripley", "Puma", "Nike"])
            talla = st.text_input("Talla (Ej: 9.5US)")
        with c2:
            nombre = st.text_input("Nombre del artículo (Sin espacios)")
            precio = st.number_input("Precio máximo (S/.)", value=100)
        with c3:
            url = st.text_input("URL exacta del producto")
        with c4:
            st.write("###") 
            if st.button("💾 GUARDAR Y AGREGAR", type="primary", use_container_width=True):
                if nombre and url:
                    nueva_linea = f"{url},{precio},{tienda}_{nombre.replace(' ', '-')}_{talla}"
                    lineas = []
                    if os.path.exists(URLS_FILE):
                        with open(URLS_FILE, "r") as f:
                            lineas = f.readlines()
                    lineas.insert(0, nueva_linea + "\n")
                    with open(URLS_FILE, "w") as f:
                        f.writelines(lineas)
                    st.toast("✅ Artículo guardado exitosamente!")
                    st.rerun()
                else:
                    st.error("Por favor completa Nombre y URL.")

    st.subheader("📋 Lista de Enlaces Activos")
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r") as f:
            for line in f.readlines():
                st.code(line.strip())
