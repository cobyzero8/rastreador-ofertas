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
    tiendas_base = ["ADIDAS", "FALABELLA", "MARATHON", "RIPLEY", "PUMA", "NIKE", "MIFARMA", "INKAFARMA", "MERCADO_LIBRE", "TRIATHLON", "JBL", "SAMSUNG", "PLAZA_VEA", "TOTTUS", "METRO", "PLATANITOS"]
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

if "mod_url" not in st.session_state: st.session_state.mod_url = ""
if "mod_nombre" not in st.session_state: st.session_state.mod_nombre = ""
if "mod_talla" not in st.session_state: st.session_state.mod_talla = ""
if "mod_precio" not in st.session_state: st.session_state.mod_precio = 100

# ==========================================
# 📈 DASHBOARD INTERACTIVO
# ==========================================
if menu == "📈 Ver Dashboard / Ofertas":
    st.title("🕵️‍♂️ Mi Central de Ofertas Activas")
    if "categoria_activa" not in st.session_state: st.session_state.categoria_activa = "TODOS"

    st.write("### 🗂️ Selecciona qué ofertas deseas inspeccionar:")
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        if st.button("🌐 Todo Junto", use_container_width=True, type="secondary" if st.session_state.categoria_activa != "TODOS" else "primary"): st.session_state.categoria_activa = "TODOS"
    with c2:
        if st.button("👟 Zapatillas", use_container_width=True, type="secondary" if st.session_state.categoria_activa != "ZAPATILLAS" else "primary"): st.session_state.categoria_activa = "ZAPATILLAS"
    with c3:
        if st.button("🧪 Perfumes", use_container_width=True, type="secondary" if st.session_state.categoria_activa != "PERFUMES" else "primary"): st.session_state.categoria_activa = "PERFUMES"
    with c4:
         if st.button("👕 Ropa", use_container_width=True, type="secondary" if st.session_state.categoria_activa != "ROPA" else "primary"): st.session_state.categoria_activa = "ROPA"
    with c5:
        if st.button("📺 Tecnología", use_container_width=True, type="secondary" if st.session_state.categoria_activa != "TECNOLOGIA" else "primary"): st.session_state.categoria_activa = "TECNOLOGIA"
    
      

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
                id_prod_upper = id_prod.upper()
                if id_prod_upper in productos_procesados: continue
                productos_procesados.add(id_prod_upper)
                
                parts = id_prod.split("-")
                tienda_txt = parts[0].upper() if len(parts) > 0 else "N/A"
                cat_txt = parts[1].upper().strip() if len(parts) > 1 else "OTROS"
                
                prod_txt = parts[2] if len(parts) > 2 else "N/A"
                prod_txt = prod_txt.replace("___", " ").replace("_", " ").strip()
                talla_txt = parts[3] if len(parts) > 3 else "Todas"
                talla_txt = talla_txt.replace("_", " ")
                
                link_final, tope_final = "#", "S/. 500.00"
                for id_radar, url_radar in mapa_urls.items():
                    if tienda_txt in id_radar:
                        link_final = url_radar
                        tope_final = f"S/. {mapa_topes[id_radar]:.2f}"
                        break
                
                # REGLA SEMÁNTICA PARA EL BOTÓN WEB
                grupo_sistema = "OTROS"
                if any(k in cat_txt for k in ["ZAPATILLA", "SNEAKER", "RUNNING", "CALZADO", "ZAPATO"]): grupo_sistema = "ZAPATILLAS"
                elif any(k in cat_txt for k in ["PERFUME", "FRAGANCIA", "COLONIA"]): grupo_sistema = "PERFUMES"
                elif any(k in cat_txt for k in ["TV", "TELEVISOR", "REFRIS", "SAMSUNG", "TECNOLOGIA", "ELECTRONICA", "JBL", "LAPTOP", "CELULAR", "ELECTRO"]): grupo_sistema = "TECNOLOGIA"
                elif any(k in cat_txt for k in ["CASACAS", "POLERAS", "POLOS", "BUZOS", "JEANS", "MEDIAS", "ROPA", "ABRIGO", "PANTALON"]): grupo_sistema = "ROPA"

                if st.session_state.categoria_activa == "TODOS" or st.session_state.categoria_activa == grupo_sistema:
                    lista_productos_dashboard.append({
                        "Tienda": tienda_txt, "Categoría": cat_txt, "Producto": prod_txt.title(), "Detalle": talla_txt, "Precio Actual": f"S/. {precio_actual:.2f}", "Tu Tope Límite": tope_final, "Enlace Compra": link_final
                    })
    except Exception as e: st.warning(f"Sincronizando: {e}")

    if lista_productos_dashboard: 
        st.data_editor(pd.DataFrame(lista_productos_dashboard), column_config={"Enlace Compra": st.column_config.LinkColumn("🛒 Ir a la Tienda")}, hide_index=True, use_container_width=True)
    else: 
        st.info(f"Aún no hay ofertas registradas en el módulo {st.session_state.categoria_activa}.")

