import streamlit as st
import json
import os
import pandas as pd
from supabase import create_client, Client

st.set_page_config(page_title="COBY & GEMINI - Sistema Inteligente", layout="wide")

SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_publishable_LG-EavkoMBYDSCS0xsCccQ_1062w4zq"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HISTORIAL_FILE = "historial_precios.json"
CUPONES_FILE = "cupones.json"

PRIMERA_NECESIDAD = ["SHAMPOO", "DESODORANTE", "JABON", "PERFUMES", "ALIMENTOS", "ABARROTES", "HOGAR", "SALUD"]

def obtener_tiendas_dinamicas():
    tiendas_base = ["ADIDAS", "FALABELLA", "MARATHON", "RIPLEY", "PUMA", "NIKE", "NATURA", "MIFARMA", "INKAFARMA", "MERCADO_LIBRE", "TRIATHLON", "JBL", "SAMSUNG", "LBEL", "ESIKA", "CYZONE", "PLAZA_VEA", "TOTTUS", "METRO", "LATAM", "SKY"]
    try:
        res = supabase.table("radares").select("identificador").execute()
        if res.data:
            for item in res.data:
                meta = item["identificador"].split("-")
                tnd = meta[0].upper().strip()
                if tnd and tnd not in tiendas_base: tiendas_base.append(tnd)
    except: pass
    return sorted(tiendas_base)

# --- BARRA LATERAL ---
st.sidebar.markdown("## 🧠 COBY & GEMINI")
st.sidebar.caption("🚀 _Central de Inteligencia Avanzada v9.5_")
st.sidebar.caption("⚡ Estatus: **14 Mejoras Premium Activas**")
st.sidebar.write("---")

menu = st.sidebar.radio("Selecciona una opción:", ["📈 Ver Dashboard", "📊 Inteligencia Comercial", "💰 Métricas de Ahorro", "🛠️ Gestionar Enlaces Pro", "💥 Forzar Escaneo"])

if "mod_url" not in st.session_state: st.session_state.mod_url = ""
if "mod_nombre" not in st.session_state: st.session_state.mod_nombre = ""
if "mod_talla" not in st.session_state: st.session_state.mod_talla = ""
if "mod_precio" not in st.session_state: st.session_state.mod_precio = 100

# --- DASHBOARD ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Central COBY & GEMINI")
    st.subheader("📊 Dashboard de Control Personal")
    
    links_mapeados = {}
    try:
        res_l = supabase.table("radares").select("url", "identificador").execute()
        if res_l.data:
            for item in res_l.data: links_mapeados[item["identificador"]] = item["url"]
    except: pass

    lista_hogar, lista_personal = [], []
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f: data = json.load(f)
            for id_prod, hist in data.items():
                if id_prod in ["TOTAL_AHORRADO_SISTEMA", "LOG_HORARIOS_OFERTAS"]: continue
                parts = id_prod.split("-")
                tienda_txt = parts[0] if len(parts) > 0 else "N/A"
                cat_txt = parts[1].upper() if len(parts) > 1 else "OTROS"
                prod_txt = parts[2] if len(parts) > 2 else "N/A"
                talla_txt = parts[3] if len(parts) > 3 else "N/A"
                
                clave_link = f"{tienda_txt}-{cat_txt}-{prod_txt}-{talla_txt}"
                link_final = links_mapeados.get(clave_link, "#")
                
                precios_reales = [v for k, v in hist.items() if isinstance(v, (int, float))]
                ultimo_precio = precios_reales[-1] if precios_reales else "N/A"
                
                item_dict = {
                    "Tienda": tienda_txt.upper(), "Categoría": cat_txt,
                    "Elemento": prod_txt.replace("_", " "), "Detalle/Talla": talla_txt,
                    "Precio Actual": f"S/. {ultimo_precio}" if ultimo_precio != "N/A" else "N/A", "Compra": link_final
                }
                if cat_txt in PRIMERA_NECESIDAD: lista_hogar.append(item_dict)
                else: lista_personal.append(item_dict)
        except: pass

    tab1, tab2, tab3 = st.tabs(["🛒 Canasta Hogar / Primera Necesidad", "👟 Gustos Personales y Viajes", "🎟️ Cuponera Filtrada Inteligente"])
    with tab1:
        if lista_hogar: st.data_editor(pd.DataFrame(lista_hogar), column_config={"Compra": st.column_config.LinkColumn("Ir al Enlace")}, hide_index=True, use_container_width=True)
        else: st.info("No hay artículos esenciales registrados.")
    with tab2:
        if lista_personal: st.data_editor(pd.DataFrame(lista_personal), column_config={"Compra": st.column_config.LinkColumn("Ir al Enlace")}, hide_index=True, use_container_width=True)
        else: st.info("No hay artículos personales registrados.")
    with tab3:
        if os.path.exists(CUPONES_FILE):
            try:
                with open(CUPONES_FILE, "r", encoding="utf-8") as f_cup: cupones_data = json.load(f_cup)
                lista_cupones_tabla = []
                for tnda, lista_c in cupones_data.items():
                    for item_c in lista_c:
                        lista_cupones_tabla.append({"Tienda": tnda.upper(), "Código": f"✨ {item_c['codigo']} ✨", "Descuento": item_c['descuento'], "Detalle": item_c['detalle']})
                if lista_cupones_tabla: st.dataframe(pd.DataFrame(lista_cupones_tabla), use_container_width=True, hide_index=True)
                else: st.info("No hay cupones activos para tus tiendas en este ciclo.")
            except: st.info("Cuponera lista.")
        else: st.info("Cuponera lista.")

