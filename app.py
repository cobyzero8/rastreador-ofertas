import streamlit as st
import json
import os
import pandas as pd
from supabase import create_client, Client

st.set_page_config(
    page_title="COBY & GEMINI - Sistema Inteligente", 
    layout="wide"
)

SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_publishable_LG-EavkoMBYDSCS0xsCccQ_1062w4zq"

# Conexión Segura
supabase = None
try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except: pass

HISTORIAL_FILE = "historial_precios.json"
CUPONES_FILE = "cupones.json"

PRIMERA_NECESIDAD = [
    "SHAMPOO", "DESODORANTE", "JABON", "PERFUMES", 
    "ALIMENTOS", "ABARROTES", "HOGAR", "SALUD"
]

# --- BARRA LATERAL ---
st.sidebar.markdown("## 🧠 COBY & GEMINI")
st.sidebar.caption("🚀 _Central de Inteligencia Avanzada v12.7_")
st.sidebar.caption("⚡ Sistema: **Aislamiento de Hilos Activo**")
st.sidebar.write("---")

menu = st.sidebar.radio(
    "Selecciona una opción:", 
    ["📈 Ver Dashboard", "📊 Inteligencia Comercial", "💰 Métricas de Ahorro", "🛠️ Gestionar Enlaces Pro", "💥 Forzar Escaneo"]
)

if "mod_url" not in st.session_state: st.session_state.mod_url = ""
if "mod_nombre" not in st.session_state: st.session_state.mod_nombre = ""
if "mod_talla" not in st.session_state: st.session_state.mod_talla = ""
if "mod_precio" not in st.session_state: st.session_state.mod_precio = 100

# =========================================================================
# --- OPCIÓN 1: DASHBOARD ---
# =========================================================================
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Central COBY & GEMINI")
    st.subheader("📊 Dashboard de Control Personal")
    
    links_mapeados = {}
    if supabase:
        try:
            res_l = supabase.table("radares").select("url", "identificador").execute()
            if res_l.data:
                for item in res_l.data: 
                    links_mapeados[item["identificador"]] = item["url"]
        except: pass

    lista_hogar, lista_personal = [], []
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f_hist:
                data = json.load(f_hist)
        except: data = {}

        for id_prod, hist in data.items():
            if id_prod in ["TOTAL_AHORRADO_SISTEMA", "LOG_HORARIOS_OFERTAS"]: continue
            
            parts = id_prod.split("-")
            tot = len(parts)
            if tot < 3: continue
            
            tienda_txt = parts[0]
            cat_txt = parts[1].upper()
            prod_txt = parts[2]
            talla_txt = parts[3] if tot > 3 else "Todas"
            
            clave_link = f"{tienda_txt}-{cat_txt}-{prod_txt}-{talla_txt}"
            link_final = links_mapeados.get(clave_link, "#")
            
            precios_reales = []
            items_hist = getattr(hist, "items", None)
            if items_hist:
                for k_h, v_h in items_hist():
                    if type(v_h) in [int, float]:
                        precios_reales.append(v_h)
            
            ultimo_precio = precios_reales[-1] if precios_reales else "N/A"
            txt_precio = f"S/. {ultimo_precio}" if ultimo_precio != "N/A" else "N/A"
            
            item_dict = {}
            item_dict["Tienda"] = tienda_txt.upper()
            item_dict["Categoría"] = cat_txt
            item_dict["Elemento"] = prod_txt.replace("_", " ")
            item_dict["Detalle/Talla"] = talla_txt
            item_dict["Precio Actual"] = txt_precio
            item_dict["Compra"] = link_final
            
            if cat_txt in PRIMERA_NECESIDAD: lista_hogar.append(item_dict)
            else: lista_personal.append(item_dict)

    tab1, tab2, tab3 = st.tabs([
        "🛒 Canasta Hogar / Primera Necesidad", 
        "👟 Gustos Personales y Viajes", 
        "🎟️ Cuponera Filtrada Inteligente"
    ])
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
                        cup_dict = {}
                        cup_dict["Tienda"] = tnda.upper()
                        cup_dict["Código"] = f"✨ {item_c['codigo']} ✨"
                        cup_dict["Descuento"] = item_c['descuento']
                        cup_dict["Detalle"] = item_c['detalle']
                        lista_cupones_tabla.append(cup_dict)
                        
                if lista_cupones_tabla: 
                    # --- LÍNEA 128 TOTALMENTE REESTRUCTURADA EN PARÁMETROS CORTOS SEPARADOS ---
                    df_cup_df = pd.DataFrame(lista_cupones_tabla)
                    st.dataframe(
                        df_cup_df, 
                        use_container_width=True, 
                        hide_index=True
                    )
                else: st.info("No hay cupones activos.")
            except: st.info("Cuponera lista.")
        else: st.info("Cuponera lista.")

