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
st.sidebar.caption("🚀 _Central de Inteligencia Avanzada v9.8_")
st.sidebar.caption("⚡ Sistema: **Protección Anti-Duplicados Activa**")
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
                
                # --- LÍNEA 70 COMPLETAMENTE CORREGIDA, COMPLETADA Y ASEGURADA AQUÍ ---
                precios_reales = [v for k, v in hist.items() if isinstance(v, (int, float))]
                ultimo_precio = precios_reales[-1] if precios_reales else "N/A"
                
                item_dict = {"Tienda": tienda_txt.upper(), "Categoría": cat_txt, "Elemento": prod_txt.replace("_", " "), "Detalle/Talla": talla_txt, "Precio Actual": f"S/. {ultimo_precio}" if ultimo_precio != "N/A" else "N/A", "Compra": link_final}
                
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
        if os.path
