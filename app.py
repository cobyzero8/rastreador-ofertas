import test_gemini
import os
import sys
import time
import json
import subprocess
import pandas as pd
import requests
import streamlit as st
from datetime import datetime, timezone
from supabase import create_client, Client

# Importaciones ajustadas a la arquitectura modular
from patrol import revisar_ofertas
from health_monitor import renderizar_dashboard_salud
from scrapers import escanear_tienda

try:
    from streamlit.runtime.scriptrunner import add_script_run_ctx
except ImportError:
    from streamlit.scriptrunner import add_script_run_ctx

st.set_page_config(page_title="COBY EL CAZADOR", layout="wide")

# ---------------------------------------------------------
# Carga de Secretos en Entorno e Inicio del Bot en Streamlit
# ---------------------------------------------------------
for secret_key, value in st.secrets.items():
    if isinstance(value, str) and secret_key not in os.environ:
        os.environ[secret_key] = value

@st.cache_resource
def iniciar_bot_telegram_en_la_nube():
    try:
        # Verificar si ya hay una instancia corriendo para no duplicar procesos
        for proc in subprocess.Popen(["ps", "aux"], stdout=subprocess.PIPE).communicate()[0].decode().split("\n"):
            if "telegram_bot.py" in proc:
                return None

        return subprocess.Popen([sys.executable, "telegram_bot.py"])
    except Exception as e:
        st.error(f"Error iniciando bot de Telegram en segundo plano: {e}")
        return None

# Enciende el bot en la nube de Streamlit (solo se ejecuta 1 vez)
iniciar_bot_telegram_en_la_nube()

# ---------------------------------------------------------

SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

@st.cache_resource
def init_supabase() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

@st.cache_data(ttl=300)
def obtener_tiendas_dinamicas():
    tiendas_base = [
        "GENERAL", "ADIDAS", "FALABELLA", "MARATHON", "RIPLEY", "PUMA", "NIKE", 
        "TRIATHLON", "JBL", "SAMSUNG", "PLAZA_VEA", "TOTTUS", "METRO", 
        "PLATANITOS", "FOOTLOOSE", "ESTILOS", "NATURA", "HM", "EFE", "SHOPSTAR"
    ]
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

