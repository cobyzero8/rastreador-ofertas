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

# --- FUNCIÓN PASO B Y C: PROCESAR COMANDOS Y BOTONES DESDE TELEGRAM ---
def sincronizar_mensajes_telegram():
    url_updates = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/getUpdates"
    try:
        res = requests.get(url_updates, params={"offset": -10, "timeout": 1}, timeout=5).json()
        if "result" in res and res["result"]:
            for update in res["result"]:
                # 1. Captura pulsaciones de botones (Callback Queries - Paso C)
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
                                
                            # Responder a Telegram que fue borrado con éxito
                            requests.post(f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/answerCallbackQuery", json={"callback_query_id": callback_id, "text": "🔕 Radar desactivado y removido."})
                            requests.post(f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage", json={"chat_id": CHAT_ID_TELEGRAM, "text": f"✅ El artículo con ID `{id_radar_borrar}` ha sido removido del sistema desde Telegram."})
                            st.rerun()

                # 2. Captura comandos de texto escritos por ti (Paso B)
                elif "message" in update and "text" in update["message"]:
                    msg = update["message"]
                    texto = msg["text"].strip().lower()
                    
                    if texto.startswith("/"):
                        # Comando genérico /lista
                        if texto == "/lista" or texto == "/radares":
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
                        
                        # Comandos por categoría por ejemplo /perfumes, /zapatillas
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
                                if not hallado: txt_retorno += "No hay registros guardados en esta categoría aún."
                                requests.post(f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage", json={"chat_id": CHAT_ID_TELEGRAM, "text": txt_retorno, "parse_mode": "Markdown"})
    except: pass

# Botón de Sincronización Manual en la barra lateral
st.sidebar.write("---")
if st.sidebar.button("📥 SINCRONIZAR TELEGRAM 📱", use_container_width=True, type="secondary"):
    sincronizar_mensajes_telegram()
    st.sidebar.success("Sincronizado.")

# --- MENÚ PRINCIPAL ---
st.sidebar.title("💥 Radar Familiar Pro")
menu = st.sidebar.radio("Selecciona una opción:", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces Pro", "💥 Forzar Escaneo"])

if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Radar Familiar Pro")
    st.subheader("📊 Dashboard de Artículos")
    
    links_mapeados = {}
    categorias_disponibles = ["Todos"]
    
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            for line in f.readlines():
                p = line.strip().split(",")
                if len(p) >= 3:
                    links_mapeados[p[2]] = p[0]
                    meta = p[2].split("-")
                    cat_check = meta[1].upper() if len(meta) > 1 else "OTROS"
                    if cat_check not in categorias_disponibles:
                        categorias_disponibles.append(cat_check)

    categoria_seleccionada = st.selectbox("🔍 Filtrar visualización por Categoría:", categorias_disponibles)

    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                lista = []
                for id_prod, hist in data.items():
                    parts = id_prod.split("-")
                    tienda_txt = parts[0] if len(parts) > 0 else "N/A"
                    cat_txt = parts[1] if len(parts) > 1 else "OTROS"
                    prod_txt = parts[2] if len(parts) > 2 else "N/A"
                    talla_txt = parts[3] if len(parts) > 3 else "N/A"
                    
                    clave_link = f"{tienda_txt}-{cat_txt}-{prod_txt}-{talla_txt}"
                    link_final = links_mapeados.get(clave_link, "#")
                    if link_final == "#" and links_mapeados:
                        for k, v in links_mapeados.items():
                            if prod_txt in k: link_final = v; break

                    if categoria_seleccionada != "Todos" and cat_txt.upper() != categoria_seleccionada.upper(): continue
                    ultimo_precio = list(hist.values())[-1] if hist else "N/A"

                    lista.append({
                        "ID": id_prod, "Tienda": tienda_txt.upper(), "Categoría": cat_txt.upper(),
                        "Producto": prod_txt.replace("_", " "), "Talla": talla_txt,
                        "Precio Final": f"S/. {ultimo_precio}" if ultimo_precio != "N/A" else "N/A", "Link de Compra": link_final
                    })
                
                df = pd.DataFrame(lista)
                if not df.empty:
                    st.data_editor(df.drop(columns=["ID"]), column_config={"Link de Compra": st.column_config.LinkColumn("Compra Directa")}, hide_index=True, use_container_width=True)
                    st.write("### 📈 Evolución Temporal de Precios")
                    producto_grafica = st.selectbox("📊 Selecciona un producto para ver su gráfica de precios:", df["Producto"].unique())
                    id_seleccionado = df[df["Producto"] == producto_grafica]["ID"].values[0]
                    historial_puntos = data.get(id_seleccionado, {})
                    if historial_puntos:
                        df_grafica = pd.DataFrame(list(historial_puntos.items()), columns=["Fecha/Hora", "Precio (S/.)"]).set_index("Fecha/Hora")
                        st.line_chart(df_grafica)
                else: st.info("No hay productos.")
        except Exception as e: st.error(f"Error: {e}")
    else: st.info("No hay datos históricos.")

elif menu == "🛠️ Gestionar Enlaces Pro":
    st.title("🛠️ Gestionar Enlaces Pro")
    with st.container(border=True):
        st.write("### 📝 Registrar nuevo artículo clasificado")
        c1, c2, c3 = st.columns(3)
        with c1:
            tienda = st.selectbox("Tienda", ["Adidas", "Falabella", "Marathon", "Ripley", "Puma", "Nike", "Natura", "Mifarma", "Inkafarma", "Mercado Libre", "Triathlon", "JBL", "Samsung", "Lbel", "Esika", "Cyzone"])
            cat_sugerida = st.selectbox("Seleccionar Categoría Frecuente", ["Zapatillas", "Polos", "Poleras", "Casacas", "Pantalon deportivo", "Perfumes", "Shampoo", "Desodorante", "Jabon", "Otros"])
            cat_manual = st.text_input("✍️ O escribir Nueva Categoría", "").strip()
            categoria_final = cat_manual if cat_manual else cat_sugerida
        with c2:
            nombre = st.text_input("Nombre del producto (ej: Buzo_Entrenamiento)")
            url = st.text_input("URL exacta del artículo")
        with c3:
            talla = st.text_input("Talla/Volumen (Ej: 9.5US, M)")
            precio_max = st.number_input("Precio máximo (Tope S/.)", value=100, min_value=1)
            
            if nombre:
                id_simulado = f"{tienda.upper()}-{categoria_final.upper()}-{nombre.replace(' ', '_').strip()}-{talla.strip() if talla.strip() else 'TODAS'}"
                if os.path.exists(HISTORIAL_FILE):
                    with open(HISTORIAL_FILE, "r", encoding="utf-8") as f_h:
                        f_data = json.load(f_h)
                        hist_existente = f_data.get(id_simulado, {})
                        if hist_existente:
                            precios_lista = list(hist_existente.values())
                            st.caption(f"💡 **Asistente:** El precio promedio histórico es **S/. {sum(precios_lista)/len(precios_lista):.2f}**.")
            
        if st.button("💾 GUARDAR ARTÍCULO CLASIFICADO", type="primary", use_container_width=True):
            if nombre and url:
                nombre_limpio = nombre.replace(" ", "_").strip()
                nueva_linea = f"{url},{precio_max},{tienda.upper()}-{categoria_final.upper()}-{nombre_limpio}-{talla.strip() if talla.strip() else 'TODAS'}\n"
                with open(URLS_FILE, "a", encoding="utf-8") as f: f.write(nueva_linea)
                st.toast("✅ ¡Guardado correctamente!")
                st.rerun()

   st.write("---")
    st.subheader("📋 Panel de Control de Radares")
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f: 
            lineas = [l.strip() for l in f.readlines() if l.strip()]
        if lineas:
            for index, linea in enumerate(lineas):
                partes = linea.split(",")
                if len(partes) >= 3:
                    precio_display = partes[1]
                    meta_parts = partes[2].split("-")
                    tnd = meta_parts[0]
                    cat = meta_parts[1] if len(meta_parts) > 1 else "OTROS"
                    prod = meta_parts[2].replace("_", " ") if len(meta_parts) > 2 else "PRODUCTO"
                    tll = meta_parts[3] if len(meta_parts) > 3 else "N/A"
                    
                    col_info, col_btn = st.columns([8, 2])
                    with col_info: 
                        st.markdown(f"**{index + 1}. [{tnd}]** {prod} | Categoría: `{cat}` | Talla: `{tll}` | Tope: `S/. {precio_display}`")
                    with col_btn:
                        # CORRECCIÓN AQUÍ: Separamos el pop y el with en líneas distintas y limpias
                        if st.button(f"🗑️ Eliminar", key=f"del_{index}", type="secondary", use_container_width=True):
                            lineas.pop(index)
                            with open(URLS_FILE, "w", encoding="utf-8") as f_w:
                                for lr in lineas: 
                                    f_w.write(lr + "\n")
                            st.toast("🗑️ Artículo eliminado con éxito.")
                            st.rerun()
                st.write("")
        else: 
            st.info("No hay radares configurados.")
elif menu == "💥 Forzar Escaneo":
    st.title("💥 Forzar Escaneo Automático")
    contenedor_mensaje = st.empty()
    if st.button("💥 INICIAR ESCANEO INTENSIVO", type="primary", use_container_width=True):
        contenedor_mensaje.info("⏳ Buscando ofertas y cargando imágenes...")
        try:
            from scraper import revisar_ofertas
            revisar_ofertas()
            contenedor_mensaje.success("✅ ¡Escaneo completado! Revisa tu Telegram.")
            st.rerun()
        except Exception as e: contenedor_mensaje.error(f"❌ Error: {e}")
