import streamlit as st
import json
import os
import time
import pandas as pd
import requests
import threading
from datetime import datetime, timezone
from supabase import create_client, Client
from scraper import revisar_ofertas

# Importación para vincular el contexto de Streamlit a hilos secundarios
try:
    from streamlit.runtime.scriptrunner import add_script_run_ctx
except ImportError:
    from streamlit.scriptrunner import add_script_run_ctx

st.set_page_config(page_title="COBY EL CAZADOR", layout="wide")

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# ⚡ Optimización de caché (TTL = 5 min)
@st.cache_data(ttl=300)
def obtener_tiendas_dinamicas():
    tiendas_base = ["ADIDAS", "FALABELLA", "MARATHON", "RIPLEY", "PUMA", "NIKE", "TRIATHLON", "JBL", "SAMSUNG", "PLAZA_VEA", "TOTTUS", "METRO", "PLATANITOS", "FOOTLOOSE", "ESTILOS", "NATURA", "HM"]
    try:
        res = supabase.table("radares").select("identificador").execute()
        if res.data:
            for item in res.data:
                ident = item.get("identificador", "")
                parts = ident.split("-")
                if parts and parts[0]:
                    tnd = parts[0].upper().strip()
                    if tnd and tnd not in tiendas_base:
                        tiendas_base.append(tnd)
    except Exception:
        pass
    return sorted(tiendas_base)

st.sidebar.markdown("## 🧠 COBY & GEMINI")
st.sidebar.caption("🚀 _Central de Ofertas Automatizada_")
st.sidebar.write("---")

menu = st.sidebar.radio("Sección:", ["📈 Ver Dashboard / Ofertas", "🛠️ Configurar Radares y URLs", "💥 Forzar Escaneo Intensivo"])

# Inicialización de Session States
if "mod_id" not in st.session_state: st.session_state.mod_id = None
if "mod_tienda" not in st.session_state: st.session_state.mod_tienda = "ADIDAS"
if "mod_cat" not in st.session_state: st.session_state.mod_cat = "Zapatillas"
if "mod_nombre" not in st.session_state: st.session_state.mod_nombre = ""
if "mod_url" not in st.session_state: st.session_state.mod_url = ""
if "mod_talla" not in st.session_state: st.session_state.mod_talla = "Todas"
if "mod_precio" not in st.session_state: st.session_state.mod_precio = 100
if "filtro_activo" not in st.session_state: st.session_state.filtro_activo = "TODOS"

if "scraper_running" not in st.session_state: st.session_state.scraper_running = False
if "scraper_result" not in st.session_state: st.session_state.scraper_result = None

def botonera_independiente():
    st.write("### 🔍 Filtrar Patrullaje por Categoría:")
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

