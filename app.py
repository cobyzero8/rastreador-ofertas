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
    # Eliminamos el filtro estricto y dejamos que el código nos diga qué hay realmente
    tiendas_base = ["ADIDAS", "FALABELLA", "MARATHON", "RIPLEY", "PUMA", "NIKE", "MERCADO_LIBRE", "TRIATHLON", "JBL", "SAMSUNG", "PLAZA_VEA", "TOTTUS", "METRO", "PLATANITOS"]
    try:
        # Recuperamos todo sin condiciones
        res = supabase.table("radares").select("identificador").execute()
        if res and res.data:
            for item in res.data:
                # Extraemos la primera parte del identificador sin importar el formato
                parts = item["identificador"].split("-")
                if len(parts) > 0:
                    tnd = parts[0].upper().strip()
                    if tnd not in tiendas_base: 
                        tiendas_base.append(tnd)
    except Exception as e:
        st.error(f"Error técnico al leer base de datos: {e}")
    return sorted(list(set(tiendas_base)))

st.sidebar.markdown("## 🧠 COBY & GEMINI")
st.sidebar.caption("🚀 _Central de Ofertas Automatizada_")
st.sidebar.write("---")

menu = st.sidebar.radio("Selecciona una sección:", ["📈 Ver Dashboard / Ofertas", "🛠️ Configurar Radares y URLs", "💥 Forzar Escaneo Intensivo"])

if "mod_url" not in st.session_state: st.session_state.mod_url = ""
if "mod_nombre" not in st.session_state: st.session_state.mod_nombre = ""
if "mod_talla" not in st.session_state: st.session_state.mod_talla = ""
if "mod_precio" not in st.session_state: st.session_state.mod_precio = 100
if "categoria_activa" not in st.session_state: st.session_state.categoria_activa = "TODOS"

def mostrar_botonera():
    c1, c2, c3, c4, c5 = st.columns(5)
    categorias = [("🧪 Perfumes", "PERFUMES"), ("👟 Zapatillas", "ZAPATILLAS"), ("👕 Ropa", "ROPA"), ("📺 Tecnología", "TECNOLOGIA"), ("🌐 Todo", "TODOS")]
    for i, (label, val) in enumerate(categorias):
        if [c1, c2, c3, c4, c5][i].button(label, use_container_width=True, type="primary" if st.session_state.categoria_activa == val else "secondary"):
            st.session_state.categoria_activa = val
            st.rerun()

# ==========================================
# 📈 DASHBOARD INTERACTIVO
# ==========================================
if menu == "📈 Ver Dashboard / Ofertas":
    st.title("🕵️‍♂️ Mi Central de Ofertas Activas")
    st.write("### 🗂️ Selecciona qué ofertas deseas inspeccionar:")
    mostrar_botonera()
    st.markdown(f"📍 Módulo visualizado actualmente: **{st.session_state.categoria_activa}**")
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
            productos_procesados = set()
            for reg in res_h.data:
                precio_actual = float(reg.get('precio', 0))
                if precio_actual <= 0: continue

                id_prod = str(reg["identificador"]).strip()
                if id_prod.upper() in productos_procesados: continue
                productos_procesados.add(id_prod.upper())
                
                parts = id_prod.split("-")
                tienda_txt = parts[0].upper()
                cat_txt = parts[1].upper().strip()
                prod_txt = parts[2].replace("_", " ").title()
                
                grupo_sistema = "OTROS"
                if "ZAPATILLA" in cat_txt: grupo_sistema = "ZAPATILLAS"
                elif "PERFUME" in cat_txt: grupo_sistema = "PERFUMES"
                elif "TECNOLOGIA" in cat_txt or "TV" in cat_txt: grupo_sistema = "TECNOLOGIA"
                elif "ROPA" in cat_txt: grupo_sistema = "ROPA"

                if st.session_state.categoria_activa == "TODOS" or st.session_state.categoria_activa == grupo_sistema:
                    lista_productos_dashboard.append({"Tienda": tienda_txt, "Producto": prod_txt, "Precio Actual": f"S/. {precio_actual:.2f}", "Enlace": mapa_urls.get(id_prod.upper(), "#")})
    except Exception as e: st.warning(f"Sincronizando: {e}")

    if lista_productos_dashboard: 
        st.data_editor(pd.DataFrame(lista_productos_dashboard), column_config={"Enlace": st.column_config.LinkColumn("🛒 Ir a la Tienda")}, hide_index=True, use_container_width=True)
    else: st.info("No hay ofertas registradas en esta categoría.")

# ==========================================
# 🛠️ GESTIÓN DE RADARES
# ==========================================
elif menu == "🛠️ Configurar Radares y URLs":
    st.title("🛠️ Panel de Gestión de Enlaces")
    lista_tiendas = obtener_tiendas_dinamicas()
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            tienda_sel = st.selectbox("Selecciona Tienda", lista_tiendas)
            categoria_final = st.selectbox("Categoría", ["Zapatillas", "Perfumes", "Ropa", "Tecnologia"])
        with c2:
            nombre = st.text_input("Nombre descriptivo")
            url = st.text_input("URL completa")
        with c3:
            precio_max = st.number_input("Precio máximo (S/.)", value=100)
        
        if st.button("💾 GUARDAR NUEVO RADAR"):
            nuevo_id = f"{tienda_sel}-{categoria_final.upper()}-{nombre.replace(' ', '_').upper()}-TODAS"
            supabase.table("radares").insert({"url": url, "precio_max": precio_max, "identificador": nuevo_id}).execute()
            st.rerun()

# ==========================================
# 💥 ESCANEO QUIRÚRGICO
# ==========================================
elif menu == "💥 Forzar Escaneo Intensivo":
    st.title("💥 Módulo de Patrullaje")
    mostrar_botonera()
    if st.button("🚀 INICIAR BARRIDO", type="primary"):
        from scraper import revisar_ofertas
        msg = revisar_ofertas(st.session_state.categoria_activa)
        st.success(msg)