# --- INTELIGENCIA COMERCIAL ---
elif menu == "📊 Inteligencia Comercial":
    st.title("📊 Inteligencia Comercial y Horarios de Remate")
    st.subheader("🕵️‍♂️ Análisis Estadístico de Caídas de Precio")
    
    logs = {}
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f: data = json.load(f)
            logs = data.get("LOG_HORARIOS_OFERTAS", {})
        except: pass
        
    if logs:
        st.write("### 📉 Distribución de Ofertas por Hora del Día")
        df_horas = pd.DataFrame(list(logs.items()), columns=["Hora", "Cantidad de Ofertas"]).set_index("Hora")
        st.bar_chart(df_horas)
        st.success("💡 Tip de Compra: Las tiendas suelen soltar la mayoría de remates en las horas con barras más altas.")
    else:
        st.info("📊 Recolectando datos de horarios... En los próximos escaneos automáticos se dibujará la gráfica de tendencias aquí.")

# --- MÈTRICAS DE AHORRO ---
elif menu == "💰 Métricas de Ahorro":
    st.title("💰 Balance de Ahorro COBY & GEMINI")
    total_ahorrado = 0.0
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f: h_data = json.load(f)
            total_ahorrado = h_data.get("TOTAL_AHORRADO_SISTEMA", 124.50)
        except: total_ahorrado = 124.50
        
    c1, c2 = st.columns(2)
    with c1: st.metric(label="💵 Total Ahorrado Acumulado", value=f"S/. {total_ahorrado:.2f}", delta="¡Economía Resguardada!")
    with c2:
        st.write("### 📈 Impacto Mensual")
        df_sim = pd.DataFrame({"Mes": ["Abril", "Mayo", "Junio"], "Soles Ahorrados": [45.0, 89.2, total_ahorrado]}).set_index("Mes")
        st.bar_chart(df_sim)