# ---------------------------
# Dashboard / Ofertas
# ---------------------------
if menu == "📈 Ver Dashboard / Ofertas":
    st.title("🕵️‍♂️ Central de Ofertas Activas")
    with st.sidebar.expander("🧪 Verificar Bot de Telegram"):
        if st.button("🔔 Ejecutar Alerta de Prueba"):
            t_tok = st.secrets.get("TELEGRAM_TOKEN")
            t_cid = st.secrets.get("TELEGRAM_CHAT_ID")
            if not t_tok or not t_cid:
                st.error("Faltan credenciales.")
            else:
                test_body = "<b>🤖 COMPROBACIÓN CENTRAL:</b>\n\nEl Bot de Telegram se ha enlazado exitosamente."
                img_demo = "https://images.unsplash.com/photo-1542291026-7eec264c27ff"
                test_url = f"https://api.telegram.org/bot{t_tok}/sendPhoto"
                try:
                    requests.post(test_url, json={"chat_id": t_cid, "photo": img_demo, "caption": f"{test_body}\n\n👉 <a href='https://google.com.pe'><b>¡ENLACE!</b></a>", "parse_mode": "HTML"}, timeout=10)
                    st.success("¡Mensaje enviado con éxito!")
                except Exception as ex_t:
                    st.error(f"Fallo: {ex_t}")

    botonera_independiente()
    st.write("---")

    lista_dashboard = []
    try:
        f_activo = st.session_state.filtro_activo
        query = supabase.table("historial_precios").select("identificador, precio, precio_regular, imagen_producto, link_producto, fecha").order("fecha", desc=True)

        if f_activo == "PERFUMES": query = query.ilike("identificador", "%PERFUME%")
        elif f_activo == "ZAPATILLAS": query = query.or_("identificador.ilike.%ZAPATILLA%,identificador.ilike.%CALZADO%")
        elif f_activo == "POLOS": query = query.ilike("identificador", "%POLO%")
        elif f_activo == "CASACAS": query = query.or_("identificador.ilike.%CASACA%,identificador.ilike.%POLERA%")
        elif f_activo == "SHORTS": query = query.ilike("identificador", "%SHORT%")
        elif f_activo == "BUZOS": query = query.or_("identificador.ilike.%BUZO%,identificador.ilike.%PANTALON%")
        elif f_activo == "MEDIAS": query = query.ilike("identificador", "%MEDIAS%")
        elif f_activo == "AUDIFONOS": query = query.ilike("identificador", "%AUDIFONO%")
        elif f_activo == "TV": query = query.or_("identificador.ilike.%TV%,identificador.ilike.%SMART%")
        elif f_activo == "PARLANTE": query = query.or_("identificador.ilike.%PARLANTE%,identificador.ilike.%SPEAKER%")
        elif f_activo == "BARRA DE SONIDO": query = query.or_("identificador.ilike.%BARRA%,identificador.ilike.%SOUNDBAR%")
        elif f_activo == "CELULAR": query = query.or_("identificador.ilike.%CELULAR%,identificador.ilike.%PHONE%")
        elif f_activo == "PC": query = query.or_("identificador.ilike.%PC%,identificador.ilike.%LAPTOP%")
        elif f_activo == "REFRIGERADORA": query = query.or_("identificador.ilike.%REFRIGERADORA%,identificador.ilike.%REFRIG%")
        elif f_activo == "LAVADORA": query = query.or_("identificador.ilike.%LAVADORA%,identificador.ilike.%LAVADO%")
        elif f_activo == "ELECTRODOMESTICOS": query = query.ilike("identificador", "%ELECTRO%")
        elif f_activo == "CAMA": query = query.or_("identificador.ilike.%CAMA%,identificador.ilike.%COLCHON%")

        res_h = query.limit(1000).execute()

        if res_h.data:
            proc = set()
            for reg in res_h.data:
                raw_precio = reg.get('precio')
                precio_venta = float(raw_precio) if raw_precio is not None else 0.0
                if precio_venta <= 0: continue

                id_p = str(reg.get("identificador", "")).strip().upper()
                if not id_p or id_p in proc: continue
                proc.add(id_p)

                parts = id_p.split("-")
                tnd_txt = parts[0].upper() if len(parts) > 0 else "GENERAL"

                if len(parts) >= 5: prd_txt = "-".join(parts[4:]).replace("_", " ").title()
                elif len(parts) >= 3: prd_txt = parts[2].replace("_", " ").title()
                else: prd_txt = id_p.replace("_", " ").title()

                raw_regular = reg.get('precio_regular')
                precio_regular = float(raw_regular) if raw_regular is not None else precio_venta
                lista_dashboard.append({
                    "Tienda": tnd_txt,
                    "Nombre del Producto": prd_txt,
                    "Imagen del Producto": reg.get('imagen_producto', ''),
                    "Precio Real": precio_regular,
                    "Precio de Venta": precio_venta,
                    "Descuento": precio_regular - precio_venta,
                    "Link": reg.get('link_producto', '#')
                })
    except Exception as e:
        st.warning(f"Sincronizando: {e}")

    if lista_dashboard:
        df_dash = pd.DataFrame(lista_dashboard).sort_values(by="Descuento", ascending=False)
        st.dataframe(df_dash, column_config={"Tienda": "🏪 Tienda", "Nombre del Producto": "📦 Nombre del Producto", "Imagen del Producto": st.column_config.ImageColumn("🖼️ Vista"), "Precio Real": st.column_config.NumberColumn("💰 Precio Real", format="S/. %.2f"), "Precio de Venta": st.column_config.NumberColumn("🏷️ Precio de Venta", format="S/. %.2f"), "Descuento": st.column_config.NumberColumn("📉 Descuento", format="S/. %.2f"), "Link": st.column_config.LinkColumn("🛒 Enlace", display_text="Ver")}, hide_index=True, use_container_width=True)
    else:
        st.info("No hay ofertas registradas en este rango.")