# ==========================================
# 🛠️ GESTIÓN DE RADARES
# ==========================================
elif menu == "🛠️ Configurar Radares y URLs":
    st.title("🛠️ Panel de Gestión de Enlaces")
    lista_tiendas = obtener_tiendas_dinamicas()
    
    with st.container(border=True):
        st.write("### 📝 Registrar o Modificar Radar Activo")
        c1, c2, c3 = st.columns(3)
        with c1:
            tienda_sel = st.selectbox("Selecciona Tienda", lista_tiendas)
            tienda_manual = st.text_input("✍️ Nueva Tienda", "").strip().upper()
            tienda_final = tienda_manual if tienda_manual else tienda_sel
            categoria_sel = st.selectbox("Categoría Sugerida", ["ZAPATILLAS", "PERFUMES", "TV", "CASACAS", "POLOS", "OTROS"])
            categoria_manual = st.text_input("✍️ Nueva Categoría", "").strip().upper()
            categoria_final = categoria_manual if categoria_manual else categoria_sel.upper()
        with c2:
            nombre = st.text_input("Nombre descriptivo", value=st.session_state.mod_nombre)
            url = st.text_input("URL completa", value=st.session_state.mod_url)
        with c3:
            talla = st.text_input("Talla / Volumen / Detalle", value=st.session_state.mod_talla)
            precio_max = st.number_input("Precio máximo (S/.)", value=int(st.session_state.mod_precio), min_value=1)
            
        if st.button("💾 GUARDAR NUEVO RADAR EN LA NUBE", type="primary", use_container_width=True):
            if nombre and url:
                nuevo_id = f"{tienda_final.replace(' ', '_')}-{categoria_final.strip()}-{nombre.replace(' ', '_').strip()}-{talla.strip() if talla.strip() else 'Todas'}"
                try:
                    supabase.table("radares").delete().eq("identificador", nuevo_id).execute()
                    if st.session_state.mod_url: supabase.table("radares").delete().eq("url", st.session_state.mod_url).execute()
                except Exception: pass
                supabase.table("radares").insert({"url": url.strip(), "precio_max": precio_max, "identificador": nuevo_id}).execute()
                st.session_state.mod_url, st.session_state.mod_nombre, st.session_state.mod_talla, st.session_state.mod_precio = "", "", "", 100
                st.toast("✅ ¡Radar guardado!")
                st.rerun()

    st.write("---")
    try:
        res_d = supabase.table("radares").select("*").order("id", desc=True).execute()
        lineas = res_d.data if res_d.data else []
    except Exception: lineas = []
    
    if lineas:
        for index, item in enumerate(lineas):
            parts = item["identificador"].split("-")
            col_info, col_mod, col_btn = st.columns([7, 1.5, 1.5])
            with col_info: 
                st.markdown(f"**{index + 1}. 🌐 [{parts[0]}]** | #{parts[1]} | `{parts[2].replace('_',' ')}` | **Tope: S/. {item['precio_max']}**")
                # ---> AQUÍ ESTÁ LA LÍNEA RESTAURADA <---
                st.caption(f"🔗 `URL:` {item['url']}")
            with col_mod:
                if st.button(f"✏️ Editar", key=f"mod_{index}", use_container_width=True):
                    st.session_state.mod_url = item["url"]
                    st.session_state.mod_nombre = parts[2].replace("_"," ")
                    st.session_state.mod_talla = parts[3] if len(parts)>3 else ""
                    st.session_state.mod_precio = item["precio_max"]
                    st.rerun()
            with col_btn:
                if st.button(f"🗑️ Eliminar", key=f"del_{index}", use_container_width=True):
                    supabase.table("radares").delete().eq("id", item["id"]).execute()
                    st.rerun()

# ==========================================
# 💥 ESCANEO QUIRÚRGICO
# ==========================================
elif menu == "💥 Forzar Escaneo Intensivo":
    st.title("💥 Módulo de Patrullaje Quirúrgico")
    st.write("### 🚨 Selecciona qué módulo exacto debe patrullar el robot ahora:")
    
    f1, f2, f3, f4, f5 = st.columns(5)
    categoria_a_lanzar = None
    
    with f1:
        if st.button("🚀 Escanear TODO", use_container_width=True, type="primary"): categoria_a_lanzar = "TODOS"
    with f2:
        if st.button("👟 Solo Zapatillas", use_container_width=True): categoria_a_lanzar = "ZAPATILLAS"
    with f3:
        if st.button("🧪 Solo Perfumes", use_container_width=True): categoria_a_lanzar = "PERFUMES"
    with f4:
        if st.button("👕 Solo Ropa", use_container_width=True): categoria_a_lanzar = "ROPA"
    with f5:
        if st.button("📺 Solo Tecnología", use_container_width=True): categoria_a_lanzar = "TECNOLOGIA"
    
        

    if categoria_a_lanzar is not None:
        contenedor_mensaje = st.empty()
        contenedor_mensaje.info(f"⏳ Lanzando escuadrón a buscar: **{categoria_a_lanzar}**...")
        try:
            from scraper import revisar_ofertas
            resultado_msg = revisar_ofertas(categoria_a_lanzar)
            contenedor_mensaje.success(f"✅ {resultado_msg}")
        except Exception as e:
            contenedor_mensaje.error(f"❌ Error real en el motor: {e}")