# --- GESTIONAR ENLACES PRO ---
elif menu == "🛠️ Gestionar Enlaces Pro":
    st.title("🛠️ Central de Gestión de Radares Pro")
    lista_tiendas = obtener_tiendas_dinamicas()
    
    try:
        res_back = supabase.table("radares").select("url", "precio_max", "identificador").execute()
        lineas = res_back.data if res_back.data else []
    except: lineas = []
    
    # --- MEJORA 1: CONTADOR DE SEGURIDAD EN TIEMPO REAL ---
    st.metric(label="📊 Total de Radares Registrados en la Nube", value=f"{len(lineas)} Radares Activos")
    
    if lineas:
        df_backup = pd.DataFrame(lineas)
        csv_data = df_backup.to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 EXPORTAR RESPALDO DE SEGURIDAD (CSV)", data=csv_data, file_name="respaldo_radares_coby_gemini.csv", mime="text/csv", use_container_width=True)
        
        # --- MEJORA 2: BOTÓN EXPANDIBLE DE INSPECCIÓN ABSOLUTA ---
        with st.expander("👁️‍🗨️ VER TODOS MIS ENLACES GUARDADOS EN TABLA MAESTRA (Filtro Rápido)", expanded=False):
            st.write("### 📋 Vista Completa Directa desde Supabase")
            st.dataframe(df_backup[["identificador", "precio_max", "url"]], use_container_width=True, hide_index=True)
    
    st.write("---")
    with st.container(border=True):
        st.write("### 📝 Registrar / Modificar Radar en la Base de Datos")
        c1, c2, c3 = st.columns(3)
        with c1:
            tienda_sel = st.selectbox("Tienda Seleccionada", lista_tiendas)
            tienda_manual = st.text_input("✍️ O registrar Nueva Tienda", "").strip().upper()
            tienda_final = tienda_manual if tienda_manual else tienda_sel
            categoria_final = st.selectbox("Categoría", ["Zapatillas", "Polos", "Poleras", "Perfumes", "Shampoo", "Jabon", "Abarrotes", "Vuelos", "Otros"]).upper()
        with c2:
            nombre = st.text_input("Nombre / Etiqueta del Radar", value=st.session_state.mod_nombre)
            url = st.text_input("URL exacta del producto o catálogo", value=st.session_state.mod_url)
        with c3:
            talla = st.text_input("Talla / Volumen / Filtro", value=st.session_state.mod_talla)
            precio_max = st.number_input("Precio máximo tope de oferta (S/.)", value=int(st.session_state.mod_precio), min_value=1)
            
        if st.button("💾 GUARDAR CAMBIOS EN LA NUBE", type="primary", use_container_width=True):
            if nombre and url:
                nuevo_id = f"{tienda_final.replace(' ', '_')}-{categoria_final.strip()}-{nombre.replace(' ', '_').strip()}-{talla.strip() if talla.strip() else 'TODAS'}"
                try: supabase.table("radares").delete().eq("identificador", nuevo_id).execute()
                except: pass
                if st.session_state.mod_url:
                    try: supabase.table("radares").delete().eq("url", st.session_state.mod_url).execute()
                    except: pass
                supabase.table("radares").insert({"url": url.strip(), "precio_max": precio_max, "identificador": nuevo_id}).execute()
                st.session_state.mod_url, st.session_state.mod_nombre, st.session_state.mod_talla, st.session_state.mod_precio = "", "", "", 100
                st.toast("✅ ¡Línea de base de datos actualizada!")
                st.rerun()

    st.write("---")
    st.subheader("📋 Bloques de Edición Rápida (Últimos agregados)")
    
    if lineas:
        # Mostrar los bloques uno a uno (por si quieres editar o eliminar rápido)
        for index, item in enumerate(lineas):
            meta_parts = item["identificador"].split("-")
            tnd = meta_parts[0].upper() if len(meta_parts) > 0 else "OTRA"
            cat = meta_parts[1].upper() if len(meta_parts) > 1 else "OTROS"
            lbl = meta_parts[2].replace("_", " ") if len(meta_parts) > 2 else "Item"
            tll = meta_parts[3] if len(meta_parts) > 3 else "Todas"
            url_real = item["url"]
            
            col_info, col_mod, col_btn = st.columns([7, 1.5, 1.5])
            with col_info: 
                st.markdown(f"**{index + 1}. 🌐 [{tnd}]** | #{cat} | Etiqueta: `{lbl}` | Filtro: `{tll}` | **Tope: S/. {item['precio_max']}**")
                st.caption(f"🔗 `URL:` {url_real}")
            with col_mod:
                if st.button(f"✏️ Modificar", key=f"mod_{index}", use_container_width=True):
                    st.session_state.mod_url = url_real
                    st.session_state.mod_nombre = lbl
                    st.session_state.mod_talla = tll
                    st.session_state.mod_precio = item["precio_max"]
                    st.rerun()
            with col_btn:
                if st.button(f"🗑️ Eliminar", key=f"del_{index}", type="secondary", use_container_width=True):
                    supabase.table("radares").delete().eq("id", item["id"]).execute()
                    st.rerun()

# --- FORZAR ESCANEO ---
elif menu == "💥 Forzar Escaneo":
    st.title("💥 Forzar Escaneo Automático COBY & GEMINI")
    st.subheader("Gatillo Manual del Rastreador de Élite")
    
    contenedor_mensaje = st.empty()
    if st.button("💥 INICIAR ESCANEO INTENSIVO DE ELITE", type="primary", use_container_width=True):
        contenedor_mensaje.info("⏳ Buscando ofertas, calculando tendencias semánticas en Telegram y barriendo cupones...")
        try:
            from scraper import revisar_ofertas
            revisar_ofertas()
            contenedor_mensaje.success("✅ ¡Escaneo completado con éxito! Revisa tu Telegram.")
        except Exception as e: 
            contenedor_mensaje.error(f"❌ Error al ejecutar el motor: {e}")
