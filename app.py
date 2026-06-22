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
                tienda_txt = parts[0].upper()
                cat_txt = parts[1].upper().strip()
                prod_txt = parts[2].replace("_", " ").title()
                talla_txt = parts[3] if len(parts) > 3 else "Todas"
                
                grupo_sistema = "OTROS"
                if "ZAPATILLA" in cat_txt: grupo_sistema = "ZAPATILLAS"
                elif "PERFUME" in cat_txt: grupo_sistema = "PERFUMES"
                elif "TECNOLOGIA" in cat_txt or "TV" in cat_txt: grupo_sistema = "TECNOLOGIA"
                elif "ROPA" in cat_txt: grupo_sistema = "ROPA"

                if grupo_sistema == "ROPA" and st.session_state.categoria_activa == "ROPA":
                    if st.session_state.sub_ropa_activa != "TODOS" and st.session_state.sub_ropa_activa not in cat_txt:
                        continue

                if st.session_state.categoria_activa == "TODOS" or st.session_state.categoria_activa == grupo_sistema:
                    lista_productos_dashboard.append({
                        "Tienda": tienda_txt, "Categoría": cat_txt.replace("ROPA_", ""), "Producto": prod_txt, "Detalle": talla_txt, "Precio Actual": f"S/. {precio_actual:.2f}", "Tu Tope": f"S/. {mapa_topes.get(id_prod.upper(), 0):.2f}", "Enlace": mapa_urls.get(id_prod.upper(), "#")
                    })
    except Exception as e: st.warning(f"Sincronizando: {e}")

    if lista_productos_dashboard: 
        st.data_editor(pd.DataFrame(lista_productos_dashboard), column_config={"Enlace": st.column_config.LinkColumn("🛒 Ir a la Tienda")}, hide_index=True, use_container_width=True)
    else: st.info("No hay ofertas registradas en esta selección.")

# ==========================================
# 🛠️ GESTIÓN DE RADARES (RECUPERADO Y MEJORADO)
# ==========================================
elif menu == "🛠️ Configurar Radares y URLs":
    st.title("🛠️ Panel de Gestión de Enlaces")
    lista_tiendas = obtener_tiendas_dinamicas()
    
    # Formulario para Guardar
    with st.container(border=True):
        st.subheader("➕ Añadir Nuevo Radar")
        c1, c2, c3 = st.columns(3)
        with c1:
            tienda_sel = st.selectbox("Selecciona Tienda", lista_tiendas)
            cat_menu = st.selectbox("Categoría Principal", ["Perfumes", "Zapatillas", "Ropa (Medias)", "Ropa (Polos)", "Ropa (Casacas/Poleras)", "Ropa (Shorts)", "Ropa (Buzos)", "Ropa (Deportivos)", "Tecnologia"])
        with c2:
            nombre = st.text_input("Nombre descriptivo (ej: Casaca_Corta_Viento)")
            url = st.text_input("URL completa de la Tienda")
        with c3:
            talla = st.text_input("Talla / Detalle", "Todas")
            precio_max = st.number_input("Precio máximo (S/.)", value=100, min_value=1)
        
        if st.button("💾 GUARDAR NUEVO RADAR EN LA NUBE", type="primary", use_container_width=True):
            mapa_ids = {
                "Perfumes": "PERFUMES", "Zapatillas": "ZAPATILLAS", "Tecnologia": "TECNOLOGIA",
                "Ropa (Medias)": "ROPA_MEDIAS", "Ropa (Polos)": "ROPA_POLOS", "Ropa (Casacas/Poleras)": "ROPA_CASACAS",
                "Ropa (Shorts)": "ROPA_SHORTS", "Ropa (Buzos)": "ROPA_BUZOS", "Ropa (Deportivos)": "ROPA_DEPORTIVOS"
            }
            cat_final = mapa_ids[cat_menu]
            nuevo_id = f"{tienda_sel}-{cat_final}-{nombre.replace(' ', '_').upper()}-{talla.replace(' ', '_').upper()}"
            
            try:
                supabase.table("radares").insert({"url": url.
