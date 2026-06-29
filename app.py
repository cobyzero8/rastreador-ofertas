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

# Inicialización de estado
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
    
    st.write("**Ropa:**")
    r1, r2, r3, r4, r5 = st.columns(5)
    with r1:
        if st.button("👕 POLOS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "POLOS" else "secondary"): st.session_state.filtro_activo = "POLOS"
    with r2:
        if st.button("🧥 CASACAS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "CASACAS" else "secondary"): st.session_state.filtro_activo = "CASACAS"
    with r3:
        if st.button("🩳 SHORTS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "SHORTS" else "secondary"): st.session_state.filtro_activo = "SHORTS"
    with r4:
        if st.button("👖 BUZOS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "BUZOS" else "secondary"): st.session_state.filtro_activo = "BUZOS"
    with r5:
        if st.button("🧦 MEDIAS", use_container_width=True, type="primary" if st.session_state.filtro_activo == "MEDIAS" else "secondary"): st.session_state.filtro_activo = "MEDIAS"

    st.info(f"📍 **Filtro seleccionado actualmente:** `{st.session_state.filtro_activo}`")

if menu == "📈 Ver Dashboard / Ofertas":
    st.title("🕵️‍♂️ Central de Ofertas Activas")
    botonera_independiente()
    st.write("---")
    
    lista_dashboard = []
    try:
        res_h = supabase.table("historial_precios").select("*").order("id", desc=True).execute()
        if res_h.data:
            proc = set()
            for reg in res_h.data:
                raw_precio = reg.get('precio')
                precio_venta = float(raw_precio) if raw_precio is not None else 0.0
                if precio_venta <= 0: continue
                id_p = str(reg["identificador"]).strip()
                if id_p.upper() in proc: continue
                proc.add(id_p.upper())
                parts = id_p.split("-")
                tnd_txt = parts[0].upper()
                cat_txt = parts[1].upper().strip()
                prd_txt = "N/A"
                if len(parts) > 2: prd_txt = parts[2].replace("_", " ").title()
                
                grupo = "OTROS"
                if "ZAPATILLA" in cat_txt: grupo = "ZAPATILLAS"
                elif "PERFUME" in cat_txt: grupo = "PERFUMES"
                elif "POLOS" in cat_txt: grupo = "POLOS"
                elif "CASACAS" in cat_txt: grupo = "CASACAS"
                elif "SHORTS" in cat_txt: grupo = "SHORTS"
                elif "BUZOS" in cat_txt: grupo = "BUZOS"
                elif "MEDIAS" in cat_txt: grupo = "MEDIAS"

                f_activo = st.session_state.filtro_activo
                if f_activo == "TODOS" or f_activo == grupo:
                    raw_regular = reg.get('precio_regular')
                    precio_regular = float(raw_regular) if raw_regular is not None else precio_venta
                    lista_dashboard.append({
                        "Tienda": tnd_txt, "Nombre del Producto": prd_txt, 
                        "Imagen del Producto": reg.get('imagen_producto', ''),
                        "Precio Real": precio_regular, "Precio de Venta": precio_venta, 
                        "Descuento": precio_regular - precio_venta, "Link": reg.get('link_producto', '#')
                    })
    except Exception as e: st.warning(f"Sincronizando: {e}")

    if lista_dashboard: 
        df_dash = pd.DataFrame(lista_dashboard).sort_values(by="Descuento", ascending=False)
        st.dataframe(df_dash, column_config={"Tienda": "🏪 Tienda", "Nombre del Producto": "📦 Nombre del Producto", "Imagen del Producto": st.column_config.ImageColumn("🖼️ Vista"), "Precio Real": st.column_config.NumberColumn("💰 Precio Real", format="S/. %.2f"), "Precio de Venta": st.column_config.NumberColumn("🏷️ Precio de Venta", format="S/. %.2f"), "Descuento": st.column_config.NumberColumn("📉 Descuento", format="S/. %.2f"), "Link": st.column_config.LinkColumn("🛒 Enlace", display_text="Ver")}, hide_index=True, use_container_width=True)

elif menu == "🛠️ Configurar Radares y URLs":
    st.title("🛠️ Panel de Gestión de Enlaces")
    lista_tiendas = obtener_tiendas_dinamicas()
    cats_form = ["Perfumes", "Zapatillas", "Ropa (Medias)", "Ropa (Polos)", "Ropa (Casacas/Poleras)", "Ropa (Shorts)", "Ropa (Buzos)", "Otros"]
    
    with st.container(border=True):
        if st.session_state.mod_id is not None: st.markdown("### ✏️ Modificando Radar")
        else: st.markdown("### 📝 Registrar Nuevo Radar Activo")
        c1, c2, c3 = st.columns(3)
        with c1:
            tienda_sel = st.selectbox("Tienda Sugerida", lista_tiendas, index=lista_tiendas.index(st.session_state.mod_tienda) if st.session_state.mod_tienda in lista_tiendas else 0)
            tienda_man = st.text_input("✍️ O Nueva Tienda", "").strip().upper()
            t_final = tienda_man if tienda_man else tienda_sel
            cat_menu = st.selectbox("Categoría Sugerida", cats_form, index=cats_form.index(st.session_state.mod_cat) if st.session_state.mod_cat in cats_form else 0)
        with c2:
            nombre = st.text_input("Nombre descriptivo", value=st.session_state.mod_nombre)
            url = st.text_input("URL completa", value=st.session_state.mod_url)
        with c3:
            talla = st.text_input("Talla / Detalle", value=st.session_state.mod_talla)
            precio_max = st.number_input("Precio máximo (S/.)", value=int(st.session_state.mod_precio), min_value=1)
        
        # Lógica de Guardado y Cancelar
        col_g, col_c = st.columns([4, 1])
        with col_g:
            if st.button("💾 GUARDAR CAMBIOS EN LA NUBE", type="primary", use_container_width=True):
                cl = cat_menu.lower()
                cat_final = "ROPA_MEDIAS" if "medias" in cl else "ROPA_POLOS" if "polos" in cl else "ROPA_CASACAS" if "casacas" in cl or "poleras" in cl else "ROPA_SHORTS" if "shorts" in cl else "ROPA_BUZOS" if "buzos" in cl else "PERFUMES" if "perfume" in cl else "ZAPATILLAS" if "zapatilla" in cl else "OTROS"
                nuevo_id = f"{t_final.replace(' ', '_')}-{cat_final}-{nombre.replace(' ', '_').upper()}-{talla.replace(' ', '_').upper()}"
                try:
                    if st.session_state.mod_id is not None: 
                        supabase.table("radares").update({"url": url.strip(), "precio_max": precio_max, "identificador": nuevo_id}).eq("id", st.session_state.mod_id).execute()
                    else: 
                        supabase.table("radares").insert({"url": url.strip(), "precio_max": precio_max, "identificador": nuevo_id}).execute()
                    
                    # Limpiar estado
                    st.session_state.mod_id = None
                    st.session_state.mod_nombre, st.session_state.mod_url, st.session_state.mod_talla = "", "", "Todas"
                    st.rerun()
                except Exception as e: st.error(f"Error: {e}")
        
        with col_c:
            if st.session_state.mod_id is not None:
                if st.button("❌ Cancelar", use_container_width=True):
                    st.session_state.mod_id = None
                    st.session_state.mod_nombre, st.session_state.mod_url, st.session_state.mod_talla = "", "", "Todas"
                    st.rerun()

    st.write("---")
    try:
        res_radares = supabase.table("radares").select("*").order("id", desc=True).execute()
        if res_radares.data:
            for index, item in enumerate(res_radares.data):
                parts = item["identificador"].split("-")
                with st.container(border=True):
                    col_info, col_mod, col_del = st.columns([7.5, 1.25, 1.25])
                    with col_info:
                        st.markdown(f"**{index + 1}. 🌐 [{parts[0]}]** | #{parts[1].replace('_', ' ')} | Nombre: `{parts[2] if len(parts)>2 else 'N/A'}` | Talla: `{parts[3] if len(parts)>3 else 'N/A'}` | **Tope: S/. {item['precio_max']:.2f}**")
                        st.caption(f"🔗 **URL:** {item['url']}")
                    with col_mod:
                        if st.button("📝 Modificar", key=f"m_{item['id']}", use_container_width=True):
                            st.session_state.mod_id = item["id"]
                            st.session_state.mod_tienda = parts[0]
                            st.session_state.mod_cat = parts[1].replace('_', ' ')
                            st.session_state.mod_url = item["url"]
                            st.session_state.mod_precio = item["precio_max"]
                            st.session_state.mod_nombre = parts[2] if len(parts)>2 else ""
                            st.session_state.mod_talla = parts[3] if len(parts)>3 else ""
                            st.rerun()
                    with col_del:
                        if st.button("🗑️ Eliminar", key=f"d_{item['id']}", use_container_width=True):
                            supabase.table("radares").delete().eq("id", item["id"]).execute()
                            st.rerun()
    except Exception as e: st.error(f"Error Supabase: {e}")

elif menu == "💥 Forzar Escaneo Intensivo":
    st.title("💥 Módulo de Patrullaje Activo")
    botonera_independiente()
    st.write("---")
    if st.button("🚀 INICIAR BARRIDO QUIRÚRGICO", type="primary", use_container_width=True):
        target = st.session_state.filtro_activo
        msg = revisar_ofertas(target)
        st.success(f"📊 Resumen del patrullaje: {msg}")
