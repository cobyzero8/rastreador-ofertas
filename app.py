import streamlit as st
import json
import os
import pandas as pd
import requests

st.set_page_config(page_title="Radar Pro - Panel Central", layout="wide")

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"
CUPONES_FILE = "cupones.json" # NUEVO REGISTRO DE ARTIFACTO
TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

PRIMERA_NECESIDAD = ["SHAMPOO", "DESODORANTE", "JABON", "PERFUMES", "ALIMENTOS", "ABARROTES", "HOGAR", "SALUD"]

def obtener_tiendas_dinamicas():
    tiendas_base = ["ADIDAS", "FALABELLA", "MARATHON", "RIPLEY", "PUMA", "NIKE", "NATURA", "MIFARMA", "INKAFARMA", "MERCADO_LIBRE", "TRIATHLON", "JBL", "SAMSUNG", "LBEL", "ESIKA", "CYZONE", "PLAZA_VEA", "TOTTUS", "METRO", "LATAM", "SKY"]
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            for line in f.readlines():
                p = line.strip().split(",")
                if len(p) >= 3:
                    meta = p[2].split("-")
                    tnd = meta[0].upper().strip()
                    if tnd and tnd not in tiendas_base: tiendas_base.append(tnd)
    return sorted(tiendas_base)

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
    except: pass

st.sidebar.markdown("### 🛠️ Radar Familiar Pro")
st.sidebar.caption("🚀 Diseñado por **[Tu Nombre] & Gemini Pro**")
st.sidebar.caption("⚡ _Estatus: Grandes Genios de la Automatización_")
st.sidebar.write("---")

if st.sidebar.button("📥 SINCRONIZAR TELEGRAM 📱", use_container_width=True, type="secondary"):
    sincronizar_mensajes_telegram()
    st.sidebar.success("Sincronizado.")