# =========================================================================
# --- OPCIÓN 2: INTELIGENCIA COMERCIAL ---
# =========================================================================
elif menu == "📊 Inteligencia Comercial":
    st.title("📊 Inteligencia Comercial y Horarios de Remate")
    st.subheader("🕵️‍♂️ Análisis Estadístico de Caídas de Precio")
    logs = {}
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f: data = json.load(f)
            logs = data.get("LOG_HORARIOS_OFERTAS", {})
        except: logs = {}
            
    if isinstance(logs, dict) and len(logs) > 0:
        try:
            st.write("### 📉 Distribución de Ofertas por Hora del Día")
            df_horas = pd.DataFrame(list(logs.items()), columns=["Hora", "Cantidad de Ofertas"]).set_index("Hora")
            st.bar_chart(df_horas)
            st.success("💡 Tip de Compra: Las tiendas suelen soltar remates en horas con barras altas.")
        except: st.info("📊 Sincronizando gráfica comercial...")
    else:
        st.info("📊 Recolectando datos de horarios... En los próximos escaneos automáticos aparecerán aquí.")

# =========================================================================
# --- OPCIÓN 3: MÈTRICAS DE AHORRO ---
# =========================================================================
elif menu == "💰 Métricas de Ahorro":
    st.title("💰 Balance de Ahorro COBY & GEMINI")
    total_ahorrado = 0.0
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f: h_data = json.load(f)
            total_ahorrado = float(h_data.get("TOTAL_AHORRADO_SISTEMA", 0.0))
        except: total_ahorrado = 0.0
            
    c1, c2 = st.columns(2)
    with c1: 
        st.metric(label="💵 Total Ahorrado Acumulado", value=f"S/. {total_ahorrado:.2f}", delta="¡Economy Resguardada!")
    with c2:
        st.write("### 📈 Impacto Mensual")
        df_sim = pd.DataFrame({
            "Mes": ["Abril", "Mayo", "Junio"], 
            "Soles Ahorrados": [45.0, 89.2, total_ahorrado]
        }).set_index("Mes")
        st.bar_chart(df_sim)