menu = st.sidebar.radio("Sección:", [
    "📈 Ver Dashboard / Ofertas", 
    "🎟️ Cupones de Descuento", 
    "🏥 Salud de Scrapers (Health Check)",
    "🛠️ Configurar Radares y URLs", 
    "💥 Forzar Escaneo Intensivo",
    "📊 Métricas visuales de Health Check (Gráficos)",
    "🧪 Validador de Radares (\"Probar URL\")",
    "🔍 Diagnóstico de Bajas de Precio"
])

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
    h1, h2, h3, h4, h5, h6 = st.columns(6)
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
    with h6:
        if st.button("💨 CAMPANA", use_container_width=True, type="primary" if st.session_state.filtro_activo == "CAMPANA EXTRACTORA" else "secondary"):
            st.session_state.filtro_activo = "CAMPANA EXTRACTORA"

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
        query = supabase.table("historial_precios").select("identificador, nombre_producto, precio, precio_regular, imagen_producto, link_producto, fecha").order("fecha", desc=True)

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
        elif f_activo == "CAMPANA EXTRACTORA": query = query.or_("identificador.ilike.%CAMPANA%,identificador.ilike.%EXTRACTORA%")

        res_h = query.limit(1000).execute()

        if res_h.data:
            proc_urls = set()
            for reg in res_h.data:
                raw_precio = reg.get('precio')
                precio_venta = float(raw_precio) if raw_precio is not None else 0.0
                if precio_venta <= 0: continue

                link_p = str(reg.get("link_producto", "")).strip()
                if not link_p or link_p in proc_urls: continue
                proc_urls.add(link_p)

                id_p = str(reg.get("identificador", "")).strip().upper()
                parts = id_p.split("-")
                tnd_txt = parts[0].upper() if len(parts) > 0 else "GENERAL"

                raw_nombre = reg.get("nombre_producto")
                if raw_nombre and str(raw_nombre).strip() and str(raw_nombre).lower() != "none":
                    prd_txt = str(raw_nombre).strip().title()
                elif len(parts) >= 4:
                    prd_txt = "-".join(parts[2:-1]).replace("_", " ").title()
                else:
                    prd_txt = id_p.replace("_", " ").title()

                raw_regular = reg.get('precio_regular')
                precio_regular = float(raw_regular) if raw_regular is not None else precio_venta
                
                lista_dashboard.append({
                    "Tienda": tnd_txt,
                    "Nombre del Producto": prd_txt,
                    "Imagen del Producto": reg.get('imagen_producto', ''),
                    "Precio Real": precio_regular,
                    "Precio de Venta": precio_venta,
                    "Descuento": max(0.0, precio_regular - precio_venta),
                    "Fecha Scan": reg.get('fecha', ''),
                    "Link": link_p
                })
    except Exception as e:
        st.warning(f"Sincronizando: {e}")

    if lista_dashboard:
        df_dash = pd.DataFrame(lista_dashboard)
        st.dataframe(
            df_dash, 
            column_config={
                "Tienda": "🏪 Tienda", 
                "Nombre del Producto": "📦 Nombre del Producto", 
                "Imagen del Producto": st.column_config.ImageColumn("🖼️ Vista"), 
                "Precio Real": st.column_config.NumberColumn("💰 Precio Real", format="S/. %.2f"), 
                "Precio de Venta": st.column_config.NumberColumn("🏷️ Precio de Venta", format="S/. %.2f"), 
                "Descuento": st.column_config.NumberColumn("📉 Descuento", format="S/. %.2f"), 
                "Fecha Scan": "📅 Fecha Scan",
                "Link": st.column_config.LinkColumn("🛒 Enlace", display_text="Ver")
            }, 
            hide_index=True, 
            use_container_width=True
        )
    else:
        st.info("No hay ofertas registradas en este rango.")

