import streamlit as st
import json
import os
import pandas as pd
from supabase import create_client, Client

st.set_page_config(page_title="COBY & GEMINI - Sistema Inteligente", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def obtener_tiendas_dinamicas():
    tiendas_base = ["ADIDAS", "FALABELLA", "MARATHON", "RIPLEY", "PUMA", "NIKE", "MERCADO_LIBRE", "TRIATHLON", "JBL", "SAMSUNG", "PLAZA_VEA", "TOTTUS", "METRO", "PLATANITOS"]
    try:
        res = supabase.table("radares").select("identificador").execute()
        if res.data:
            for item in res.data:
                tnd = item["identificador"].split("-")[0].upper().strip()
                if tnd and tnd not in tiendas_base: tiendas_base.append(tnd)
    except Exception: pass
    return sorted(tiendas_base)

st.sidebar.markdown("## 🧠 COBY & GEMINI")
st.sidebar.caption("🚀 _Central de Ofertas Automatizada_")
st.sidebar.write("---")

menu = st.sidebar.radio("Selecciona una sección:", ["📈 Ver Dashboard / Ofertas", "🛠️ Configurar Radares y URLs", "💥 Forzar Escaneo Intensivo"])

# Inicialización de estados para la modificación
if "mod_id" not in st.session_state: st.session_state.mod_id = None
if "mod_tienda" not in st.session_state: st.session_state.mod_tienda = "ADIDAS"
if "mod_cat" not in st.session_state: st.session_state.mod_cat = "Zapatillas"
if "mod_nombre" not in st.session_state: st.session_state.mod_nombre = ""
if "mod_url" not in st.session_state: st.session_state.mod_url = ""
if "mod_talla" not in st.session_state: st.session_state.mod_talla = "Todas"
if "mod_precio" not in st.session_state: st.session_state.mod_precio = 100

if "categoria_activa" not in st.session_state: st.session_state.categoria_activa = "TODOS"
if "sub_ropa_activa" not in st.session_state: st.session_state.sub_ropa_activa = "TODOS"

def botonera():
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        if st.button("🧪 Perfumes", use_container_width=True, type="primary" if st.session_state.categoria_activa == "PERFUMES" else "secondary"): st.session_state.categoria_activa = "PERFUMES"
    with c2:
        if st.button("👟 Zapatillas", use_container_width=True, type="primary" if st.session_state.categoria_activa == "ZAPATILLAS" else "secondary"): st.session_state.categoria_activa = "ZAPATILLAS"
    with c3:
        if st.button("👕 Ropa", use_container_width=True, type="primary" if st.session_state.categoria_activa == "ROPA" else "secondary"): st.session_state.categoria_activa = "ROPA"
    with c4:
        if st.button("📺 Tecnología", use_container_width=True, type="primary" if st.session_state.categoria_activa == "TECNOLOGIA" else "secondary"): st.session_state.categoria_activa = "TECNOLOGIA"
    with c5:
        if st.button("🌐 Todo", use_container_width=True, type="primary" if st.session_state.categoria_activa == "TODOS" else "secondary"): st.session_state.categoria_activa = "TODOS"

def sub_botonera_ropa():
    st.write("▼ **Filtrar por tipo de prenda:**")
    sub_cols = st.columns(7)
    sub_cats = [("Todo Ropa", "TODOS"), ("🧦 Medias", "MEDIAS"), ("👕 Polos", "POLOS"), ("🧥 Casacas/Poleras", "CASACAS"), ("🩳 Shorts", "SHORTS"), ("👖 Buzos", "BUZOS"), ("🏋️‍♂️ Deportivos", "DEPORTIVOS")]
    for idx, (label, val) in enumerate(sub_cats):
        if sub_cols[idx].button(label, key=f"sub_{menu}_{val}", use_container_width=True, type="primary" if st.session_state.sub_ropa_activa == val else "secondary"):
            st.session_state.sub_ropa_activa = val
            st.rerun()

# ==========================================
# 📈 DASHBOARD INTERACTIVO
# ==========================================
if menu == "📈 Ver Dashboard / Ofertas":
    st.title("🕵️‍♂️ Mi Central de Ofertas Activas")
    botonera()
    
    if st.session_state.categoria_activa == "ROPA":
        sub_botonera_ropa()

    st.markdown(f"📍 Módulo visualizado actualmente: **{st.session_state.categoria_activa}** {f' > **{st.session_state.sub_ropa_activa}**' if st.session_state.categoria_activa == 'ROPA' else ''}")
    st.write("---")

    lista_productos_dashboard = []
    try:
        res_r = supabase.table("radares").select("*").execute()
        mapa_urls, mapa_topes = {}, {}
        if res_r.data:
            for r in res_r.data:
                id_r_upper = str(r["identificador"]).upper().strip()
                mapa_urls[id_r_upper] = r["url"]
                mapa_topes[id_r_upper] = r["precio_max"]

        res_h = supabase.table("historial_precios").select("*").order("id", desc=True).execute()
        if res_h.data:
            productos_processed = set()
            for reg in res_h.data:
                precio_actual = float(reg.get('precio', 0))
                if precio_actual <= 0: continue

                id_prod = str(reg["identificador"]).strip()
                if id_prod.upper() in productos_processed: continue
                productos_processed.add(id_prod.upper())
                
                parts = id_prod.split("-")
                tienda_txt = parts[0].upper() if len(parts) > 0 else "N/A"
                cat_txt = parts[1].upper().strip() if len(parts) > 1 else "OTROS"
                prod_txt = parts[2].replace("_", " ").title() if len(parts) > 2 else "N/A"
                talla_txt = parts[3] if len(parts) > 3 else "Todas"
                
                grupo_sistema = "OTROS"
                if "ZAPATILLA" in cat_txt: grupo_sistema = "ZAPATILLAS"
                elif "PERFUME" in cat_txt: grupo_sistema = "PERFUMES"
                elif "TECNOLOGIA" in cat_txt or "TV" in cat_txt: grupo_sistema = "TECNOLOGIA"
                elif "ROPA" in cat_txt: grupo_sistema = "ROPA"

                if grupo_sistema == "ROPA" and st.session_state.categoria_activa == "ROPA":
                    if st.session_state.sub_ropa_activa != "TODOS" and st.session_state.sub_ropa_activa not in cat_txt:
                        continue

                if st.session_state.categoria_activa == "TODOS" or st.session_state.
