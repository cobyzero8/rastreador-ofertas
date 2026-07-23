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

# ⚡ Optimización de caché (TTL = 5 min) para reducir tráfico Egress
@st.cache_data(ttl=300)
def obtener_tiendas_dinamicas():
    tiendas_base = ["ADIDAS", "FALABELLA", "MARATHON", "RIPLEY", "PUMA", "NIKE", "MERCADO_LIBRE", "TRIATHLON", "JBL", "SAMSUNG", "PLAZA_VEA", "TOTTUS", "METRO", "PLATANITOS", "FOOTLOOSE", "ESTILOS", "NATURA", "HM"]
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
    
    with st.sidebar.expander("🧪 Verificar Bot de Telegram"):
        if st.button("🔔 Ejecutar Alerta de Prueba"):
            t_tok = st.secrets.get("TELEGRAM_TOKEN")
            t_cid = st.secrets.get("TELEGRAM_CHAT_ID")
            if not t_tok or not t_cid: st.error("Faltan credenciales.")
            else:
                test_body = "<b>🤖 COMPROBACIÓN CENTRAL:</b>\n\nEl Bot de Telegram se ha enlazado exitosamente."
                img_demo = "https://images.unsplash.com/photo-1542291026-7eec264c27ff"
                test_url = f"https://api.telegram.org/bot{t_tok}/sendPhoto"
                try:
                    requests.post(test_url, json={"chat_id": t_cid, "photo": img_demo, "caption": f"{test_body}\n\n👉 <a href='https://google.com.pe'><b>¡ENLACE!</b></a>", "parse_mode": "HTML"}, timeout=10)
                    st.success("¡Mensaje enviado con éxito!")
                except Exception as ex_t: st.error(f"Fallo: {ex_t}")

    botonera_independiente()
    st.write("---")
    
    lista_dashboard = []
    try:
        f_activo = st.session_state.filtro_activo
        # Selección acotada de columnas para ahorrar ancho de banda
        query = supabase.table("historial_precios").select("identificador, precio, precio_regular, imagen_producto, link_producto, fecha").order("fecha", desc=True)

        # Filtro de búsqueda directo en la base de datos
        if f_activo == "PERFUMES":
            query = query.ilike("identificador", "%PERFUME%")
        elif f_activo == "ZAPATILLAS":
            query = query.or_("identificador.ilike.%ZAPATILLA%,identificador.ilike.%CALZADO%")
        elif f_activo == "POLOS":
            query = query.ilike("identificador", "%POLO%")
        elif f_activo == "CASACAS":
            query = query.or_("identificador.ilike.%CASACA%,identificador.ilike.%POLERA%")
        elif f_activo == "SHORTS":
            query = query.ilike("identificador", "%SHORT%")
        elif f_activo == "BUZOS":
            query = query.or_("identificador.ilike.%BUZO%,identificador.ilike.%PANTALON%")
        elif f_activo == "MEDIAS":
            query = query.ilike("identificador", "%MEDIAS%")
        elif f_activo == "AUDIFONOS":
            query = query.ilike("identificador", "%AUDIFONO%")
        elif f_activo == "TV":
            query = query.or_("identificador.ilike.%TV%,identificador.ilike.%SMART%")
        elif f_activo == "PARLANTE":
            query = query.or_("identificador.ilike.%PARLANTE%,identificador.ilike.%SPEAKER%")
        elif f_activo == "BARRA DE SONIDO":
            query = query.or_("identificador.ilike.%BARRA%,identificador.ilike.%SOUNDBAR%")
        elif f_activo == "CELULAR":
            query = query.or_("identificador.ilike.%CELULAR%,identificador.ilike.%PHONE%")
        elif f_activo == "PC":
            query = query.or_("identificador.ilike.%PC%,identificador.ilike.%LAPTOP%")
        elif f_activo == "REFRIGERADORA":
            query = query.or_("identificador.ilike.%REFRIGERADORA%,identificador.ilike.%REFRIG%")
        elif f_activo == "LAVADORA":
            query = query.or_("identificador.ilike.%LAVADORA%,identificador.ilike.%LAVADO%")
        elif f_activo == "ELECTRODOMESTICOS":
            query = query.ilike("identificador", "%ELECTRO%")
        elif f_activo == "CAMA":
            query = query.or_("identificador.ilike.%CAMA%,identificador.ilike.%COLCHON%")

        res_h = query.limit(1000).execute()

        if res_h.data:
            proc = set()
            for reg in res_h.data:
                raw_precio = reg.get('precio')
                precio_venta = float(raw_precio) if raw_precio is not None else 0.0
                if precio_venta <= 0: continue

                id_p = str(reg["identificador"]).strip().upper()
                if id_p in proc: continue
                proc.add(id_p)
                
                parts = id_p.split("-")
                tnd_txt = parts[0].upper()
                
                prd_txt = "N/A"
                if len(parts) > 4:
                    prd_txt = "-".join(parts[4:]).replace("_", " ").title()
                elif len(parts) > 2:
                    prd_txt = parts[2].replace("_", " ").title()
                
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
    except Exception as e: st.warning(f"Sincronizando: {e}")

    if lista_dashboard: 
        df_dash = pd.DataFrame(lista_dashboard).sort_values(by="Descuento", ascending=False)
        st.dataframe(df_dash, column_config={"Tienda": "🏪 Tienda", "Nombre del Producto": "📦 Nombre del Producto", "Imagen del Producto": st.column_config.ImageColumn("🖼️ Vista"), "Precio Real": st.column_config.NumberColumn("💰 Precio Real", format="S/. %.2f"), "Precio de Venta": st.column_config.NumberColumn("🏷️ Precio de Venta", format="S/. %.2f"), "Descuento": st.column_config.NumberColumn("📉 Descuento", format="S/. %.2f"), "Link": st.column_config.LinkColumn("🛒 Enlace", display_text="Ver")}, hide_index=True, use_container_width=True)
    else: st.info("No hay ofertas registradas en este rango.")

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
                cat_final = "ROPA_MEDIAS" if "medias" in cl else "ROPA_POLOS" if "polos" in cl else "ROPA_CASACAS" if "casacas" in cl or "poleras" in cl else "ROPA_SHORTS" if "shorts" in cl else "ROPA_BUZOS" if "buzos" in cl else "PERFUMES" if "perfume" in cl else "ZAPATILLAS" if "zapatilla" in cl else "AUDIFONOS" if "audifono" in cl else "TV" if "tv" in cl else "PARLANTE" if "parlante" in cl else "BARRA_DE_SONIDO" if "barra" in cl else "CELULAR" if "celular" in cl else "PC" if "pc" in cl or "laptop" in cl else "REFRIGERADORA" if "refrigeradora" in cl else "LAVADORA" if "lavadora" in cl else "ELECTRODOMESTICOS" if "electro" in cl else "CAMA" if "cama" in cl or "colchon" in cl else "OTROS"
            
            nuevo_id = f"{t_final.replace(' ', '_')}-{cat_final}-{nombre.replace(' ', '_').upper()}-{talla.replace(' ', '_').upper()}"
            try:
                if st.session_state.mod_id is not None: 
                    supabase.table("radares").update({"url": url.strip(), "precio_max": precio_max, "identificador": nuevo_id}).eq("id", st.session_state.mod_id).execute()
                else: 
                    supabase.table("radares").insert({"url": url.strip(), "precio_max": precio_max, "identificador": nuevo_id}).execute()
                st.session_state.mod_id = None
                st.session_state.mod_nombre, st.session_state.mod_url = "", ""
                st.rerun()
            except Exception as e: st.error(f"Error: {e}")

    st.write("---")
    
    # 🏬 RENDERIZADO AGRUPADO POR TIENDAS (EXPANSORES)
    try:
        res_radares = supabase.table("radares").select("*").order("id", desc=True).execute()
        if res_radares.data:
            radares_por_tienda = {}
            for item in res_radares.data:
                parts = item["identificador"].split("-")
                tienda_nombre = parts[0].upper().strip() if parts[0] else "OTRAS"
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
                            with col_info:
                                st.markdown(f"**{index + 1}. 🌐 [{parts[0]}]** | #{parts[1].replace('_', ' ')} | Etiqueta: `{parts[2] if len(parts)>2 else 'N/A'}` | **Tope: S/. {item['precio_max']:.2f}**")
                                st.caption(f"🔗 **URL:** {item['url']}")
                            with col_mod:
                                if st.button("📝 Modificar", key=f"m_{item['id']}", use_container_width=True):
                                    st.session_state.mod_id = item["id"]
                                    st.session_state.mod_tienda = parts[0]
                                    st.session_state.mod_cat = parts[1].replace("_", " ").title()
                                    st.session_state.mod_nombre = parts[2] if len(parts) > 2 else ""
                                    st.session_state.mod_talla = parts[3] if len(parts) > 3 else "Todas"
                                    st.session_state.mod_url = item["url"]
                                    st.session_state.mod_precio = item["precio_max"]
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
        st.toast(f"🕵️‍♂️ Buscando {target}...")
        msg = revisar_ofertas(target)
        st.success(f"📊 Resumen del patrullaje: {msg}")