# ---------------------------
# Cupones de Descuento
# ---------------------------
elif menu == "🎟️ Cupones de Descuento":
    st.title("🎟️ Cupones y Códigos de Descuento Activos")
    st.caption("⚡ _Central de códigos promocionales recopilados automáticamente de la web y canales de ofertas._")
    st.write("---")

    col_c1, col_c2 = st.columns([3, 1])
    with col_c1:
        st.subheader("📋 Lista de Cupones Vigentes por Tienda")
    with col_c2:
        if st.button("🔍 BUSCAR NUEVOS CUPONES AHORA", type="primary", use_container_width=True):
            with st.spinner("🤖 Escaneando la web en busca de nuevos códigos promocionales..."):
                try:
                    from scrapers_cupones import ejecutar_escaneo_cupones_web
                    ejecutar_escaneo_cupones_web()
                    st.success("¡Escaneo finalizado! Lista de cupones actualizada.")
                    time.sleep(1)
                    st.rerun()
                except Exception as ex_c:
                    st.error(f"Error al ejecutar el rastreador de cupones: {ex_c}")

    st.write("")
    try:
        res_cup = supabase.table("cupones").select("tienda, codigo, descripcion, origen, fecha_registro").eq("activo", True).order("fecha_registro", desc=True).execute()
        if res_cup.data:
            df_cupones = pd.DataFrame(res_cup.data)
            df_cupones_show = df_cupones[["tienda", "codigo", "descripcion", "origen", "fecha_registro"]].copy()
            df_cupones_show.columns = ["Tienda", "Código", "Descripción / Beneficio", "Origen", "Fecha de Registro"]
            
            st.dataframe(
                df_cupones_show,
                column_config={
                    "Tienda": st.column_config.TextColumn("🏪 Tienda"),
                    "Código": st.column_config.TextColumn("🎟️ Código (Copiar y Pegar)"),
                    "Descripción / Beneficio": st.column_config.TextColumn("📝 Descripción / Beneficio"),
                    "Origen": st.column_config.TextColumn("🌐 Origen"),
                    "Fecha de Registro": st.column_config.TextColumn("📅 Fecha Registro")
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("No hay cupones activos registrados por el momento. Presiona 'BUSCAR NUEVOS CUPONES AHORA' para escanear.")
    except Exception as err_c:
        st.error(f"Error cargando cupones desde Supabase: {err_c}")

# ---------------------------
# Panel de Salud (Health Check)
# ---------------------------
elif menu == "🏥 Salud de Scrapers (Health Check)":
    renderizar_dashboard_salud(supabase)

# ---------------------------
# Panel de Gestión
# ---------------------------
elif menu == "🛠️ Configurar Radares y URLs":
    st.title("🛠️ Panel de Gestión de Enlaces")
    try:
        res_conteo = supabase.table("radares").select("id, identificador, url, activo").execute()
        if res_conteo.data:
            totales = len(res_conteo.data)
            activos = sum(1 for r in res_conteo.data if r.get("activo", True) is not False)
            pausados = totales - activos

            m1, m2, m3 = st.columns(3)
            m1.metric("📊 Total Radares Registrados", totales)
            m2.metric("🟢 Radares En Servicio", activos)
            m3.metric("🔴 Radares Pausados / Inactivos", pausados)

            if pausados > 0:
                with st.expander("👁️ Ver lista de URLs deshabilitadas actualmente", expanded=False):
                    for r in res_conteo.data:
                        if r.get("activo") is False:
                            st.write(f"🔴 **{r.get('identificador')}** ➔ `{r.get('url')}`")
        st.write("---")
    except Exception:
        pass
    lista_tiendas = obtener_tiendas_dinamicas()
    cats_form = ["Perfumes", "Zapatillas", "Ropa (Medias)", "Ropa (Polos)", "Ropa (Casacas/Poleras)", "Ropa (Shorts)", "Ropa (Buzos)", "Audifonos", "TV", "Parlante", "Barra de sonido", "Celular", "PC / Laptop", "Refrigeradora", "Lavadora", "Electrodomesticos", "Campana Extractora", "Cama", "Otros"]

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
                    "electro": "ELECTRODOMESTICOS", "campana": "CAMPANA_EXTRACTORA", "extractora": "CAMPANA_EXTRACTORA", "cama": "CAMA", "colchon": "CAMA"
                }
                cat_final = next((val for key, val in cat_map.items() if key in cl), "OTROS")

            nuevo_id = f"{t_final.replace(' ', '_')}-{cat_final}-{nombre.replace(' ', '_').upper()}-{talla.replace(' ', '_').upper()}"
            try:
                if st.session_state.mod_id is not None:
                    supabase.table("radares").update({"url": url.strip(), "precio_max": precio_max, "identificador": nuevo_id}).eq("id", st.session_state.mod_id).execute()
                else:
                    supabase.table("radares").insert({"url": url.strip(), "precio_max": precio_max, "identificador": nuevo_id, "activo": True}).execute()
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

                with st.expander(f"🏪 **{tienda_nombre}** ({cant_radares} radar{'es' if cant_radares > 1 else ''})", expanded=False):
                    for index, (item, parts) in enumerate(items_tienda):
                        es_activo = item.get("activo", True)
                        if es_activo is None:
                            es_activo = True

                        with st.container(border=True):
                            col_info, col_toggle, col_mod, col_del = st.columns([5.5, 1.5, 1.5, 1.5])
                            
                            p_tienda = parts[0] if len(parts) > 0 else "OTRAS"
                            p_cat = parts[1].replace('_', ' ') if len(parts) > 1 else "GENERAL"
                            p_tag = parts[2] if len(parts) > 2 else "N/A"
                            p_talla = parts[3] if len(parts) > 3 else "Todas"

                            indicador_estado = "🟢 **[ACTIVO]**" if es_activo else "🔴 **[INACTIVO]**"

                            with col_info:
                                st.markdown(f"**{index + 1}. 🌐 [{p_tienda}]** {indicador_estado} | #{p_cat} | Etiqueta: `{p_tag}` | **Tope: S/. {item.get('precio_max', 0):.2f}**")
                                st.caption(f"🔗 **URL:** {item.get('url', '')}")
                            
                            with col_toggle:
                                lbl_btn = "⏸️ Pausar" if es_activo else "▶️ Activar"
                                if st.button(lbl_btn, key=f"t_{item['id']}", use_container_width=True):
                                    supabase.table("radares").update({"activo": not es_activo}).eq("id", item['id']).execute()
                                    st.rerun()

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

    if start_btn:
        target = st.session_state.get("filtro_activo", "TODOS")
        
        with st.status(f"🕵️‍♂️ Patrullando objetivo: '{target}'...", expanded=True) as status:
            st.write("🔎 Iniciando enrutamiento y escaneo de tienda...")
            try:
                result_msg = revisar_ofertas(target)
                st.session_state.scraper_result = {"resumen": result_msg, "target": target, "status": "ok"}
                status.update(label="✅ ¡Patrullaje completado con éxito!", state="complete", expanded=False)
            except Exception as e:
                st.session_state.scraper_result = {"error": str(e), "target": target, "status": "error"}
                status.update(label=f"❌ Error durante el patrullaje: {e}", state="error", expanded=True)

    raw_res = st.session_state.get("scraper_result", None)
    if raw_res:
        st.write("---")
        if raw_res.get("status") == "error":
            st.error(f"❌ **Falló el escaneo:** {raw_res.get('error')}")
        else:
            st.success(f"📋 **Resumen:** {raw_res.get('resumen')}")

    st.write("---")
    st.subheader("📊 Reporte de Ofertas Registradas")

    target_escaneado = st.session_state.get("filtro_activo", "TODOS")

    try:
        q = supabase.table("historial_precios").select("identificador, nombre_producto, precio, precio_regular, imagen_producto, link_producto, fecha").order("fecha", desc=True)
        if target_escaneado and target_escaneado != "TODOS":
            q = q.ilike("identificador", f"%{target_escaneado}%")
        
        res_recientes = q.limit(60).execute()
        
        if res_recientes.data:
            reporte_items = []
            vistos_ui = set()
            for reg in res_recientes.data:
                p_o = float(reg.get("precio") or 0.0)
                p_r = float(reg.get("precio_regular") or p_o)
                
                link_p = str(reg.get("link_producto", "#")).strip()
                if not link_p or link_p in vistos_ui or p_o <= 0:
                    continue
                vistos_ui.add(link_p)
                
                id_p = str(reg.get("identificador", "")).upper()
                parts = id_p.split("-")
                tienda = parts[0] if len(parts) > 0 else "GENERAL"
                
                raw_nombre = reg.get("nombre_producto")
                if raw_nombre and str(raw_nombre).strip() and str(raw_nombre).lower() != "none":
                    nombre_prod = str(raw_nombre).strip().title()
                elif len(parts) >= 4:
                    nombre_prod = "-".join(parts[2:-1]).replace("_", " ").title()
                else:
                    nombre_prod = id_p.replace("_", " ").title()
                
                reporte_items.append({
                    "Tienda": tienda,
                    "Producto": nombre_prod,
                    "Vista": reg.get("imagen_producto", ""),
                    "Precio Regular": p_r,
                    "Precio Oferta": p_o,
                    "Ahorro": max(0.0, p_r - p_o),
                    "Fecha": reg.get("fecha", ""),
                    "Link": link_p
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
                    df_reporte = pd.DataFrame(reporte_items)
                    st.dataframe(
                        df_reporte,
                        column_config={
                            "Tienda": "🏪 Tienda",
                            "Producto": "📦 Producto",
                            "Vista": st.column_config.ImageColumn("🖼️ Foto"),
                            "Precio Regular": st.column_config.NumberColumn("💰 P. Regular", format="S/. %.2f"),
                            "Precio Oferta": st.column_config.NumberColumn("🏷️ P. Oferta", format="S/. %.2f"),
                            "Ahorro": st.column_config.NumberColumn("📉 Ahorro", format="S/. %.2f"),
                            "Fecha": "📅 Fecha",
                            "Link": st.column_config.LinkColumn("🛒 Enlace", display_text="Ver Oferta")
                        },
                        hide_index=True,
                        use_container_width=True
                    )
        else:
            st.info("No hay registros almacenados para esta categoría.")
    except Exception as err_rep:
        st.error(f"Error cargando catálogo: {err_rep}")

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

# ---------------------------
# Métricas Visuales de Health Check (Gráficos)
# ---------------------------
elif menu == "📊 Métricas visuales de Health Check (Gráficos)":
    st.title("📊 Monitor Visual de Salud de Scrapers")
    st.caption("Estado actual, historial de fallos y rendimiento de extracción por tienda.")
    st.write("---")

    try:
        res = supabase.table("health_checks")\
            .select("tienda, estado, fallos_consecutivos, ultimo_escaneo, ultimos_productos_count, ultimo_error")\
            .order("fallos_consecutivos", desc=True)\
            .execute()

        data = res.data if res and res.data else []

        if not data:
            st.info("ℹ️ No hay registros almacenados en la tabla 'health_checks'.")
        else:
            df_salud = pd.DataFrame(data)

            total_tiendas = len(df_salud)
            operativas = len(df_salud[df_salud["estado"].str.upper() == "OPERATIVO"])
            caidas = len(df_salud[df_salud["estado"].str.upper() == "CAIDO"])
            total_prods = df_salud["ultimos_productos_count"].fillna(0).sum()

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Tiendas Monitoreadas", f"{total_tiendas}")
            m2.metric("🟢 Operativas", f"{operativas}")
            m3.metric("🔴 Caídas", f"{caidas}")
            m4.metric("📦 Total Prods. Úl. Scan", f"{int(total_prods)}")

            st.divider()

            col_g1, col_g2 = st.columns(2)

            with col_g1:
                st.markdown("#### 🚨 Fallos Consecutivos por Tienda")
                st.bar_chart(data=df_salud, x="tienda", y="fallos_consecutivos", color="#FF3D00")

            with col_g2:
                st.markdown("#### 📦 Productos Extraídos en Último Escaneo")
                st.bar_chart(data=df_salud, x="tienda", y="ultimos_productos_count", color="#00C853")

            st.divider()
            st.markdown("#### 📋 Detalle Completo de Diagnóstico")

            def dar_formato_estado(est):
                e = str(est).upper() if est else "DESCONOCIDO"
                if "OPERATIVO" in e:
                    return "🟢 OPERATIVO"
                elif "CAIDO" in e:
                    return "🔴 CAÍDO"
                elif "ADVERTENCIA" in e:
                    return "⚠️ ADVERTENCIA"
                return f"⚪ {e}"

            df_salud["Estado"] = df_salud["estado"].apply(dar_formato_estado)
            df_salud["ultimo_error"] = df_salud["ultimo_error"].fillna("Sin errores registrados")

            df_mostrar = df_salud.rename(columns={
                "tienda": "Tienda",
                "fallos_consecutivos": "Fallos Consecutivos",
                "ultimos_productos_count": "Prods. Capturados",
                "ultimo_escaneo": "Último Escaneo",
                "ultimo_error": "Último Error Registrado"
            })[["Tienda", "Estado", "Fallos Consecutivos", "Prods. Capturados", "Último Escaneo", "Último Error Registrado"]]

            st.dataframe(
                df_mostrar,
                use_container_width=True,
                hide_index=True
            )
    except Exception as e:
        st.error(f"🚨 Error al generar reporte visual de salud: {e}")

# ---------------------------
# Validador de Radares ("Probar URL")
# ---------------------------
elif menu == "🧪 Validador de Radares (\"Probar URL\")":
    st.title("🧪 Probador de Radares en Tiempo Real")
    st.caption("Verifica si una URL extrae productos de forma correcta antes de guardarla en la base de datos.")
    st.write("---")

    lista_tiendas_val = obtener_tiendas_dinamicas()

    col1, col2, col3 = st.columns([3, 1.5, 1])
    with col1:
        test_url = st.text_input("URL del radar a probar:", placeholder="https://www.falabella.com.pe/...")
    with col2:
        test_tienda = st.selectbox("Tienda:", lista_tiendas_val)
    with col3:
        test_limite = st.number_input("Precio Máx (S/.):", value=500.0, step=50.0)

    btn_probar = st.button("🚀 Probar Scraper Ahora", type="primary", use_container_width=True)

    if btn_probar:
        if not test_url or not test_url.startswith("http"):
            st.warning("⚠️ Por favor ingresa una URL válida (debe empezar con http:// o https://).")
        else:
            with st.spinner(f"⏳ Escaneando {test_tienda}... Por favor espera unos segundos..."):
                try:
                    productos_test = escanear_tienda(test_url, test_tienda, test_limite)
                    
                    if productos_test:
                        st.success(f"✅ ¡Éxito! Se encontraron {len(productos_test)} productos válidos por debajo de S/. {test_limite:.2f}")
                        st.markdown("#### 📦 Previsualización de Productos Extraídos:")
                        cols = st.columns(3)
                        for idx, p in enumerate(productos_test[:6]):
                            with cols[idx % 3]:
                                with st.container(border=True):
                                    img_src = p.get("img")
                                    if img_src and len(img_src) > 10:
                                        st.image(img_src, use_container_width=True)
                                    else:
                                        st.caption("🖼️ Sin imagen")
                                    st.markdown(f"**{p.get('nombre')}**")
                                    st.markdown(f"🏷️ **S/. {p.get('precio'):.2f}** *(Reg: S/. {p.get('precio_regular', 0):.2f})*")
                                    st.markdown(f"🛒 [Ver en Tienda]({p.get('link')})")

                        if len(productos_test) > 6:
                            st.info(f"ℹ️ Y {len(productos_test) - 6} productos más extraídos...")
                    else:
                        st.error("❌ El scraper finalizó pero no devolvió ningún producto válido. Revisa si la URL o el precio máximo son correctos.")
                except Exception as e:
                    st.error(f"🚨 Error ejecutando el scraper de prueba: {e}")

# ---------------------------
# Diagnóstico de Bajas de Precio
# ---------------------------
elif menu == "🔍 Diagnóstico de Bajas de Precio":
    st.title("🔍 Diagnóstico y Probador de Bajas de Precio")
    st.markdown(
        "Ingresa la URL de una tienda que ya funciona para analizar sus productos en vivo, "
        "compararlos contra Supabase y **probar la notificación de baja de precio en Telegram**."
    )

    url_test = st.text_input("Ingresa la URL a diagnosticar:", placeholder="https://www.jbl.com.pe/audio-para-hogar")
    
    col1, col2 = st.columns(2)
    with col1:
        precio_limite = st.number_input("Precio límite (S/.):", value=999999.0, step=100.0)
    with col2:
        tienda_nombre = st.text_input("Nombre de la tienda (ej. JBL, ADIDAS, PLATANITOS):", value="JBL").strip().upper()

    if st.button("🚀 Diagnosticar URL y Comparar con Supabase", type="primary"):
        if not url_test:
            st.error("Por favor ingresa una URL válida.")
        else:
            with st.spinner("Analizando productos y consultando la base de datos..."):
                from patrol import TIENDAS_CON_ENFRIAMIENTO, tienda_necesita_patrullaje
                from utils import safe_float

                # 1. Verificar Enfriamiento
                if tienda_nombre in TIENDAS_CON_ENFRIAMIENTO:
                    horas = TIENDAS_CON_ENFRIAMIENTO[tienda_nombre]
                    puede = tienda_necesita_patrullaje(supabase, tienda_nombre, horas_espera=horas)
                    if not puede:
                        st.warning(f"⏳ **Atención:** La tienda **{tienda_nombre}** está en modo Enfriamiento (espera de {horas}h). El patrullaje automático omitirá esta tienda para no gastar créditos.")
                    else:
                        st.success(f"✅ La tienda **{tienda_nombre}** está libre y lista para patrullar.")

                # 2. Escanear productos de la URL
                prods = escanear_tienda(url_test, tienda_nombre, precio_limite)
                
                if not prods:
                    st.error("No se extrajo ningún producto de la URL. Revisa la consola/log o el scraper de la tienda.")
                else:
                    st.success(f"Se extrajeron {len(prods)} productos de la web.")
                    
                    resultados = []

                    for p in prods:
                        link_raw = str(p.get("link", url_test)).strip()
                        link_clean = link_raw.split('?')[0].split('#')[0].rstrip('/')
                        precio_web = safe_float(p.get("precio"))
                        nombre = p.get("nombre", "Sin nombre")
                        img = p.get("img", "")

                        # Consultar Supabase
                        res_bd = supabase.table("historial_precios")\
                            .select("id, precio, fecha")\
                            .eq("link_producto", link_clean)\
                            .limit(1)\
                            .execute()

                        if not res_bd.data:
                            estado = "🆕 NUEVO (No existe en BD)"
                            precio_bd_txt = "No registrado"
                            precio_bd_num = None
                        else:
                            reg = res_bd.data[0]
                            precio_bd_num = safe_float(reg.get("precio"))
                            precio_bd_txt = f"S/. {precio_bd_num:.2f}"
                            
                            if precio_web < precio_bd_num:
                                estado = "📉 BAJÓ DE PRECIO (Disparará Alerta)"
                            elif precio_web > precio_bd_num:
                                estado = "📈 SUBIÓ DE PRECIO (Silencioso)"
                            else:
                                estado = "🕒 PRECIO IGUAL (Silencioso)"

                        resultados.append({
                            "Producto": nombre,
                            "Precio Web": f"S/. {precio_web:.2f}",
                            "Precio BD": precio_bd_txt,
                            "Estado Detectado": estado,
                            "Link Clean": link_clean,
                            "Imagen": img,
                            "Precio Web Raw": precio_web,
                            "Precio BD Raw": precio_bd_num
                        })

                    st.subheader("📊 Comparativa en Tiempo Real (Web vs Supabase)")
                    st.dataframe(resultados)

                    st.session_state["diag_resultados"] = resultados
                    st.session_state["diag_tienda"] = tienda_nombre

    # 3. Módulo para forzar el envío de una alerta de baja de precio a Telegram
    if "diag_resultados" in st.session_state and st.session_state["diag_resultados"]:
        st.divider()
        st.subheader("🧪 Probador de Alerta 'BAJA DE PRECIO' en Telegram")
        st.markdown("Selecciona uno de los productos analizados arriba para simular una oferta y enviar la alerta a Telegram:")

        opciones_prods = [f"{r['Producto']} ({r['Precio Web']})" for r in st.session_state["diag_resultados"]]
        prod_idx = st.selectbox("Selecciona producto a probar:", range(len(opciones_prods)), format_func=lambda x: opciones_prods[x])
        
        prod_sel = st.session_state["diag_resultados"][prod_idx]
        tienda_sel = st.session_state["diag_tienda"]

        precio_anterior_simulado = st.number_input("Simular precio regular/anterior (S/.):", value=prod_sel["Precio Web Raw"] + 250.0, step=50.0)

        if st.button("📲 Probar Alerta 'BAJA DE PRECIO' en Telegram AHORA", type="primary"):
            from notifications import enviar_alerta_telegram
            
            with st.spinner("Enviando mensaje de prueba a Telegram..."):
                exito = enviar_alerta_telegram(
                    tienda=tienda_sel,
                    nombre=prod_sel["Producto"],
                    precio_oferta=prod_sel["Precio Web Raw"],
                    precio_regular=precio_anterior_simulado,
                    link=prod_sel["Link Clean"],
                    imagen=prod_sel["Imagen"],
                    tipo_alerta="BAJA_PRECIO"
                )

                if exito:
                    st.balloons()
                    st.success("✅ ¡Excelente! La alerta de 'BAJA DE PRECIO' fue enviada correctamente a tu Telegram.")
                else:
                    st.error("❌ Falló el envío a Telegram. Revisa las credenciales `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID`.")