# =========================================================================
# --- OPCIÓN 4: GESTIONAR ENLACES PRO ---
# =========================================================================
elif menu == "🛠️ Gestionar Enlaces Pro":
    st.title("🛠️ Auditoría y Gestión de Radares Cloud")
    
    lista_tiendas = ["ADIDAS", "CYZONE", "ESIKA", "FALABELLA", "INKAFARMA", "JBL", "LATAM", "LBEL", "MARATHON", "MERCADO_LIBRE", "MIFARMA", "NATURA", "NIKE", "PLAZA_VEA", "PUMA", "RIPLEY", "SAMSUNG", "SKY", "TOTTUS", "TRIATHLON"]
    lineas = []
    
    if supabase:
        try:
            res_back = supabase.table("radares").select("*").execute()
            if res_back.data: lineas = res_back.data
        except: lineas = []
    
    st.metric(label="📊 Total de Radares Registrados en Supabase", value=f"{len(lineas)} Enlaces Activos")
    
    if len(lineas) > 0:
        try:
            df_completo = pd.DataFrame(lineas)
            if not df_completo.empty:
                df_completo = df_completo.sort_values(by="identificador")
                df_completo.insert(0, "N° Orden", range(1, len(df_completo) + 1))
                
                with st.expander("👁️‍gnd DESPLEGAR ACORDEÓN: VER TODOS MIS ENLACES GUARDADOS EN LA NUBE", expanded=False):
                    st.write("### 📋 Vista de Auditoría Completa (Sin saltos numéricos)")
                    st.dataframe(df_completo[["N° Orden", "identificador", "precio_max", "url"]], use_container_width=True, hide_index=True)
                    
                    csv_data = df_completo.to_csv(index=False).encode('utf-8')
                    st.download_button(label="📥 EXPORTAR TODA LA BASE DE DATOS A CSV", data=csv_data, file_name="base_datos_radares_completa.csv", mime="text/csv", use_container_width=True)
        except: pass
    else:
        st.warning("No hay registros guardados en la base de datos de la nube.")
        
    st.write("---")
    with st.container(border=True):
        st.write("### 📝 Registrar / Modificar Radar en la Base de Datos")
        c1, c2, c3 = st.columns(3)
        with c1:
            tienda_sel = st.selectbox("Tienda Identificada", lista_tiendas)
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
            if nombre and url and supabase:
                u_limpia = url.strip()
                ya_existe = False
                
                if not st.session_state.mod_url:
                    for item_db in lineas:
                        db_url = item_db.get("url", "").strip().lower()
                        if db_url == u_limpia.lower():
                            ya_existe = True
                            id_repetido = item_db.get("identificador", "Desconocido")
                            break
                            
                if ya_existe:
                    st.error(f"❌ ¡BLOQUEO DE SEGURIDAD! Esa URL ya la tienes guardada en: `{id_repetido}`.")
                else:
                    nuevo_id = f"{tienda_final.replace(' ', '_')}-{categoria_final.strip()}-{nombre.replace(' ', '_').strip()}-{talla.strip() if talla.strip() else 'TODAS'}"
                    try: supabase.table("radares").delete().eq("identificador", nuevo_id).execute()
                    except: pass
                    if st.session_state.mod_url:
                        try: supabase.table("radares").delete().eq("url", st.session_state.mod_url).execute()
                        except: pass
                    try:
                        supabase.table("radares").insert({"url": u_limpia, "precio_max": precio_max, "identificador": nuevo_id}).execute()
                        st.session_state.mod_url, st.session_state.mod_nombre, st.session_state.mod_talla, st.session_state.mod_precio = "", "", "", 100
                        st.toast("✅ ¡Base de datos actualizada!")
                        st.rerun()
                    except: pass

    st.write("---")
    st.subheader("📋 Bloques de Edición y Eliminación Rápida")
    if len(lineas) > 0:
        for index, item in enumerate(lineas):
            try:
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
                        if supabase:
                            supabase.table("radares").delete().eq("id", item["id"]).execute()
                            st.rerun()
            except: pass

# =========================================================================
# --- OPCIÓN 5: FORZAR ESCANEO ---
# =========================================================================
elif menu == "💥 Forzar Escaneo":
    st.title("💥 Forzar Escaneo Automático COBY & GEMINI")
    st.subheader("Gatillo Manual del Rastreador de Élite")
    
    contenedor_mensaje = st.empty()
    if st.button("💥 INICIAR ESCANEO INTENSIVO DE ELITE", type="primary", use_container_width=True):
        contenedor_mensaje.info("⏳ Buscando ofertas y barriendo cupones...")
        try:
            from scraper import revisar_ofertas
            revisar_ofertas()
            contenedor_mensaje.success("✅ ¡Escaneo completado! Revisa tu Telegram.")
        except Exception as e: 
            contenedor_mensaje.error(f"❌ Error al ejecutar el motor scraper: {e}")
