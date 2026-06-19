import streamlit as st
import json
import os
import pandas as pd
import requests
from datetime import datetime
from supabase import create_client, Client

st.set_page_config(page_title="COBY & GEMINI - Sistema Inteligente", layout="wide")

# --- CONFIGURACIÓN DE ÉLITE SEGURA ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

CUPONES_FILE = "cupones.json"
TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

def obtener_tiendas_dinamicas():
    tiendas_base = ["ADIDAS", "FALABELLA", "MARATHON", "RIPLEY", "PUMA", "NIKE", "MIFARMA", "INKAFARMA", "MERCADO_LIBRE", "TRIATHLON", "JBL", "SAMSUNG", "LBEL", "ESIKA", "CYZONE", "PLAZA_VEA", "TOTTUS", "METRO", "LATAM", "SKY", "PLATANITOS"]
    try:
        res = supabase.table("radares").select("identificador").execute()
        if res.data:
            for item in res.data:
                meta = item["identificador"].split("-")
                tnd = meta[0].upper().strip()
                if tnd and tnd not in tiendas_base: tiendas_base.append(tnd)
    except: pass
    return sorted(tiendas_base)

# --- PROCESAR COMANDOS DESDE TELEGRAM ---
def procesar_comandos_telegram_pendientes():
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/getUpdates"
    try:
        resp = requests.get(url, timeout=5).json()
        if resp.get("ok") and resp.get("result"):
            for update in resp["result"]:
                msg = update.get("message", {})
                txt = msg.get("text", "")
                if txt.startswith("/guardar "):
                    parts = txt.replace("/guardar ", "").split(" ")
                    if len(parts) >= 5:
                        r_url = parts[0]
                        r_tnd = parts[1].upper()
                        r_cat = parts[2].upper()
                        r_nom = parts[3].replace(" ", "_")
                        r_top = int(parts[4])
                        r_id = f"{r_tnd}-{r_cat}-{r_nom}-TODAS"
                        supabase.table("radares").insert({"url": r_url, "precio_max": r_top, "identificador": r_id}).execute()
                        requests.post(f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage", json={"chat_id": CHAT_ID_TELEGRAM, "text": f"✅ ¡Radar `{r_nom}` guardado desde Telegram!"})
    except: pass

try: procesar_comandos_telegram_pendientes()
except: pass

# --- BARRA LATERAL SIMPLIFICADA ---
st.sidebar.markdown("## 🧠 COBY & GEMINI")
st.sidebar.caption("🚀 _Central de Ofertas Automatizada_")
st.sidebar.write("---")

menu = st.sidebar.radio("Selecciona una sección:", ["📈 Ver Dashboard / Ofertas", "🛠️ Configurar Radares y URLs", "💥 Forzar Escaneo Intensivo"])

if "mod_url" not in st.session_state: st.session_state.mod_url = ""
if "mod_nombre" not in st.session_state: st.session_state.mod_nombre = ""
if "mod_talla" not in st.session_state: st.session_state.mod_talla = ""
if "mod_precio" not in st.session_state: st.session_state.mod_precio = 100

# ==========================================
# 📈 DASHBOARD DE CONTROL POR BOTONES MULTI-OFERTAS
# ==========================================
if menu == "📈 Ver Dashboard / Ofertas":
    st.title("🕵️‍♂️ Mi Central de Ofertas Activas")
    
    # Inicializar el estado de la categoría seleccionada si no existe
    if "categoria_activa" not in st.session_state:
        st.session_state.categoria_activa = "TODOS"

    # --- FILA DE BOTONES INTEGRADOS ---
    st.write("### 🗂️ Selecciona qué ofertas deseas inspeccionar:")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    
    with c1:
        if st.button("🌐 Todo Junto", use_container_width=True, type="secondary" if st.session_state.categoria_activa != "TODOS" else "primary"):
            st.session_state.categoria_activa = "TODOS"
    with c2:
        if st.button("👟 Zapatillas", use_container_width=True, type="secondary" if st.session_state.categoria_activa != "ZAPATILLAS" else "primary"):
            st.session_state.categoria_activa = "ZAPATILLAS"
    with c3:
        if st.button("🧪 Perfumes", use_container_width=True, type="secondary" if st.session_state.categoria_activa != "PERFUMES" else "primary"):
            st.session_state.categoria_activa = "PERFUMES"
    with c4:
        if st.button("🧼 Cuidado Personal", use_container_width=True, type="secondary" if st.session_state.categoria_activa != "CUIDADO_PERSONAL" else "primary"):
            st.session_state.categoria_activa = "CUIDADO_PERSONAL"
    with c5:
        if st.button("📺 Tecnología", use_container_width=True, type="secondary" if st.session_state.categoria_activa != "TECNOLOGIA" else "primary"):
            st.session_state.categoria_activa = "TECNOLOGIA"
    with c6:
        if st.button("👕 Ropa", use_container_width=True, type="secondary" if st.session_state.categoria_activa != "ROPA" else "primary"):
            st.session_state.categoria_activa = "ROPA"

    st.markdown(f"📍 Módulo visualizado actualmente: **{st.session_state.categoria_activa}**")
    st.write("---")

    lista_productos_dashboard = []
    
    try:
        # 1. Mapear radares para recuperar URLs de compra y topes
        res_r = supabase.table("radares").select("*").execute()
        mapa_urls, mapa_topes = {}, {}
        if res_r.data:
            for r in res_r.data:
                id_r_upper = str(r["identificador"]).upper().strip()
                mapa_urls[id_r_upper] = r["url"]
                mapa_topes[id_r_upper] = r["precio_max"]

        # 2. Obtener el historial de precios
        res_h = supabase.table("historial_precios").select("*").order("id", desc=True).execute()
        
        if res_h.data:
            productos_procesados = set()
            
            for reg in res_h.data:
                id_prod = str(reg["identificador"]).strip()
                id_prod_upper = id_prod.upper()
                
                if id_prod_upper in productos_procesados: 
                    continue
                productos_procesados.add(id_prod_upper)
                
                parts = id_prod.split("-")
                tienda_txt = parts[0].upper() if len(parts) > 0 else "N/A"
                cat_txt = parts[1].upper() if len(parts) > 1 else "OTROS"
                prod_txt = parts[2] if len(parts) > 2 else "N/A"
                talla_txt = parts[3] if len(parts) > 3 else "Todas"
                
                link_final = "#"
                tope_final = "S/. 500.00"
                for id_radar, url_radar in mapa_urls.items():
                    if tienda_txt in id_radar and cat_txt in id_radar:
                        link_final = url_radar
                        tope_final = f"S/. {mapa_topes[id_radar]:.2f}"
                        break
                
                ultimo_precio = f"S/. {float(reg.get('precio', 0)):.2f}"
                nombre_elemento = prod_txt.replace("_", " ").strip().title()
                
                item_dict = {
                    "Tienda": tienda_txt, 
                    "Categoría": cat_txt,
                    "Elemento": nombre_elemento, 
                    "Detalle / Talla": talla_txt.replace("_", " "),
                    "Precio Actual": ultimo_precio, 
                    "Tu Tope Límite": tope_final,
                    "Enlace Compra": link_final
                }

                # --- AGROUPACIÓN INTELIGENTE PARA EL FILTRADO ---
                grupo_sistema = "OTROS"
                if "ZAPATILLA" in cat_txt or "SNEAKER" in cat_txt or "RUNNING" in cat_txt:
                    grupo_sistema = "ZAPATILLAS"
                elif "PERFUME" in cat_txt or "FRAGANCIA" in cat_txt:
                    grupo_sistema = "PERFUMES"
                elif cat_txt in ["SHAMPOO", "JABON", "DESODORANTE", "CUIDADO_PERSONAL", "SALUD"]:
                    grupo_sistema = "CUIDADO_PERSONAL"
                elif cat_txt in ["TV", "TELEVISOR", "REFRIS", "SAMSUNG", "TECNOLOGIA", "ELECTRONICA", "JBL", "EQUIPOS"]:
                    grupo_sistema = "TECNOLOGIA"
                elif cat_txt in ["CASACAS", "POLERAS", "POLOS", "BUZOS", "JEANS", "MEDIAS", "ROPA", "ABRIGO"]:
                    grupo_sistema = "ROPA"

                # Filtrar según el botón presionado
                if st.session_state.categoria_activa == "TODOS" or st.session_state.categoria_activa == grupo_sistema:
                    lista_productos_dashboard.append(item_dict)
                    
    except Exception as e:
        st.warning(f"Sincronizando grilla de ofertas... ({e})")

    if lista_productos_dashboard:
        st.data_editor(pd.DataFrame(lista_productos_dashboard), column_config={"Enlace Compra": st.column_config.LinkColumn("🛒 Ir a la Tienda")}, hide_index=True, use_container_width=True)
    else:
        st.info(f"Aún no hay ofertas registradas en el módulo {st.session_state.categoria_activa}.")

    # --- SECCIÓN DE CUPONES ---
    st.write("---")
    st.subheader("🎟️ Cupones de Descuento Activos")
    if os.path.exists(CUPONES_FILE):
        try:
            with open(CUPONES_FILE, "r", encoding="utf-8") as f_cup: 
                cupones_data = json.load(f_cup)
            lista_cupones_tabla = []
            for tnda, lista_c in cupones_data.items():
                for item_c in lista_c:
                    lista_cupones_tabla.append({"Tienda": tnda.upper(), "Código": f"✨ {item_c['codigo']} ✨", "Descuento": item_c['descuento'], "Detalle": item_c['detalle']})
            if lista_cupones_tabla: 
                st.dataframe(pd.DataFrame(lista_cupones_tabla), use_container_width=True, hide_index=True)
        except: pass

# ==========================================
# 🛠️ SECCIÓN: CONFIGURAR RADARES Y URLS
# ==========================================
elif menu == "🛠️ Configurar Radares y URLs":
    st.title("🛠️ Panel de Gestión de Enlaces y Base de Datos")
    lista_tiendas = obtener_tiendas_dinamicas()
    
    with st.container(border=True):
        st.write("### 📝 Registrar o Modificar Radar Activo")
        c1, c2, c3 = st.columns(3)
        with c1:
            tienda_sel = st.selectbox("Selecciona Tienda", lista_tiendas)
            tienda_manual = st.text_input("✍️ O escribe una Nueva Tienda", "").strip().upper()
            tienda_final = tienda_manual if tienda_manual else tienda_sel
            
            categoria_sel = st.selectbox("Categoría Sugerida", ["Zapatillas", "Perfumes", "Shampoo", "Jabon", "Desodorante", "Tv", "Casacas", "Polos", "Abarrotes", "Otros"])
            categoria_manual = st.text_input("✍️ O escribe una Nueva Categoría (Libre)", "").strip().upper()
            categoria_final = categoria_manual if categoria_manual else categoria_sel.upper()
            
        with c2:
            nombre = st.text_input("Nombre descriptivo del artículo", value=st.session_state.mod_nombre)
            url = st.text_input("URL completa del producto o catálogo", value=st.session_state.mod_url)
        with c3:
            talla = st.text_input("Filtro adicional / Talla / Volumen", value=st.session_state.mod_talla)
            precio_max = st.number_input("Precio máximo de oferta límite (S/.)", value=int(st.session_state.mod_precio), min_value=1)
            
        if st.button("💾 GUARDAR NUEVO RADAR EN LA NUBE", type="primary", use_container_width=True):
            if nombre and url:
                nuevo_id = f"{tienda_final.replace(' ', '_')}-{categoria_final.strip()}-{nombre.replace(' ', '_').strip()}-{talla.strip() if talla.strip() else 'TODAS'}"
                try:
                    supabase.table("radares").delete().eq("identificador", nuevo_id).execute()
                    if st.session_state.mod_url:
                        supabase.table("radares").delete().eq("url", st.session_state.mod_url).execute()
                except: pass
                
                supabase.table("radares").insert({"url": url.strip(), "precio_max": precio_max, "identificador": nuevo_id}).execute()
                st.session_state.mod_url, st.session_state.mod_nombre, st.session_state.mod_talla, st.session_state.mod_precio = "", "", "", 100
                st.toast("✅ ¡Base de datos de radares actualizada!")
                st.rerun()

    st.write("---")
    st.subheader("📋 Lista de Enlaces que estás Vigilando Actualmente")
    try:
        res_d = supabase.table("radares").select("*").order("id", desc=True).execute()
        lineas = res_d.data if res_d.data else []
    except: lineas = []
    
    if lineas:
        for index, item in enumerate(lineas):
            meta_parts = item["identificador"].split("-")
            tnd = meta_parts[0].upper()
            cat = meta_parts[1].upper()
            lbl = meta_parts[2].replace("_", " ")
            tll = meta_parts[3] if len(meta_parts) > 3 else "Todas"
            url_real = item["url"]
            
            col_info, col_mod, col_btn = st.columns([7, 1.5, 1.5])
            with col_info: 
                st.markdown(f"**{index + 1}. 🌐 [{tnd}]** | #{cat} | Producto: `{lbl}` | Detalle: `{tll}` | **Tope: S/. {item['precio_max']}**")
                st.caption(f"🔗 `Dirección:` {url_real}")
            with col_mod:
                if st.button(f"✏️ Editar", key=f"mod_{index}", use_container_width=True):
                    st.session_state.mod_url = url_real
                    st.session_state.mod_nombre = lbl
                    st.session_state.mod_talla = tll
                    st.session_state.mod_precio = item["precio_max"]
                    st.rerun()
            with col_btn:
                if st.button(f"🗑️ Eliminar", key=f"del_{index}", use_container_width=True):
                    supabase.table("radares").delete().eq("id", item["id"]).execute()
                    st.rerun()

# ==========================================
# 💥 SECCIÓN: FORZAR ESCANEO INTENSIVO
# ==========================================
elif menu == "💥 Forzar Escaneo Intensivo":
    st.title("💥 Módulo de Patrullaje Forzado en Tiempo Real")
    st.write("Presiona el botón de abajo para activar los raspadores inmediatamente y forzar el análisis de precios en tus enlaces activos.")
    
    contenedor_mensaje = st.empty()
    if st.button("💥 ENVIAR ROBOT A BUSCAR OFERTAS YA", type="primary", use_container_width=True):
        contenedor_mensaje.info("⏳ Camuflando conexión y escaneando la base de datos de enlaces activos...")
        try:
            from scraper import revisar_ofertas
            revisar_ofertas()
            contenedor_mensaje.success("✅ ¡Operación completada con honores! Los reportes válidos ya fueron enviados a Telegram.")
        except Exception as e: 
            contenedor_mensaje.error(f"❌ Ocurrió una traba en el raspador: {e}")
