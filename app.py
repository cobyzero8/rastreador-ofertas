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
st.sidebar.caption("🚀 _Central de Inteligencia Avanzada v12.0_")
st.sidebar.caption("⚡ Sistema: **Protección Absoluta Anti-Cortes**")
st.sidebar.write("---")

menu = st.sidebar.radio(
    "Selecciona una opción:", 
    ["📈 Ver Dashboard", "📊 Inteligencia Comercial", "💰 Métricas de Ahorro", "🛠️ Gestionar Enlaces Pro", "💥 Forzar Escaneo"]
)

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
            for item in res_l.data: 
                links_mapeados[item["identificador"]] = item["url"]
    except: pass

    lista_hogar, lista_personal = [], []
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f_hist:
                data = json.load(f_hist)
        except:
            data = {}

        for id_prod, hist in data.items():
            if id_prod in ["TOTAL_AHORRADO_SISTEMA", "LOG_HORARIOS_OFERTAS"]: continue
            
            parts = id_prod.split("-")
            tot = len(parts)
            if tot < 3: continue
            
            tienda_txt = parts[0]
            cat_txt = parts
