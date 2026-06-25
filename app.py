import streamlit as st
import json
import os
import pandas as pd
from supabase import create_client, Client

st.set_page_config(page_title="COBY EL CAZADOR", layout="wide")

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
                if tnd and tnd not in tiendas_base: 
                    tiendas_base.append(tnd)
    except Exception: 
        pass
    return sorted(tiendas_base)

st.sidebar.markdown("## 🧠 COBY & GEMINI")
st.sidebar.caption("🚀 _Central de Ofertas Automatizada_")
st.sidebar.write("---")

menu = st.sidebar.radio("Sección:", ["📈 Ver Dashboard / Ofertas", "🛠️ Configurar Radares y URLs", "💥 Forzar Escaneo Intensivo"])

if "mod_id" not in st.session_state: st.session_state.mod_id = None
if "mod_tienda" not in st.session_state: st.session_state.mod_tienda = "ADIDAS"
if "mod_cat" not in st.session_state: st.session_state.mod_cat = "Zapatillas"
if "mod_nombre" not in st.session_state: st.session_state.mod_nombre = ""
if "mod_url" not in st.session_state: st.session_state.mod_url = ""
if "mod_talla" not in st.session_state: st.session_state.mod_talla = "Todas"
if "mod_precio" not in st.session_state: st.session_state.mod_precio = 100

if "filtro_activo" not in st.session_state: st.session_state.filtro_activo = "TODOS"

