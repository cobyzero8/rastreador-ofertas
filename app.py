import streamlit as st
import json
import os
import pandas as pd
import requests

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Radar Pro - Panel Central", layout="wide")

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

# --- MENÚ DE NAVEGACIÓN ---
st.sidebar.title("💥 Radar Familiar Pro")
menu = st.sidebar.radio("Selecciona una opción:", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces Pro", "💥 Forzar Escaneo"])

# --- OPCIÓN 1: DASHBOARD ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Radar Familiar Pro")
    st.subheader("📊 Dashboard: Artículos bajo vigilancia")
    
    links_mapeados = {}
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            for line in f.readlines():
                p = line.strip().split(",")
                if len(p) >= 3:
                    links_mapeados[p[2]] = p[0]

    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                lista = []
                for id_prod, hist in data.items():
                    parts = id_prod.split("_")
                    clave_buscar = f"{parts[0]}_{parts[1]}_{parts[2]}" if len(parts) > 2 else id_prod
                    link_final = links_mapeados.get(clave_buscar, "#")
                    
                    lista.append({
                        "Tienda": parts[0] if len(parts) > 0 else "N/A",
                        "Producto": parts[1].replace("-", " ") if len(parts) > 1 else "N/A",
                        "Talla": parts[2] if len(parts) > 2 else "N/A",
                        "Precio": f"S/. {list(hist.values())[-1]}" if hist else "N/A",
                        "Link de Compra": link_final
                    })
                
                df = pd.DataFrame(lista)
                if not df.empty:
                    st.data_editor(
                        df,
                        column_config={"Link de Compra": st.column_config.LinkColumn("Compra Directa")},
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("El historial está vacío.")
        except Exception as e:
            st.error(f"Error al cargar el historial: {e}")
    else:
        st.info("No hay datos históricos. Agrega tus enlaces en 'Gestionar Enlaces Pro'.")

# --- OPCIÓN 2: GESTIONAR ENLACES PRO ---
elif menu == "🛠️ Gestionar Enlaces Pro":
    st.title("🛠️ Gestionar Enlaces Pro")
    
    with st.container(border=True):
        st.write("### 📝 Registrar nuevo artículo")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            tienda = st.selectbox("Tienda", ["Adidas", "Falabella", "Marathon", "Ripley", "Puma", "Nike"])
            nombre = st.text_input("Nombre del producto (Usa guiones, ej: Zapatilla-Ultraboost)")
        with c2:
            url = st.text_input("URL exacta del artículo")
            talla = st.text_input("Talla (Ej: 9.5US o M)")
        with c3:
            precio_max = st.number_input("Precio máximo (Tope S/.)", value=100, min_value=1)
            st.write("###")
            if st.button("💾 GUARDAR ARTÍCULO", type="primary", use_container_width=True):
                if nombre and url:
                    nombre_limpio = nombre.replace(" ", "-")
                    nueva_linea = f"{url},{precio_max},{tienda}_{nombre_limpio}_{talla}\n"
                    
                    with open(URLS_FILE, "a", encoding="utf-8") as f:
                        f.write(nueva_linea)
                        
                    st.toast("✅ ¡Artículo guardado correctamente con tu precio tope!")
                    st.rerun()
                else:
                    st.error("❌ Por favor, completa los campos requeridos (Nombre y URL).")

    st.write("---")
    st.subheader("📋 Lista de Radares Configurados")
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            lineas = f.read()
            if lineas.strip():
                st.code(lineas)
            else:
                st.info("No hay artículos en tu lista de monitoreo.")
    else:
        st.info("Aún no se ha creado el archivo de enlaces.")

# --- OPCIÓN 3: FORZAR ESCANEO ---
elif menu == "💥 Forzar Escaneo":
    st.title("💥 Forzar Escaneo Automático")
    st.write("Presiona el botón para enviar la orden de ejecución al sistema. Al finalizar, recibirás la confirmación en Telegram con los datos y el link del artículo.")
    
    contenedor_mensaje = st.empty()
    
    if st.button("💥 INICIAR ESCANEO INTENSIVO", type="primary", use_container_width=True):
        contenedor_mensaje.info("⏳ Ejecutando orden de rastreo... Por favor espera.")
        
        try:
            from scraper import revisar_ofertas
            revisar_ofertas()
            contenedor_mensaje.success("✅ ¡Escaneo completado con éxito!")
        except Exception as e:
            contenedor_mensaje.error(f"❌ Error al ejecutar el rastreador externo: {e}")
            st.code(str(e))