menu = st.sidebar.radio("Selecciona una opción:", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces Pro", "💥 Forzar Escaneo"])

if "mod_url" not in st.session_state: st.session_state.mod_url = ""
if "mod_nombre" not in st.session_state: st.session_state.mod_nombre = ""
if "mod_talla" not in st.session_state: st.session_state.mod_talla = ""
if "mod_precio" not in st.session_state: st.session_state.mod_precio = 100

# --- OPCIÓN 1: DASHBOARD CON LA NUEVA PESTAÑA DE CUPONES ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Radar Familiar Pro")
    st.subheader("📊 Dashboard de Artículos y Beneficios")
    
    links_mapeados = {}
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            for line in f.readlines():
                p = line.strip().split(",")
                if len(p) >= 3: links_mapeados[p[2]] = p[0]

    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f: data = json.load(f)
            lista_hogar, lista_personal = [], []
            
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
                
                if cat_txt in PRIMERA_NECESIDAD or cat_txt in ["ALIMENTOS", "ABARROTES", "SHAMPOO", "JABON", "DESODORANTE"]:
                    lista_hogar.append(item_dict)
                else:
                    lista_personal.append(item_dict)
            
            # --- AGREGAMOS LA TERCERA PESTAÑA: CUPONES ---
            tab1, tab2, tab3 = st.tabs(["🛒 Canasta Hogar / Primera Necesidad", "👟 Gustos Personales y Viajes", "🎟️ Cuponera Central Express"])
            
            with tab1:
                if lista_hogar: st.data_editor(pd.DataFrame(lista_hogar).drop(columns=["ID"]), column_config={"Compra": st.column_config.LinkColumn("Ir al Enlace")}, hide_index=True, use_container_width=True)
                else: st.info("No hay artículos esenciales registrados.")
            with tab2:
                if lista_personal: st.data_editor(pd.DataFrame(lista_personal).drop(columns=["ID"]), column_config={"Compra": st.column_config.LinkColumn("Ir al Enlace")}, hide_index=True, use_container_width=True)
                else: st.info("No hay artículos personales registrados.")
            
            # --- CONTROL VISUAL DE LA CUPONERA DEL GRAN GENIO ---
            with tab3:
                st.write("### 🎟️ Códigos de Descuento Vigentes Encontrados")
                if os.path.exists(CUPONES_FILE):
                    with open(CUPONES_FILE, "r", encoding="utf-8") as f_cup:
                        cupones_data = json.load(f_cup)
                    
                    lista_cupones_tabla = []
                    for tnda, lista_c in cupones_data.items():
                        for item_c in lista_c:
                            lista_cupones_tabla.append({
                                "Tienda": tnda.upper(),
                                "Código del Cupón": f"✨ {item_c['codigo']} ✨",
                                "Descuento / Impacto": item_c['descuento'],
                                "Condición / Detalle": item_c['detalle'],
                                "Estatus": "✅ ACTIVO"
                            })
                    
                    if lista_cupones_tabla:
                        st.dataframe(pd.DataFrame(lista_cupones_tabla), use_container_width=True, hide_index=True)
                        st.caption("💡 _Tip: Copia el código en mayúsculas y pégalo en la casilla de checkout de la tienda web._")
                        if st.button("🗑️ Vaciar Historial de Cupones Expirados", type="secondary"):
                            with open(CUPONES_FILE, "w", encoding="utf-8") as f_reset: json.dump({}, f_reset)
                            st.toast("🗑️ Cuponera reseteada de forma segura.")
                            st.rerun()
                    else:
                        st.info("Aún no se han recolectado cupones globales en este ciclo. Ejecuta un escaneo intensivo.")
                else:
                    st.info("Archivo de cuponera inicializado. Listo para el rastreo.")

            st.write("---")
            st.write("### 📈 Evolución Temporal de Precios")
            todos_productos = [i["Elemento"] for i in lista_hogar] + [i["Elemento"] for i in lista_personal]
            if todos_productos:
                producto_grafica = st.selectbox("📊 Selecciona un producto para ver su gráfica:", list(set(todos_productos)))
                id_seleccionado = ""
                for item in (lista_hogar + lista_personal):
                    if item["Elemento"] == producto_grafica: 
                        id_seleccionado = item["ID"]
                        break
                
                historial_puntos = data.get(id_seleccionado, {})
                if historial_puntos:
                    df_grafica = pd.DataFrame(list(historial_puntos.items()), columns=["Fecha", "Precio (S/.)"]).set_index("Fecha")
                    st.line_chart(df_grafica)
                    
        except Exception as e: st.error(f"Error: {e}")
    else: st.info("No hay datos disponibles.")

# --- OPCIÓN 2: GESTIONAR ENLACES PRO ---
elif menu == "🛠️ Gestionar Enlaces Pro":
    st.title("🛠️ Gestionar Enlaces Pro")
    lista_tiendas = obtener_tiendas_dinamicas()
    
    with st.container(border=True):
        st.write("### 📝 Registrar / Modificar Artículo Clasificado")
        c1, c2, c3 = st.columns(3)
        with c1:
            tienda_sel = st.selectbox("Tienda Seleccionada", lista_tiendas)
            tienda_manual = st.text_input("✍️ O registrar Nueva Tienda", "").strip().upper()
            tienda_final = tienda_manual if tienda_manual else tienda_sel
            
            cat_sugerida = st.selectbox("Categoría Frecuente", ["Zapatillas", "Polos", "Poleras", "Casacas", "Pantalon deportivo", "Perfumes", "Shampoo", "Desodorante", "Jabon", "Abarrotes", "Vuelos", "Otros"])
            cat_manual = st.text_input("✍️ O escribir Nueva Categoría", "").strip()
            categoria_final = cat_manual if cat_manual else cat_sugerida
        with c2:
            nombre = st.text_input("Nombre del Artículo", value=st.session_state.mod_nombre)
            url = st.text_input("URL exacta del producto", value=st.session_state.mod_url)
        with c3:
            talla = st.text_input("Talla / Volumen / Fecha", value=st.session_state.mod_talla)
            precio_max = st.number_input("Precio máximo tope (S/.)", value=int(st.session_state.mod_precio), min_value=1)
            
        if st.button("💾 GUARDAR CAMBIOS EN EL RADAR", type="primary", use_container_width=True):
            if nombre and url:
                nombre_limpio = nombre.replace(" ", "_").strip()
                nuevo_id = f"{tienda_final.replace(' ', '_')}-{categoria_final.upper().strip()}-{nombre_limpio}-{talla.strip() if talla.strip() else 'TODAS'}"
                nueva_linea = f"{url},{precio_max},{nuevo_id}"
                
                lineas_actuales = []
                if os.path.exists(URLS_FILE):
                    with open(URLS_FILE, "r", encoding="utf-8") as f:
                        lineas_actuales = [l.strip() for l in f.readlines() if l.strip()]
                
                lineas_actuales = [l for l in lineas_actuales if nuevo_id not in l and (not st.session_state.mod_url or st.session_state.mod_url not in l)]
                lineas_actuales.insert(0, nueva_linea)
                
                with open(URLS_FILE, "w", encoding="utf-8") as f:
                    for la in lineas_actuales: f.write(la + "\n")
                
                st.session_state.mod_url, st.session_state.mod_nombre, st.session_state.mod_talla, st.session_state.mod_precio = "", "", "", 100
                st.toast("✅ ¡Radar guardado en primera fila con éxito!")
                st.rerun()

    st.write("---")
    st.subheader("📋 Panel de Control de Radares")
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f: lineas = [l.strip() for l in f.readlines() if f.readlines() or f.read() or l.strip()]
        # Recarga segura limpia
        with open(URLS_FILE, "r", encoding="utf-8") as f_r: lineas = [l.strip() for l in f_r.readlines() if l.strip()]
        if lineas:
            for index, linea in enumerate(lineas):
                partes = linea.split(",")
                if len(partes) >= 3:
                    url_display = partes[0]
                    precio_display = partes[1]
                    meta_parts = partes[2].split("-")
                    tnd = meta_parts[0]
                    cat = meta_parts[1] if len(meta_parts)>1 else "OTROS"
                    prod = meta_parts[2].replace("_", " ") if len(meta_parts)>2 else "PRODUCTO"
                    tll = meta_parts[3] if len(meta_parts)>3 else "N/A"
                    
                    col_info, col_mod, col_btn = st.columns([7, 1.5, 1.5])
                    with col_info: st.markdown(f"**{index + 1}. [{tnd}]** {prod} | Categoría: `{cat}` | Detalle: `{tll}` | Tope: `S/. {precio_display}`")
                    with col_mod:
                        if st.button(f"✏️ Modificar", key=f"mod_{index}", use_container_width=True):
                            st.session_state.mod_url = url_display
                            st.session_state.mod_nombre = prod.replace(" ", "_")
                            st.session_state.mod_talla = tll
                            st.session_state.mod_precio = precio_display
                            st.rerun()
                    with col_btn:
                        if st.button(f"🗑️ Eliminar", key=f"del_{index}", type="secondary", use_container_width=True):
                            lineas.pop(index)
                            with open(URLS_FILE, "w", encoding="utf-8") as f_w:
                                for lr in lineas: f_w.write(lr + "\n")
                            st.rerun()
                st.write("")
        else: st.info("No hay radares activos.")

elif menu == "💥 Forzar Escaneo":
    st.title("💥 Forzar Escaneo Automático")
    st.caption("🤖 _Sistema de rastreo firmado por los Genios de la Automatización_")
    contenedor_mensaje = st.empty()
    if st.button("💥 INICIAR ESCANEO INTENSIVO", type="primary", use_container_width=True):
        contenedor_mensaje.info("⏳ Buscando ofertas y barriendo cuponeras globales...")
        try:
            from scraper import revisar_ofertas
            revisar_ofertas()
            contenedor_mensaje.success("✅ ¡Escaneo completado! Revisa tu Telegram y la pestaña de Cupones.")
            st.rerun()
        except Exception as e: contenedor_mensaje.error(f"❌ Error: {e}")