# ---------------------------
# Panel de Gestión
# ---------------------------
elif menu == "🛠️ Configurar Radares y URLs":
    st.title("🛠️ Panel de Gestión de Enlaces")
    lista_tiendas = obtener_tiendas_dinamicas()
    cats_form = ["Perfumes", "Zapatillas", "Ropa (Medias)", "Ropa (Polos)", "Ropa (Casacas/Poleras)", "Ropa (Shorts)", "Ropa (Buzos)", "Audifonos", "TV", "Parlante", "Barra de sonido", "Celular", "PC / Laptop", "Refrigeradora", "Lavadora", "Electrodomesticos", "Cama", "Otros"]

    with st.container(border=True):
        col_tit, col_canc = st.columns([6, 1])
        with col_tit:
            if st.session_state.mod_id is not None: st.markdown("### ✏️ Modificando Radar")
            else: st.markdown("### 📝 Registrar Nuevo Radar Activo")
        with col_canc:
            if st.session_state.mod_id is not None:
                if st.button("❌ CANCELAR"):
                    st.session_state.mod_id = None
                    st.session_state.mod_tienda = "ADIDAS"
                    st.session_state.mod_cat = "Zapatillas"
                    st.session_state.mod_nombre = ""
                    st.session_state.mod_url = ""
                    st.session_state.mod_talla = "Todas"
                    st.session_state.mod_precio = 100
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
            if cat_man: cat_final = cat_man.replace(" ", "_").upper()
            else:
                cl = cat_menu.lower()
                cat_map = {
                    "medias": "ROPA_MEDIAS", "polos": "ROPA_POLOS", "casacas": "ROPA_CASACAS",
                    "poleras": "ROPA_CASACAS", "shorts": "ROPA_SHORTS", "buzos": "ROPA_BUZOS",
                    "perfume": "PERFUMES", "zapatilla": "ZAPATILLAS", "audifono": "AUDIFONOS",
                    "tv": "TV", "parlante": "PARLANTE", "barra": "BARRA_DE_SONIDO",
                    "celular": "CELULAR", "pc": "PC", "laptop": "PC",
                    "refrigeradora": "REFRIGERADORA", "lavadora": "LAVADORA",
                    "electro": "ELECTRODOMESTICOS", "cama": "CAMA", "colchon": "CAMA"
                }
                cat_final = next((val for key, val in cat_map.items() if key in cl), "OTROS")

            nuevo_id = f"{t_final.replace(' ', '_')}-{cat_final}-{nombre.replace(' ', '_').upper()}-{talla.replace(' ', '_').upper()}"
            try:
                if st.session_state.mod_id is not None:
                    supabase.table("radares").update({"url": url.strip(), "precio_max": precio_max, "identificador": nuevo_id}).eq("id", st.session_state.mod_id).execute()
                else:
                    supabase.table("radares").insert({"url": url.strip(), "precio_max": precio_max, "identificador": nuevo_id}).execute()
                st.session_state.mod_id = None
                st.session_state.mod_nombre, st.session_state.mod_url = "", ""
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")

    st.write("---")

    try:
        res_radares = supabase.table("radares").select("*").order("id", desc=True).execute()
        if res_radares.data:
            radares_por_tienda = {}
            for item in res_radares.data:
                parts = item.get("identificador", "").split("-")
                tienda_nombre = parts[0].upper().strip() if len(parts) > 0 and parts[0] else "OTRAS"
                if tienda_nombre not in radares_por_tienda:
                    radares_por_tienda[tienda_nombre] = []
                radares_por_tienda[tienda_nombre].append((item, parts))

            for tienda_nombre in sorted(radares_por_tienda.keys()):
                items_tienda = radares_por_tienda[tienda_nombre]
                cant_radares = len(items_tienda)

                with st.expander(f"🏪 **{tienda_nombre}** ({cant_radares} radar{'es' if cant_radares > 1 else ''} activo{'s' if cant_radares > 1 else ''})", expanded=False):
                    for index, (item, parts) in enumerate(items_tienda):
                        with st.container(border=True):
                            col_info, col_mod, col_del = st.columns([7.5, 1.25, 1.25])
                            p_tienda = parts[0] if len(parts) > 0 else "OTRAS"
                            p_cat = parts[1].replace('_', ' ') if len(parts) > 1 else "GENERAL"
                            p_tag = parts[2] if len(parts) > 2 else "N/A"
                            p_talla = parts[3] if len(parts) > 3 else "Todas"

                            with col_info:
                                st.markdown(f"**{index + 1}. 🌐 [{p_tienda}]** | #{p_cat} | Etiqueta: `{p_tag}` | **Tope: S/. {item.get('precio_max', 0):.2f}**")
                                st.caption(f"🔗 **URL:** {item.get('url', '')}")
                            with col_mod:
                                if st.button("📝 Modificar", key=f"m_{item['id']}", use_container_width=True):
                                    st.session_state.mod_id = item["id"]
                                    st.session_state.mod_tienda = p_tienda
                                    st.session_state.mod_cat = p_cat.title()
                                    st.session_state.mod_nombre = p_tag
                                    st.session_state.mod_talla = p_talla
                                    st.session_state.mod_url = item.get("url", "")
                                    st.session_state.mod_precio = item.get("precio_max", 100)
                                    st.rerun()
                            with col_del:
                                if st.button("🗑️ Eliminar", key=f"d_{item['id']}", use_container_width=True):
                                    supabase.table("radares").delete().eq("id", item['id']).execute()
                                    st.rerun()
    except Exception as e:
        st.error(f"Error Supabase: {e}")

