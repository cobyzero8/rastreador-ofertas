import streamlit as st
import json
import os
import pandas as pd
import requests

st.set_page_config(page_title="Radar Pro - Panel Central", layout="wide")

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"
TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

# Lista de categorías de primera necesidad / hogar
PRIMERA_NECESIDAD = ["SHAMPOO", "DESODORANTE", "JABON", "PERFUMES", "ALIMENTOS", "ABARROTES", "HOGAR", "SALUD"]

def sincronizar_mensajes_telegram():
    url_updates = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/getUpdates"
    try:
        res = requests.get(url_updates, params={"offset": -10, "timeout": 1}, timeout=5).json()
        if "result" in res and res["result"]:
            for update in res["result"]:
                if "callback_query" in update:
                    callback = update["callback_query"]
                    data_btn = callback["data"]
                    callback_id = callback["id"]
                    
                    if data_btn.startswith("pausar_"):
                        id_radar_borrar = data_btn.replace("pausar_", "").strip()
                        if os.path.exists(URLS_FILE):
                            with open(URLS_FILE, "r", encoding="utf-8") as f:
                                lineas = [l.strip() for l in f.readlines() if l.strip()]
                            nuevas_lineas = [l for l in lineas if id_radar_borrar not in l]
                            with open(URLS_FILE, "w", encoding="utf-8") as f:
                                for nl in nuevas_lineas: f.write(nl + "\n")
                            requests.post(f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/answerCallbackQuery", json={"callback_query_id": callback_id, "text": "🔕 Radar desactivado."})
                            requests.post(f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage", json={"chat_id": CHAT_ID_TELEGRAM, "text": f"✅ Removido con ID `{id_radar_borrar}` desde Telegram."})
                            st.rerun()

                elif "message" in update and "text" in update["message"]:
                    msg = update["message"]
                    texto = msg["text"].strip().lower()
                    if texto.startswith("/"):
                        if texto in ["/lista", "/radares"]:
                            if os.path.exists(URLS_FILE):
                                with open(URLS_FILE, "r", encoding="utf-8") as f:
                                    r_lineas = [l.strip() for l in f.readlines() if l.strip()]
                                txt_retorno = "📋 *RADARES BAJO VIGILANCIA:*\n\n"
                                for rl in r_lineas:
                                    partes_r = rl.split(",")
                                    if len(partes_r) >= 3:
                                        meta = partes_r[2].split("-")
                                        txt_retorno += f"🔹 *[{meta[0]}]* {meta[2].replace('_',' ')} (#{meta[1]}) - Tope S/. {partes_r[1]}\n"
                                requests.post(f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage", json={"chat_id": CHAT_ID_TELEGRAM, "text": txt_retorno, "parse_mode": "Markdown"})
                        else:
                            cat_buscar = texto.replace("/", "").upper()
                            if os.path.exists(HISTORIAL_FILE):
                                with open(HISTORIAL_FILE, "r", encoding="utf-8") as f: h_data = json.load(f)
                                txt_retorno = f"📂 *ARTÍCULOS EN CATEGORÍA #{cat_buscar}:*\n\n"
                                hallado = False
                                for k, v in h_data.items():
                                    meta = k.split("-")
                                    if len(meta) > 1 and meta[1] == cat_buscar:
                                        hallado = True
                                        txt_retorno += f"📦 *{meta[2].replace('_',' ')}* ({meta[0]}) -> Último: S/. {list(v.values())[-1]}\n"
                                if not hallado: txt_retorno += "No hay registros guardados."
                                requests.post(f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage", json={"chat_id": CHAT_ID_TELEGRAM, "text": txt_retorno, "parse_mode": "Markdown"})
    except: pass

st.sidebar.write("---")
if st.sidebar.button("📥 SINCRONIZAR TELEGRAM 📱", use_container_width=True, type="secondary"):
    sincronizar_mensajes_telegram()
    st.sidebar.success("Sincronizado.")

st.sidebar.title("💥 Radar Familiar Pro")
menu = st.sidebar.radio("Selecciona una opción:", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces Pro", "💥 Forzar Escaneo"])

# --- OPCIÓN 1: DASHBOARD CON PASO C (PESTAÑAS DE SEPARACIÓN HOGAR VS GUSTOS) ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Radar Familiar Pro")
    st.subheader("📊 Dashboard de Artículos")
    
    links_mapeados = {}
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            for line in f.readlines():
                p = line.strip().split(",")
                if len(p) >= 3: links_mapeados[p[2]] = p[0]

    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f: data = json.load(f)
            
            lista_hogar = []
            lista_personal = []
            
            for id_prod, hist in data.items():
                parts = id_prod.split("-")
                tienda_txt = parts[0] if len(parts) > 0 else "N/A"
                cat_txt = parts[1].upper() if len(parts) > 1 else "OTROS"
                prod_txt = parts[2] if len(parts) > 2 else "N/A"
                talla_txt = parts[3] if len(parts) > 3 else "N/A"
                
                clave_link = f"{tienda_txt}-{cat_txt}-{prod_txt}-{talla_txt}"
                link_final = links_mapeados.get(clave_link, "#")
                
                ultimo_precio = list(hist.values())[-1] if hist else "N/A"
                item_dict = {
                    "ID": id_prod, "Tienda": tienda_txt.upper(), "Categoría": cat_txt,
                    "Elemento": prod_txt.replace("_", " "), "Detalle/Talla": talla_txt,
                    "Precio": f"S/. {ultimo_precio}" if ultimo_precio != "N/A" else "N/A", "Compra": link_final
                }
                
                # --- PASO C: CLASIFICACIÓN INTERNA DE PESTAÑAS ---
                if cat_txt in PRIMERA_NECESIDAD or cat_txt in ["ALIMENTOS", "ABARROTES", "SHAMPOO", "JABON", "DESODORANTE"]:
                    lista_hogar.append(item_dict)
                else:
                    lista_personal.append(item_dict)
            
            # Dibujamos las dos pestañas de visualización en Streamlit
            tab1, tab2 = st.tabs(["🛒 Canasta Hogar / Primera Necesidad", "👟 Gustos Personales y Viajes"])
            
            with tab1:
                st.write("### 🏠 Artículos esenciales de la casa")
                if lista_hogar:
                    df_h = pd.DataFrame(lista_hogar)
                    st.data_editor(df_h.drop(columns=["ID"]), column_config={"Compra": st.column_config.LinkColumn("Ir al Enlace")}, hide_index=True, use_container_width=True)
                else: st.info("No hay artículos esenciales registrados.")
                
            with tab2:
                st.write("### 😎 Ropa, Tecnología y Pasajes de Avión")
                if lista_personal:
                    df_p = pd.DataFrame(lista_personal)
                    st.data_editor(df_p.drop(columns=["ID"]), column_config={"Compra": st.column_config.LinkColumn("Ir al Enlace")}, hide_index=True, use_container_width=True)
                else: st.info("No hay artículos personales registrados.")
                
            st.write("---")
            st.write("### 📈 Evolución Temporal de Precios")
            todos_productos = [i["Elemento"] for i in lista_hogar] + [i["Elemento"] for i in lista_personal]
            if todos_productos:
                producto_grafica = st.selectbox("📊 Selecciona un producto para ver su gráfica:", list(set(todos_productos)))
                id_seleccionado = ""
                for item in (lista_hogar + lista_personal):
                    if item["Elemento"] == producto_grafica: id_seleccionado = item["ID"]; break
                
                historial_puntos = data.get(id_seleccionado, {})
                if historial_puntos:
                    df_grafica = pd.DataFrame(list(historial_puntos.items()), columns=["Fecha", "Precio (S/.)"]).set_index("Fecha")
                    st.line_chart(df_grafica)
                    
        except Exception as e: st.error(f"Error: {e}")
    else: st.info("No hay datos disponibles.")

# --- OPCIÓN 2: GESTIONAR ENLACES CON TIENDAS DE ABARROTES Y VUELOS ---
elif menu == "🛠️ Gestionar Enlaces Pro":
    st.title("🛠️ Gestionar Enlaces Pro")
    with st.container(border=True):
        st.write("### 📝 Registrar nuevo artículo clasificado")
        c1, c2, c3 = st.columns(3)
        with c1:
            # TIENDAS TOTALMENTE AMPLIADAS (PASO A Y B)
            tienda = st.selectbox("Tienda", [
                "Adidas", "Falabella", "Marathon", "Ripley", "Puma", "Nike", 
                "Natura", "Mifarma", "Inkafarma", "Mercado Libre", "Triathlon", "JBL", "Samsung",
                "Lbel", "Esika", "Cyzone", "Plaza Vea", "Tottus", "Metro", "Latam", "Sky"
            ])
            cat_sugerida = st.selectbox("Seleccionar Categoría Frecuente", ["Zapatillas", "Polos", "Poleras", "Casacas", "Pantalon deportivo", "Perfumes", "Shampoo", "Desodorante", "Jabon", "Abarrotes", "Vuelos", "Otros"])
            cat_manual = st.text_input("✍️ O escribir Nueva Categoría", "").strip()
            categoria_final = cat_manual if cat_manual else cat_sugerida
        with c2:
            nombre = st.text_input("Nombre (ej: Pañales_Huggies o Vuelo_Cusco_Lima)")
            url = st.text_input("URL exacta del artículo")
        with c3:
            talla = st.text_input("Talla/Volumen/Fecha (Ej: G, 120ml, 15-Julio)")
            precio_max = st.number_input("Precio máximo tope (S/.)", value=100, min_value=1)
            
        if st.button("💾 GUARDAR ARTÍCULO CLASIFICADO", type="primary", use_container_width=True):
            if nombre and url:
                nombre_limpio = nombre.replace(" ", "_").strip()
                nueva_linea = f"{url},{precio_max},{tienda.upper().replace(' ', '_')}-{categoria_final.upper().strip()}-{nombre_limpio}-{talla.strip() if talla.strip() else 'TODAS'}\n"
                with open(URLS_FILE, "a", encoding="utf-8") as f: f.write(nueva_linea)
                st.toast("✅ ¡Guardado con éxito!")
                st.rerun()

    st.write("---")
    st.subheader("📋 Panel de Control de Radares")
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f: lineas = [l.strip() for l in f.readlines() if l.strip()]
        if lineas:
            for index, linea in enumerate(lineas):
                partes = linea.split(",")
                if len(partes) >= 3:
                    precio_display = partes[1]
                    meta_parts = partes[2].split("-")
                    tnd = meta_parts[0]; cat = meta_parts[1] if len(meta_parts)>1 else "OTROS"
                    prod = meta_parts[2].replace("_", " ") if len(meta_parts)>2 else "PRODUCTO"
                    tll = meta_parts[3] if len(meta_parts)>3 else "N/A"
                    
                    col_info, col_btn = st.columns([8, 2])
                    with col_info: st.markdown(f"**{index + 1}. [{tnd}]** {prod} | Categoría: `{cat}` | Detalle: `{tll}` | Tope: `S/. {precio_display}`")
                    with col_btn:
                        if st.button(f"🗑️ Eliminar", key=f"del_{index}", type="secondary", use_container_width=True):
                            lineas.pop(index); with open(URLS_FILE, "w", encoding="utf-8") as f_w:
                                for lr in lineas: f_w.write(lr + "\n")
                            st.rerun()
        else: st.info("No hay radares.")

elif menu == "💥 Forzar Escaneo":
    st.title("💥 Forzar Escaneo Automático")
    contenedor_mensaje = st.empty()
    if st.button("💥 INICIAR ESCANEO INTENSIVO", type="primary", use_container_width=True):
        contenedor_mensaje.info("⏳ Buscando ofertas familiares en mercados y aerolíneas...")
        try:
            from scraper import revisar_ofertas
            revisar_ofertas()
            contenedor_mensaje.success("✅ ¡Escaneo completado! Revisa tu Telegram.")
            st.rerun()
        except Exception as e: contenedor_mensaje.error(f"❌ Error: {e}")
