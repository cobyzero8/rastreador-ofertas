import streamlit as st
import json
import os
import pandas as pd
import requests
from supabase import create_client, Client

st.set_page_config(page_title="COBY & GEMINI - Panel Central", layout="wide")

# CREDENCIALES EXCLUSIVAS DE TU PROYECTO EN LA NUBE
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_publishable_LG-EavkoMBYDSCS0xsCccQ_1062w4zq"

# Inicializar cliente de Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HISTORIAL_FILE = "historial_precios.json"
CUPONES_FILE = "cupones.json"
TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

PRIMERA_NECESIDAD = ["SHAMPOO", "DESODORANTE", "JABON", "PERFUMES", "ALIMENTOS", "ABARROTES", "HOGAR", "SALUD"]

# --- LEER TIENDAS DE LA NUBE DE FORMA DINÁMICA ---
def obtener_tiendas_dinamicas():
    tiendas_base = ["ADIDAS", "FALABELLA", "MARATHON", "RIPLEY", "PUMA", "NIKE", "NATURA", "MIFARMA", "INKAFARMA", "MERCADO_LIBRE", "TRIATHLON", "JBL", "SAMSUNG", "LBEL", "ESIKA", "CYZONE", "PLAZA_VEA", "TOTTUS", "METRO", "LATAM", "SKY"]
    try:
        res = supabase.table("radares").select("identificador").execute()
        if res.data:
            for item in res.data:
                meta = item["identificador"].split("-")
                tnd = meta[0].upper().strip()
                if tnd and tnd not in tiendas_base: 
                    tiendas_base.append(tnd)
    except: pass
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
                        try:
                            supabase.table("radares").delete().eq("identificador", id_radar_borrar).execute()
                        except: pass
                        requests.post(f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/answerCallbackQuery", json={"callback_query_id": callback_id, "text": "🔕 Radar desactivado."})
                        requests.post(f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage", json={"chat_id": CHAT_ID_TELEGRAM, "text": f"✅ Removido con ID `{id_radar_borrar}` desde la Nube Supabase."})
                        st.rerun()
    except: pass

# --- BARRA LATERAL ---
st.sidebar.markdown("## 🧠 COBY & GEMINI")
st.sidebar.caption("🚀 _Central de Inteligencia Familiar v6.0_")
st.sidebar.caption("⚡ Base de Datos: **🛡️ CLOUD BLINDADA**")
st.sidebar.write("---")

if st.sidebar.button("📥 SINCRONIZAR TELEGRAM 📱", use_container_width=True, type="secondary"):
    sincronizar_mensajes_telegram()
    st.sidebar.success("Sincronizado.")

menu = st.sidebar.radio("Selecciona una opción:", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces Pro", "💥 Forzar Escaneo"])

if "mod_url" not in st.session_state: st.session_state.mod_url = ""
if "mod_nombre" not in st.session_state: st.session_state.mod_nombre = ""
if "mod_talla" not in st.session_state: st.session_state.mod_talla = ""
if "mod_precio" not in st.session_state: st.session_state.mod_precio = 100

# --- DASHBOARD ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Central COBY & GEMINI")
    st.subheader("📊 Dashboard de Artículos y Beneficios")
    
    links_mapeados = {}
    try:
        res_l = supabase.table("radares").select("url", "identificador").execute()
        if res_l.data:
            for item in res_l.data: links_mapeados[item["identificador"]] = item["url"]
    except: pass

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
                else: lista_personal.append(item_dict)
            
            tab1, tab2, tab3 = st.tabs(["🛒 Canasta Hogar / Primera Necesidad", "👟 Gustos Personales y Viajes", "🎟️ Cuponera Central Express"])
            
            with tab1:
                if lista_hogar: st.data_editor(pd.DataFrame(lista_hogar).drop(columns=["ID"]), column_config={"Compra": st.column_config.LinkColumn("Ir al Enlace")}, hide_index=True, use_container_width=True)
                else: st.info("No hay artículos esenciales registrados.")
            with tab2:
                if lista_personal: st.data_editor(pd.DataFrame(lista_personal).drop(columns=["ID"]), column_config={"Compra": st.column_config.LinkColumn("Ir al Enlace")}, hide_index=True, use_container_width=True)
                else: st.info("No hay artículos personales registrados.")
            with tab3:
                if os.path.exists(CUPONES_FILE):
                    with open(CUPONES_FILE, "r", encoding="utf-8") as f_cup: cupones_data = json.load(f_cup)
                    lista_cupones_tabla = []
                    for tnda, lista_c in cupones_data.items():
                        for item_c in lista_c:
                            lista_cupones_tabla.append({"Tienda": tnda.upper(), "Código del Cupón": f"✨ {item_c['codigo']} ✨", "Descuento / Impacto": item_c['descuento'], "Condición / Detalle": item_c['detalle'], "Estatus": "✅ ACTIVO"})
                    if lista_cupones_tabla:
                        st.dataframe(pd.DataFrame(lista_cupones_tabla), use_container_width=True, hide_index=True)
                        if st.button("🗑️ Vaciar Historial de Cupones Expirados", type="secondary"):
                            with open(CUPONES_FILE, "w", encoding="utf-8") as f_reset: json.dump({}, f_reset)
                            st.rerun()
                    else: st.info("Aún no se han recolectado cupones.")
        except Exception as e: st.error(f"Error: {e}")
    else: st.info("No hay datos históricos aún.")

# --- GESTIONAR ENLACES PRO ---
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
            
        if st.button("💾 GUARDAR CAMBIOS EN LA NUBE", type="primary", use_container_width=True):
            if nombre and url:
                nombre_limpio = nombre.replace(" ", "_").strip()
                nuevo_id = f"{tienda_final.replace(' ', '_')}-{categoria_final.upper().strip()}-{nombre_limpio}-{talla.strip() if talla.strip() else 'TODAS'}"
                
                # CORRECCIÓN AQUÍ: Try/Except completos con sangría reglamentaria
                try: 
                    supabase.table("radares").delete().eq("identificador", nuevo_id).execute()
                except: 
                    pass
                    
                if st.session_state.mod_url:
                    try: 
                        supabase.table("radares").delete().eq("url", st.session_state.mod_url).execute()
                    except: 
                        pass
                
                # INSERTAR EN LA BASE DE DATOS EN LA NUBE
                try:
                    supabase.table("radares").insert({"url": url, "precio_max": precio_max, "identificador": nuevo_id}).execute()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
                
                st.session_state.mod_url, st.session_state.mod_nombre, st.session_state.mod_talla, st.session_state.mod_precio = "", "", "", 100
                st.toast("✅ ¡Guardado de forma indestructible en la Nube Supabase!")
                st.rerun()

    st.write("---")
    st.subheader("📋 Panel de Control de Radares (Líneas Activas)")
    
    try:
        res_d = supabase.table("radares").select("*").order("id", desc=True).execute()
        lineas = res_d.data if res_d.data else []
    except: lineas = []
    
    if lineas:
        for index, item in enumerate(lineas):
            url_display = item["url"]
            precio_display = item["precio_max"]
            meta_parts = item["identificador"].split("-")
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
                    try:
                        supabase.table("radares").delete().eq("id", item["id"]).execute()
                    except: pass
                    st.rerun()
            st.write("")
    else: st.info("No hay radares activos en la nube.")

elif menu == "💥 Forzar Escaneo":
    st.title("💥 Forzar Escaneo Automático")
    st.caption("🤖 _Sistema operativo de la firma de software COBY & GEMINI_")
    contenedor_mensaje = st.empty()
    if st.button("💥 INICIAR ESCANEO INTENSIVO", type="primary", use_container_width=True):
        contenedor_mensaje.info("⏳ Buscando ofertas y barriendo cuponeras globales...")
        try:
            from scraper import revisar_ofertas
            revisar_ofertas()
            contenedor_mensaje.success("✅ ¡Escaneo completado! Revisa tu Telegram.")
            st.rerun()
        except Exception as e: contenedor_mensaje.error(f"❌ Error: {e}")