# ---------------------------
# Forzar Escaneo Intensivo
# ---------------------------
elif menu == "💥 Forzar Escaneo Intensivo":
    st.title("💥 Módulo de Patrullaje Activo")
    botonera_independiente()
    st.write("---")

    start_btn = st.button("🚀 INICIAR BARRIDO QUIRÚRGICO", type="primary", use_container_width=True)

    # 🚀 EJECUCIÓN DIRECTA EN 1 SOLO CLIC
    if start_btn:
        target = st.session_state.get("filtro_activo", "TODOS")
        
        with st.status(f"🕵️‍♂️ Patrullando objetivo: '{target}'...", expanded=True) as status:
            st.write(f"🔎 Iniciando enrutamiento y escaneo de tienda...")
            try:
                # Ejecutar directamente el motor
                result_msg = revisar_ofertas(target)
                st.session_state.scraper_result = {"resumen": result_msg, "target": target, "status": "ok"}
                status.update(label="✅ ¡Patrullaje completado con éxito!", state="complete", expanded=False)
            except Exception as e:
                st.session_state.scraper_result = {"error": str(e), "target": target, "status": "error"}
                status.update(label=f"❌ Error durante el patrullaje: {e}", state="error", expanded=True)

    # 📊 REPORTE DE RESULTADOS DE LA ÚLTIMA EJECUCIÓN
    raw_res = st.session_state.get("scraper_result", None)
    if raw_res:
        st.write("---")
        if raw_res.get("status") == "error":
            st.error(f"❌ **Falló el escaneo:** {raw_res.get('error')}")
        else:
            st.success(f"📋 **Resumen:** {raw_res.get('resumen')}")

    # 📊 TABLA / TARJETAS DE OFERTAS EN VIVO
    st.write("---")
    st.subheader("📊 Reporte de Ofertas Registradas")

    target_escaneado = st.session_state.get("filtro_activo", "TODOS")

    try:
        q = supabase.table("historial_precios").select("identificador, precio, precio_regular, imagen_producto, link_producto, fecha").order("fecha", desc=True)
        if target_escaneado and target_escaneado != "TODOS":
            q = q.ilike("identificador", f"%{target_escaneado}%")
        
        res_recientes = q.limit(60).execute()
        
        if res_recientes.data:
            reporte_items = []
            vistos_ui = set()
            for reg in res_recientes.data:
                p_o = float(reg.get("precio") or 0.0)
                p_r = float(reg.get("precio_regular") or p_o)
                id_p = str(reg.get("identificador", "")).upper()
                
                if not id_p or id_p in vistos_ui or p_o <= 0:
                    continue
                vistos_ui.add(id_p)
                
                parts = id_p.split("-")
                tienda = parts[0] if len(parts) > 0 else "GENERAL"
                nombre_prod = "-".join(parts[2:]).replace("_", " ").title() if len(parts) >= 3 else id_p
                
                reporte_items.append({
                    "Tienda": tienda,
                    "Producto": nombre_prod,
                    "Vista": reg.get("imagen_producto", ""),
                    "Precio Regular": p_r,
                    "Precio Oferta": p_o,
                    "Ahorro": max(0.0, p_r - p_o),
                    "Link": reg.get("link_producto", "#")
                })

            if reporte_items:
                modo_vista = st.radio(
                    "👁️ Selecciona el formato de visualización:",
                    ["🖼️ Tarjetas Grandes (Ampliable al hacer clic)", "📊 Tabla Compacta"],
                    horizontal=True
                )
                st.write("")

                if "Tarjetas" in modo_vista:
                    cols = st.columns(3)
                    for idx, item in enumerate(reporte_items):
                        col = cols[idx % 3]
                        with col:
                            with st.container(border=True):
                                if item["Vista"]:
                                    st.image(item["Vista"], use_container_width=True)
                                else:
                                    st.caption("📷 Sin vista previa")
                                
                                st.markdown(f"**🏪 {item['Tienda']}**")
                                st.markdown(f"**{item['Producto']}**")
                                st.markdown(f"🏷️ **Precio Oferta:** `S/. {item['Precio Oferta']:.2f}`")
                                
                                if item["Ahorro"] > 0:
                                    st.caption(f"~~Antes: S/. {item['Precio Regular']:.2f}~~ | 📉 Ahorro: S/. {item['Ahorro']:.2f}")
                                
                                st.markdown(f"🛒 [**IR A LA OFERTA**]({item['Link']})")
                else:
                    df_reporte = pd.DataFrame(reporte_items).sort_values(by="Ahorro", ascending=False)
                    st.dataframe(
                        df_reporte,
                        column_config={
                            "Tienda": "🏪 Tienda",
                            "Producto": "📦 Producto",
                            "Vista": st.column_config.ImageColumn("🖼️ Foto"),
                            "Precio Regular": st.column_config.NumberColumn("💰 P. Regular", format="S/. %.2f"),
                            "Precio Oferta": st.column_config.NumberColumn("🏷️ P. Oferta", format="S/. %.2f"),
                            "Ahorro": st.column_config.NumberColumn("📉 Ahorro", format="S/. %.2f"),
                            "Link": st.column_config.LinkColumn("🛒 Enlace", display_text="Ver Oferta")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
        else:
            st.info("No hay registros almacenados para esta categoría.")
    except Exception as err_rep:
        st.error(f"Error cargando catálogo: {err_rep}")

    # 📄 AUDITORÍA Y REGISTRO EN DISCO
    debug_path = "ml_debug/combined_debug.json"
    if os.path.exists(debug_path):
        try:
            with open(debug_path, "r", encoding="utf-8") as fh:
                data_debug = json.load(fh)
                
                st.write("---")
                st.subheader("🛠️ Diagnóstico del Patrullaje")
                with st.expander("📄 Ver Registro JSON Guardado", expanded=False):
                    st.json(data_debug)
        except Exception:
            pass
