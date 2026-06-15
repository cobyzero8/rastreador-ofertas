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
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HISTORIAL_FILE = "historial_precios.json"
CUPONES_FILE = "cupones.json"

PRIMERA_NECESIDAD = [
    "SHAMPOO", "DESODORANTE", "JABON", "PERFUMES", 
    "ALIMENTOS", "ABARROTES", "HOGAR", "SALUD"
]

def obtener_tiendas_dinamicas():
    tiendas_base = [
        "ADIDAS", "FALABELLA", "MARATHON", "RIPLEY", 
        "PUMA", "NIKE", "NATURA", "MIFARMA", "INKAFARMA", 
        "MERCADO_LIBRE", "TRIATHLON", "JBL", "SAMSUNG", 
        "LBEL", "ESIKA", "CYZONE", "PLAZA_VEA", "TOTTUS", 
        "METRO", "LATAM", "SKY"
    ]
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

# --- BARRA LATERAL ---
st.sidebar.markdown("## 🧠 COBY & GEMINI")
st.sidebar.caption("🚀 _Central de Inteligencia Avanzada v12.1_")
st.sidebar.caption("⚡ Sistema: **Renderizado Forzado Activo**")
st.sidebar.write("---")

menu = st.sidebar.radio(
    "Selecciona una opción:", 
    ["📈 Ver Dashboard", "📊 Inteligencia Comercial", "💰 Métricas de Ahorro", "🛠️ Gestionar Enlaces Pro", "💥 Forzar Escaneo"]
)

if "mod_url" not in st.session_state: st.session_state.mod_url = ""
if "mod_nombre" not in st.session_state: st.session_state.mod_nombre = ""
if "mod_talla" not in st.session_state: st.session_state.mod_talla = ""
if "mod_precio" not in st.session_state: st.session_state.mod_precio = 100

# --- PESTAÑA 1: DASHBOARD ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Central COBY & GEMINI")
    st.subheader("📊 Dashboard de Control Personal")
    
    links_mapeados = {}
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
            
            ultimo_precio = "N/A"
            if precios_reales: ultimo_precio = precios_reales[-1]
            
            txt_precio = "N/A"
            if ultimo_precio != "N/A": txt_precio = f"S/. {ultimo_precio}"
            
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
        if lista_hogar: 
            st.data_editor(pd.DataFrame(lista_hogar), column_config={"Compra": st.column_config.LinkColumn("Ir al Enlace")}, hide_index=True, use_container_width=True)
        else: st.info("No hay artículos esenciales registrados.")
    with tab2:
        if lista_personal: 
            st.data_editor(pd.DataFrame(lista_personal), column_config={"Compra": st.column_config.LinkColumn("Ir al Enlace")}, hide_index=True, use_container_width=True)
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
                if lista_cupones_tabla: st.dataframe(pd.DataFrame(lista_cupones_tabla), use_container_width=True, hide_index=True)
                else: st.info("No hay cupones activos.")
            except: st.info("Cuponera lista.")
        else: st.info("Cuponera lista.")

# --- PESTAÑA 2: INTELIGENCIA COMERCIAL ---
if menu == "📊 Inteligencia Comercial":
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
        except: st.info("📊 Esperando la sincronización de la gráfica con el scraper...")
    else:
        st.info("📊 Recolectando datos de horarios... En los próximos escaneos automáticos aparecerán aquí.")

# --- PESTAÑA 3: MÈTRICAS DE AHORRO ---
if menu == "💰 Métricas de Ahorro":
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

# --- PESTAÑA 4: GESTIONAR ENLACES PRO ---
if menu == "🛠️ Gestionar Enlaces Pro":
    st.title("🛠️ Auditoría y Gestión de Radares Cloud")
    lista_tiendas = obtener_tiendas_dinamicas()
    lineas = []
    
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
                    csv