def botonera_independiente():
    st.write("### 🔍 Filtrar Patrullaje por Categoría:")
    
    if "filtro_activo" not in st.session_state:
        st.session_state.filtro_activo = "TODOS"
        
    st.write("**Básicos:**")
    c1, c2, c3, c4 = st.columns(4)
    with c1: 
        if st.button("🌐 TODOS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "TODOS" else "secondary"): 
            st.session_state.filtro_activo = "TODOS"
    with c2: 
        if st.button("🧪 PERFUMES", use_container_width=True, type="primary" if st.session_state.filtro_activo == "PERFUMES" else "secondary"): 
            st.session_state.filtro_activo = "PERFUMES"
    with c3: 
        if st.button("👟 ZAPATILLAS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "ZAPATILLAS" else "secondary"): 
            st.session_state.filtro_activo = "ZAPATILLAS"
    with c4: 
        if st.button("📦 OTROS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "OTROS" else "secondary"): 
            st.session_state.filtro_activo = "OTROS"
            
    st.write("**Ropa:**")
    r1, r2, r3, r4, r5 = st.columns(5)
    with r1:
        if st.button("👕 POLOS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "POLOS" else "secondary"): 
            st.session_state.filtro_activo = "POLOS"
    with r2:
        if st.button("🧥 CASACAS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "CASACAS" else "secondary"): 
            st.session_state.filtro_activo = "CASACAS"
    with r3:
        if st.button("🩳 SHORTS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "SHORTS" else "secondary"): 
            st.session_state.filtro_activo = "SHORTS"
    with r4:
        if st.button("👖 BUZOS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "BUZOS" else "secondary"): 
            st.session_state.filtro_activo = "BUZOS"
    with r5:
        if st.button("🧦 MEDIAS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "MEDIAS" else "secondary"): 
            st.session_state.filtro_activo = "MEDIAS"

    st.write("**Audio, Video y Gadgets:**")
    t1, t2, t3, t4, t5 = st.columns(5)
    with t1:
        if st.button("🎧 AUDÍFONOS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "AUDIFONOS" else "secondary"): 
            st.session_state.filtro_activo = "AUDIFONOS"
    with t2:
        if st.button("📺 TV", use_container_width=True, type="primary" if st.session_state.filtro_activo == "TV" else "secondary"): 
            st.session_state.filtro_activo = "TV"
    with t3:
        if st.button("🔊 PARLANTE", use_container_width=True, type="primary" if st.session_state.filtro_activo == "PARLANTE" else "secondary"): 
            st.session_state.filtro_activo = "PARLANTE"
    with t4:
        if st.button("🎵 B. SONIDO", use_container_width=True, type="primary" if st.session_state.filtro_activo == "BARRA DE SONIDO" else "secondary"): 
            st.session_state.filtro_activo = "BARRA DE SONIDO"
    with t5:
        if st.button("📱 CELULAR", use_container_width=True, type="primary" if st.session_state.filtro_activo == "CELULAR" else "secondary"): 
            st.session_state.filtro_activo = "CELULAR"

    st.write("**Hogar y Electrodomésticos:**")
    h1, h2, h3, h4, h5 = st.columns(5)
    with h1:
        if st.button("💻 PC / LAPTOP", use_container_width=True, type="primary" if st.session_state.filtro_activo == "PC" else "secondary"): 
            st.session_state.filtro_activo = "PC"
    with h2:
        if st.button("❄️ REFRIGERADORA", use_container_width=True, type="primary" if st.session_state.filtro_activo == "REFRIGERADORA" else "secondary"): 
            st.session_state.filtro_activo = "REFRIGERADORA"
    with h3:
        if st.button("🧺 LAVADORA", use_container_width=True, type="primary" if st.session_state.filtro_activo == "LAVADORA" else "secondary"): 
            st.session_state.filtro_activo = "LAVADORA"
    with h4:
        if st.button("🔌 ELECTRODOM.", use_container_width=True, type="primary" if st.session_state.filtro_activo == "ELECTRODOMESTICOS" else "secondary"): 
            st.session_state.filtro_activo = "ELECTRODOMESTICOS"
    with h5:
        if st.button("🛏️ CAMA", use_container_width=True, type="primary" if st.session_state.filtro_activo == "CAMA" else "secondary"): 
            st.session_state.filtro_activo = "CAMA"

    st.info(f"📍 **Filtro seleccionado actualmente:** `{st.session_state.filtro_activo}`")

if menu == "📈 Ver Dashboard / Ofertas":
    st.title("🕵️‍♂️ Central de Ofertas Activas")
    botonera_independiente()
    st.write("---")
    st.write(f"📋 Mostrando registros para: **{st.session_state.filtro_activo}**")
    
    lista_dashboard = []
    try:
        res_r = supabase.table("radares").select("*").execute()
        map_urls, map_topes = {}, {}
        if res_r.data:
            for r in res_r.data:
                id_u = str(r["identificador"]).upper().strip()
                map_urls[id_u] = r["url"]
                map_topes[id_u] = r["precio_max"]

        res_h = supabase.table("historial_precios").select("*").order("id", desc=True).execute()
        if res_h.data:
            proc = set()
            for reg in res_h.data:
                precio = float(reg.get('precio', 0))
                if precio <= 0: continue

                id_p = str(reg["identificador"]).strip()
                if id_p.upper() in proc: continue
                proc.add(id_p.upper())
                
                parts = id_p.split("-")
                tnd_txt = parts[0].upper() if len(parts) > 0 else "N/A"
                cat_txt = parts[1].upper().strip() if len(parts) > 1 else "OTROS"
                prd_txt = parts[2].replace("_", " ").title() if len(parts) > 2 else "N/A"
                tll_txt = parts[3] if len(parts) > 3 else "Todas"
                
                grupo = "OTROS"
                if "ZAPATILLA" in cat_txt: grupo = "ZAPATILLAS"
                elif "PERFUME" in cat_txt: grupo = "PERFUMES"
                elif "TECNOLOGIA" in cat_txt or "TV" in cat_txt: grupo = "TECNOLOGIA"
                elif "MEDIAS" in cat_txt: grupo = "MEDIAS"
                elif "POLOS" in cat_txt: grupo = "POLOS"
                elif "CASACAS" in cat_txt: grupo = "CASACAS"
                elif "SHORTS" in cat_txt: grupo = "SHORTS"
                elif "BUZOS" in cat_txt: grupo = "BUZOS"

                f_activo = st.session_state.filtro_activo
                mostrar = False
                if f_activo == "TODOS": mostrar = True
                if f_activo == grupo: mostrar = True
                
                if mostrar:
                    lista_dashboard.append({
                        "Tienda": tnd_txt, "Categoría": cat_txt.replace("ROPA_", ""), "Producto": prd_txt, "Detalle": tll_txt, "Precio Actual": f"S/. {precio:.2f}", "Tu Tope": f"S/. {map_topes.get(id_p.upper(), 0):.2f}", "Enlace": map_urls.get(id_p.upper(), "#")
                    })
    except Exception as e: 
        st.warning(f"Sincronizando: {e}")

    if lista_dashboard: 
        st.data_editor(pd.DataFrame(lista_dashboard), column_config={"Enlace": st.column_config.LinkColumn("🛒 Ir a la Tienda")}, hide_index=True, use_container_width=True)
    else: 
        st.info("No hay ofertas registradas en este rango.")

elif menu == "🛠️ Configurar Radares y URLs":
    st.title("🛠️ Panel de Gestión de Enlaces")
    lista_tiendas = obtener_tiendas_dinamicas()
    
    cats_form = [
        "Perfumes", "Zapatillas", "Ropa (Medias)", "Ropa (Polos)", 
        "Ropa (Casacas/Poleras)", "Ropa (Shorts)", "Ropa (Buzos)", 
        "Audifonos", "TV", "Parlante", "Barra de sonido", "Celular", 
        "PC / Laptop", "Refrigeradora", "Lavadora", "Electrodomesticos", "Cama", "Otros"
    ]
    
    with st.container(border=True):
        if st.session_state.mod_id is not None: st.markdown("### ✏️ Modificando Radar")
        else: st.markdown("### 📝 Registrar Nuevo Radar Activo")
            
        c1, c2, c3 = st.columns(3)
        with c1:
            idx_t = lista_tiendas.index(st.session_state.mod_tienda) if st.session_state.mod_tienda in lista_tiendas else 0
            tienda_sel = st.selectbox("Tienda Sugerida", lista_tiendas, index=idx_t)
            tienda_man = st.text_input("✍️ O Nueva Tienda", "").strip().upper()
            t_final = tienda_man if tienda_man else tienda_sel
            
            idx_c = cats_form.index(st.session_state.mod_cat) if st.session_state.mod_cat in cats_form else 0
            cat_menu = st.selectbox("Categoría Sugerida", cats_form, index=idx_c)
            cat_man = st.text_input("✍️ O Nueva Categoría", "").strip().upper()
        with c2:
            nombre = st.text_input("Nombre descriptivo", value=st.session_state.mod_nombre)
            url = st.text_input("URL completa", value=st.session_state.mod_url)
        with c3:
            talla = st.text_input("Talla / Detalle", value=st.session_state.mod_
