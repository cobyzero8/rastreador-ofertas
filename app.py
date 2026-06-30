import streamlit as st
import json
import os
import pandas as pd
import requests
from supabase import create_client, Client
from scraper import revisar_ofertas

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
    c1, c2, c3, c4 = st.columns(4)
    with c1: 
        if st.button("🌐 TODOS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "TODOS" else "secondary"): st.session_state.filtro_activo = "TODOS"
    with c2: 
        if st.button("🧪 PERFUMES", use_container_width=True, type="primary" if st.session_state.filtro_activo == "PERFUMES" else "secondary"): st.session_state.filtro_activo = "PERFUMES"
    with c3: 
        if st.button("👟 ZAPATILLAS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "ZAPATILLAS" else "secondary"): st.session_state.filtro_activo = "ZAPATILLAS"
    with c4: 
        if st.button("📦 OTROS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "OTROS" else "secondary"): st.session_state.filtro_activo = "OTROS"
    st.info(f"📍 **Filtro seleccionado actualmente:** `{st.session_state.filtro_activo}`")

if menu == "📈 Ver Dashboard / Ofertas":
    st.title("🕵️‍♂️ Central de Ofertas Activas")
    botonera_independiente()
    st.write("---")
    # ... (resto de tu lógica de dashboard existente)

elif menu == "🛠️ Configurar Radares y URLs":
    st.title("🛠️ Panel de Gestión de Enlaces")
    lista_tiendas = obtener_tiendas_dinamicas()
    cats_form = ["Perfumes", "Zapatillas", "Ropa (Medias)", "Ropa (Polos)", "Ropa (Casacas/Poleras)", "Ropa (Shorts)", "Ropa (Buzos)", "Audifonos", "TV", "Parlante", "Barra de sonido", "Celular", "PC / Laptop", "Refrigeradora", "Lavadora", "Electrodomesticos", "Cama", "Otros"]
    
    with st.container(border=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            if st.session_state.mod_id is not None: st.markdown("### ✏️ Modificando Radar")
            else: st.markdown("### 📝 Registrar Nuevo Radar Activo")
        with col2:
            if st.session_state.mod_id is not None:
                if st.button("❌ Cancelar"):
                    st.session_state.mod_id = None
                    st.rerun()

        c1, c2, c3 = st.columns(3)
        with c1:
            tienda_sel = st.selectbox("Tienda Sugerida", lista_tiendas, index=lista_tiendas.index(st.session_state.mod_tienda) if st.session_state.mod_tienda in lista_tiendas else 0)
            tienda_man = st.text_input("✍️ O Nueva Tienda", "").strip().upper()
            t_final = tienda_man if tienda_man else tienda_sel
            cat_menu = st.selectbox("Categoría Sugerida", cats_form, index=cats_form.index(st.session_state.mod_cat) if st.session_state.mod_cat in cats_form else 0)
            cat_man = st.text_input("✍️ O Nueva Categoría", "").strip().upper()
        with c2:
            nombre = st.text_input("Nombre descriptivo", value=st.session_state.mod_nombre)
            url = st.text_input("URL completa", value=st.session_state.mod_url)
        with c3:
            talla = st.text_input("Talla / Detalle", value=st.session_state.mod_talla)
            precio_max = st.number_input("Precio máximo (S/.)", value=int(st.session_state.mod_precio), min_value=1)
        
        if st.button("💾 GUARDAR CAMBIOS EN LA NUBE", type="primary", use_container_width=True):
            cat_final = cat_man.replace(" ", "_").upper() if cat_man else cat_menu.replace(" ", "_").upper()
            nuevo_id = f"{t_final.replace(' ', '_')}-{cat_final}-{nombre.replace(' ', '_').upper()}-{talla.replace(' ', '_').upper()}"
            try:
                if st.session_state.mod_id is not None: 
                    supabase.table("radares").update({"url": url.strip(), "precio_max": precio_max, "identificador": nuevo_id}).eq("id", st.session_state.mod_id).execute()
                else: 
                    supabase.table("radares").insert({"url": url.strip(), "precio_max": precio_max, "identificador": nuevo_id}).execute()
                st.session_state.mod_id = None
                st.rerun()
            except Exception as e: st.error(f"Error: {e}")

    st.write("---")
    res_radares = supabase.table("radares").select("*").order("id", desc=True).execute()
    if res_radares.data:
        for item in res_radares.data:
            parts = item["identificador"].split("-")
            with st.container(border=True):
                c_info, c_mod, c_del = st.columns([7.5, 1.25, 1.25])
                with c_info:
                    st.markdown(f"**🌐 {parts[0]}** | #{parts[1]} | **{parts[2]}**")
                with c_mod:
                    if st.button("📝 Modificar", key=f"m_{item['id']}"):
                        st.session_state.mod_id = item["id"]
                        st.session_state.mod_tienda = parts[0]
                        st.session_state.mod_cat = parts[1].replace("_", " ").title()
                        st.session_state.mod_nombre = parts[2]
                        st.session_state.mod_talla = parts[3] if len(parts) > 3 else "Todas"
                        st.session_state.mod_url = item["url"]
                        st.session_state.mod_precio = item["precio_max"]
                        st.rerun()
                with c_del:
                    if st.button("🗑️ Eliminar", key=f"d_{item['id']}"):
                        supabase.table("radares").delete().eq("id", item["id"]).execute()
                        st.rerun()

elif menu == "💥 Forzar Escaneo Intensivo":
    st.title("💥 Módulo de Patrullaje Activo")
    botonera_independiente()
    st.write("---")
    if st.button("🚀 INICIAR BARRIDO QUIRÚRGICO", type="primary", use_container_width=True):
        msg = revisar_ofertas(st.session_state.filtro_activo)
        st.success(f"📊 Resumen: {msg}")
