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

                if st.session_state.categoria_activa == "TODOS" or st.session_state.categoria_activa == grupo_sistema:
                    lista_productos_dashboard.append({
                        "Tienda": tienda_txt, "Categoría": cat_txt.replace("ROPA_", ""), "Producto": prod_txt, "Detalle": talla_txt, "Precio Actual": f"S/. {precio_actual:.2f}", "Tu Tope": f"S/. {mapa_topes.get(id_prod.upper(), 0):.2f}", "Enlace": mapa_urls.get(id_prod.upper(), "#")
                    })
    except Exception as e: st.warning(f"Sincronizando: {e}")

    if lista_productos_dashboard: 
        st.data_editor(pd.DataFrame(lista_productos_dashboard), column_config={"Enlace": st.column_config.LinkColumn("🛒 Ir a la Tienda")}, hide_index=True, use_container_width=True)
    else: st.info("No hay ofertas registradas en esta selección.")

# ==========================================
# 🛠️ GESTIÓN DE RADARES (CON ENTRADA MANUAL COMPLETA)
# ==========================================
elif menu == "🛠️ Configurar Radares y URLs":
    st.title("🛠️ Panel de Gestión de Enlaces")
    lista_tiendas = obtener_tiendas_dinamicas()
    categorias_formulario = ["PERFUMES", "ZAPATILLAS", "ROPA (MEDIAS)", "ROPA (POLOS)", "ROPA (CASACAS/POLERAS)", "ROPA (SHORTS)", "ROPA (BUZOS)", "ROPA (DEPORTIVOS)", "TECNOLOGIA", "OTROS"]
    
    with st.container(border=True):
        if st.session_state.mod_id is not None:
            st.markdown("### ✏️ Modificando Radar Activo")
        else:
            st.markdown("### 📝 Registrar Nuevo Radar Activo")
            
        c1, c2, c3 = st.columns(3)
        with c1:
            idx_tnd = lista_tiendas.index(st.session_state.mod_tienda) if st.session_state.mod_tienda in lista_tiendas else 0
            tienda_sel = st.selectbox("Selecciona Tienda Sugerida", lista_tiendas, index=idx_tnd)
            tienda_manual = st.text_input("✍️ O escribe una Nueva Tienda", "").strip().upper()
            tienda_final = tienda_manual if tienda_manual else tienda_sel
            
            idx_cat = categorias_formulario.index(st.session_state.mod_cat) if st.session_state.mod_cat in categorias_formulario else 0
            cat_menu = st.selectbox("Categoría Sugerida", categorias_formulario, index=idx_cat)
            categoria_manual = st.text_input("✍️ O escribe una Nueva Categoría", "").strip().upper()
        with c2:
            nombre = st.text_input("Nombre descriptivo (ej: Casaca_Corta_Viento)", value=st.session_state.mod_nombre)
            url = st.text_input("URL completa de la Tienda", value=st.session_state.mod_url)
        with c3:
            talla = st.text_input("Talla / Volumen / Detalle", value=st.session_state.mod_talla)
            precio_max = st.number_input("Precio máximo (S/.)", value=int(st.session_state.mod_precio), min_value=1)
        
        c_btn1, c_btn2 = st.columns([8, 2])
        with c_btn1:
            texto_boton = "💾 GUARDAR CAMBIOS EN LA NUBE" if st.session_state.mod_id is not None else "💾 GUARDAR NUEVO RADAR EN LA NUBE"
            if st.button(texto_boton, type="primary", use_container_width=True):
                if categoria_manual:
                    cat_final = categoria_manual.replace(" ", "_")
                else:
                    mapa_ids = {
                        "Perfumes": "PERFUMES", "Zapatillas": "ZAPATILLAS", "Tecnologia": "TECNOLOGIA", "Otros": "OTROS",
                        "Ropa (Medias)": "ROPA_MEDIAS", "Ropa (Polos)": "ROPA_POLOS", "Ropa (Casacas/Poleras)": "ROPA_CASACAS",
                        "Ropa (Shorts)": "ROPA_SHORTS", "Ropa (Buzos)": "ROPA_BUZOS", "Ropa (Deportivos)": "ROPA_DEPORTIVOS"
                    }
                    cat_final = mapa_ids.get(cat_menu, "OTROS")
                
                nuevo_id = f"{tienda_final.replace(' ', '_')}-{cat_final}-{nombre.replace(' ', '_').upper()}-{talla.replace(' ', '_').upper()}"
                
                try:
                    if st.session_state.mod_id is not None:
                        supabase.table("radares").update({"url": url.strip(), "precio_max": precio_max, "identificador": nuevo_id}).eq("id", st.session_state.mod_id).execute()
                        st.toast("✅ ¡Radar modificado con éxito!")
                    else:
                        supabase.table("radares").insert({"url": url.strip(), "precio_max": precio_max, "identificador": nuevo_id}).execute()
                        st.toast("✅ ¡Radar guardado con éxito!")
                    
                    st.session_state.mod_id = None
                    st.session_state.mod_nombre, st.session_state.mod_url, st.session_state.mod_talla = "", "", "Todas"
                    st.session_state.mod_precio = 100
                    st.rerun()
                except Exception as e: st.error(f"Error al procesar: {e}")
                
        with c_btn2:
            if st.session_state.mod_id is not None:
                if st.button("❌ Cancelar", use_container_width=True):
                    st.session_state.mod_id = None
                    st.session_state.mod_nombre, st.session_state.mod_url, st.session_state.mod_talla = "", "", "Todas"
                    st.session_state.mod_precio = 100
                    st.rerun()

    st.write("---")
    st.markdown("### 📋 Registro Actual de la Base de Datos (Radares Activos)")
    
    try:
        res_radares = supabase.table("radares").select("*").order("id", desc=True).execute()
        if res_radares.data:
            for index, item in enumerate(res_radares.data):
                parts = item["identificador"].split("-")
                tienda_p = parts[0].upper()
                cat_p = parts[1].upper()
                nombre_p = parts[2].replace("_", " ").title() if len(parts) > 2 else "N/A"
                talla_p = parts[3].replace("_", " ") if len(parts) > 3 else "Todas"
                
                with st.container(border=True):
                    col_info, col_mod, col_del = st.columns([7.5, 1.25, 1.25])
                    
                    with col_info:
                        st.markdown(f"**{index + 1}. 🌐 [{tienda_p}]** | #{cat_p.replace('ROPA_', 'ROPA ')} | Etiqueta: `{nombre_p}` | Filtro: `{talla_p}` | **Tope: S/. {item['precio_max']:.2f}**")
                        st.caption(f"🔗 **URL Guardada:** [{item['url']}]({item['url']})")
                    
                    with col_mod:
                        st.write("")
                        if st.button(f"📝 Modificar", key=f"mod_btn_{item['id']}", use_container_width=True):
                            st.session_state.mod_id = item["id"]
                            st.session_state.mod_tienda = tienda_p
                            
                            rev_mapa = {
                                "PERFUMES": "Perfumes", "ZAPATILLAS": "Zapatillas", "TECNOLOGIA": "Tecnologia", "OTROS": "Otros",
                                "ROPA_MEDIAS": "Ropa (Medias)", "ROPA_POLOS": "Ropa (Polos)", "ROPA_CASACAS": "Ropa (Casacas/Poleras)",
                                "ROPA_SHORTS": "Ropa (Shorts)", "ROPA_BUZOS": "Ropa (Buzos)", "ROPA_DEPORTIVOS": "Ropa (Deportivos)"
                            }
                            st.session_state.mod_cat = rev_mapa.get(cat_p, "Otros")
                            st.session_state.mod_nombre = parts[2].replace("_", " ") if len(parts) > 2 else ""
                            st.session_state.mod_url = item["url"]
                            st.session_state.mod_talla = talla_p
                            st.session_state.mod_precio = item["precio_max"]
                            st.rerun()
                    
                    with col_del:
                        st.write("")
                        if st.button(f"🗑️ Eliminar", key=f"del_btn_{item['id']}", use_container_width=True, type="secondary"):
                            try:
                                supabase.table("radares").delete().eq("id", item["id"]).execute()
                                st.toast(f"🗑️ Radar {tienda_p} eliminado.")
                                st.rerun()
                            except Exception as err:
                                st.error(f"Error: {err}")
        else:
            st.info("Aún no hay radares registrados en la base de datos.")
    except Exception as e:
        st.error(f"Error al conectar con la lista de radares: {e}")

# ==========================================
# 💥 ESCANEO QUIRÚRGICO
# ==========================================
elif menu == "💥 Forzar Escaneo Intensivo":
    st.title("💥 Módulo de Patrullaje")
    botonera()
    
    if st.session_state.categoria_activa == "ROPA":
        sub_botonera_ropa()
        
    st.write("---")
    if st.button("🚀 INICIAR BARRIDO QUIRÚRGICO", type="primary", use_container_width=True):
        contenedor_mensaje = st.empty()
        sub_info = f" ({st.session_state.sub_ropa_activa})" if st.session_state.categoria_activa == "ROPA" else ""
        contenedor_mensaje.info(f"⏳ Lanzando escuadrón para: **{st.session_state.categoria_activa}**{sub_info}...")
        
        try:
            from scraper import revisar_ofertas
            msg = revisar_ofertas(st.session_state.categoria_activa, st.session_state.sub_ropa_activa)
            contenedor_mensaje.success(f"✅ {msg}")
        except Exception as e:
            contenedor_mensaje.error(f"❌ Error en el motor: {e}")
