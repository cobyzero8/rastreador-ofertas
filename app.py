import streamlit as st
import json
import os
import pandas as pd
import requests
from datetime import datetime
import plotly.express as px
from supabase import create_client, Client

st.set_page_config(page_title="COBY & GEMINI - Central de Élite", layout="wide")

SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_publishable_LG-EavkoMBYDSCS0xsCccQ_1062w4zq"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

CUPONES_FILE = "cupones.json"
TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

PRIMERA_NECESIDAD = ["SHAMPOO", "DESODORANTE", "JABON", "PERFUMES", "ALIMENTOS", "ABARROTES", "HOGAR", "SALUD"]

def obtener_tiendas_dinamicas():
    tiendas_base = ["ADIDAS", "FALABELLA", "MARATHON", "RIPLEY", "PUMA", "NIKE", "NATURA", "MIFARMA", "INKAFARMA", "MERCADO_LIBRE", "TRIATHLON", "JBL", "SAMSUNG", "LBEL", "ESIKA", "CYZONE", "PLAZA_VEA", "TOTTUS", "METRO", "LATAM", "SKY"]
    try:
        res = supabase.table("radares").select("identificador").execute()
        if res.data:
            for item in res.data:
                meta = item["identificador"].split("-")
                tnd = meta[0].upper().strip()
                if tnd and tnd not in tiendas_base: tiendas_base.append(tnd)
    except: pass
    return sorted(tiendas_base)

def obtener_categorias_dinamicas():
    categorias_base = ["ZAPATILLAS", "POLOS", "POLERAS", "PERFUMES", "SHAMPOO", "JABON", "ABARROTES", "VUEGOS", "OTROS"]
    try:
        res = supabase.table("radares").select("identificador").execute()
        if res.data:
            for item in res.data:
                meta = item["identificador"].split("-")
                if len(meta) > 1:
                    cat = meta[1].upper().strip()
                    if cat and cat not in categorias_base: categorias_base.append(cat)
    except: pass
    return sorted(categorias_base)

def procesar_comandos_telegram_pendientes():
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/getUpdates"
    try:
        resp = requests.get(url, timeout=5).json()
        if resp.get("ok") and resp.get("result"):
            for update in resp["result"]:
                msg = update.get("message", {})
                txt = msg.get("text", "")
                if txt.startswith("/guardar "):
                    parts = txt.replace("/guardar ", "").split(" ")
                    if len(parts) >= 5:
                        r_url = parts[0]
                        r_tnd = parts[1].upper()
                        r_cat = parts[2].upper()
                        r_nom = parts[3].replace(" ", "_")
                        r_top = int(parts[4])
                        r_id = f"{r_tnd}-{r_cat}-{r_nom}-TODAS"
                        supabase.table("radares").insert({"url": r_url, "precio_max": r_top, "identificador": r_id}).execute()
    except: pass

try: procesar_comandos_telegram_pendientes()
except: pass

# --- BARRA LATERAL ---
st.sidebar.markdown("## 🧠 COBY & GEMINI")
st.sidebar.caption("🚀 _Central de Inteligencia Avanzada v10.0_")
st.sidebar.caption("⚡ Estatus: **Diseño Ultra Dashboard Activado**")
st.sidebar.write("---")

menu = st.sidebar.radio("Selecciona una opción:", ["📈 Ver Dashboard", "💰 Métricas de Ahorro", "📊 Historial de Precios Pro", "🛠️ Gestionar Enlaces Pro", "💥 Forzar Escaneo"])

if "mod_url" not in st.session_state: st.session_state.mod_url = ""
if "mod_nombre" not in st.session_state: st.session_state.mod_nombre = ""
if "mod_talla" not in st.session_state: st.session_state.mod_talla = ""
if "mod_precio" not in st.session_state: st.session_state.mod_precio = 100

# --- FUNCION REUTILIZABLE PARA PINTAR TARJETAS MODERNAS ---
def renderizar_tarjetas_productos(lista_items):
    if not lista_items:
        st.info("No hay artículos registrados en esta categoría.")
        return
        
    for item in lista_items:
        # Definir color del borde si es oferta destructiva o patrullaje normal
        es_oferta = False
        if isinstance(item["p_actual"], float) and item["p_actual"] <= item["p_compra"]:
            es_oferta = True
            
        borde_color = "rgba(0, 204, 150, 0.4)" if es_oferta else "rgba(128, 128, 128, 0.2)"
        bg_card = "rgba(0, 204, 150, 0.05)" if es_oferta else "rgba(255, 255, 255, 0.01)"
        
        # Contenedor interactivo moderno
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([2.5, 2, 2.5, 2])
            
            with c1:
                st.markdown(f"### 📦 {item['Elemento']}")
                st.markdown(f"**🏪 Tienda:** `{item['Tienda']}` | **🏷️ Talla:** `{item['Detalle/Talla']}`")
                
            with c2:
                if isinstance(item["p_actual"], float):
                    st.metric(label="💰 Precio Actual Tienda", value=f"S/. {item['p_actual']:.2f}")
                else:
                    st.markdown(f"**💰 Precio Actual Tienda**\n\n<span style='color:#FFA500; font-weight:bold;'>{item['p_actual']}</span>", unsafe_allow_html=True)
                    
            with c3:
                st.metric(label="🎯 Tu Precio Objetivo", value=f"S/. {item['p_compra']:.2f}")
                
            with c4:
                # Calcular descuento dinámico en base a la data extraída
                if es_oferta and isinstance(item["p_actual"], float):
                    ahorro_soles = item["p_compra"] - item["p_actual"]
                    porcentaje = (ahorro_soles / item["p_compra"]) * 100 if item["p_compra"] > 0 else 0
                    st.metric(label="🔥 ¡Ahorro Detectado!", value=f"-S/. {ahorro_soles:.2f}", delta=f"{porcentaje:.1f}% menos")
                elif isinstance(item["p_actual"], float):
                    sobreprecio = item["p_actual"] - item["p_compra"]
                    st.markdown(f"**📊 Estado**\n\n<span style='color:#888;'>Falta S/. {sobreprecio:.2f} para tu meta</span>", unsafe_allow_html=True)
                else:
                    st.markdown("**📊 Estado**\n\n`Esperando Radar`", unsafe_allow_html=True)
            
            # Fila inferior de acción rápida
            st.markdown(f"[🛒 Abrir Enlace Oficial de Compra]({item['Compra']})")

# --- DASHBOARD REDISEÑADO ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Central Operativa COBY & GEMINI")
    st.markdown("### 📊 Monitor de Inteligencia Comercial en Tiempo Real")
    st.write("---")
    
    lista_hogar, lista_personal = [], []
    
    try:
        res_r = supabase.table("radares").select("*").execute()
        if res_r.data:
            for item in res_r.data:
                id_prod = item["identificador"]
                parts = id_prod.split("-")
                tienda_txt = parts[0].upper() if len(parts) > 0 else "N/A"
                cat_txt = parts[1].upper() if len(parts) > 1 else "OTROS"
                prod_txt = parts[2].replace("_", " ").title() if len(parts) > 2 else "N/A"
                talla_txt = parts[3] if len(parts) > 3 else "N/A"
                
                # Valores numéricos puros para el motor de lógica
                precio_compra_base = float(item['precio_max'])
                precio_actual_tienda = "🔄 Esperando Guardia..."
                
                try:
                    res_h = supabase.table("historial_precios").select("precio").eq("identificador", id_prod).order("id", desc=True).limit(1).execute()
                    if res_h.data and res_h.data[0]['precio']:
                        precio_actual_tienda = float(res_h.data[0]['precio'])
                except: pass
                
                item_dict = {
                    "Tienda": tienda_txt, "Categoría": cat_txt,
                    "Elemento": prod_txt, "Detalle/Talla": talla_txt,
                    "p_actual": precio_actual_tienda, "p_compra": precio_compra_base, 
                    "Compra": item["url"]
                }
                
                if cat_txt in PRIMERA_NECESIDAD: lista_hogar.append(item_dict)
                else: lista_personal.append(item_dict)
    except: pass

    tab1, tab2, tab3 = st.tabs(["🛒 Canasta Hogar / Primera Necesidad", "👟 Gustos Personales y Viajes", "🎟️ Cuponera Inteligente"])
    
    with tab1:
        renderizar_tarjetas_productos(lista_hogar)
    with tab2:
        renderizar_tarjetas_productos(lista_personal)
    with tab3:
        if os.path.exists(CUPONES_FILE):
            with open(CUPONES_FILE, "r", encoding="utf-8") as f_cup: cupones_data = json.load(f_cup)
            lista_cupones_tabla = []
            for tnda, lista_c in cupones_data.items():
                for item_c in lista_c:
                    lista_cupones_tabla.append({"Tienda": tnda.upper(), "Código": f"✨ {item_c['codigo']} ✨", "Descuento": item_c['descuento'], "Detalle": item_c['detalle']})
            if lista_cupones_tabla: st.dataframe(pd.DataFrame(lista_cupones_tabla), use_container_width=True, hide_index=True)
            else: st.info("No hay cupones activos.")
        else: st.info("Cuponera lista.")

# --- MANTENER MÉTODOS DE SOPORTE ACTIVO ---
elif menu == "💰 Métricas de Ahorro":
    st.title("💰 Balance de Ahorro Familiar COBY & GEMINI")
    total_ahorrado = 145.80 
    c1, c2 = st.columns(2)
    with c1: st.metric(label="💵 Total Ahorrado Acumulado", value=f"S/. {total_ahorrado:.2f}")
    with c2: st.bar_chart(pd.DataFrame({"Mes": ["Abril", "Mayo", "Junio"], "Soles Ahorrados": [45.0, 89.2, total_ahorrado]}).set_index("Mes"))

elif menu == "📊 Historial de Precios Pro":
    st.title("📊 Gráficas del Historial de Precios Real")
    try:
        res_h = supabase.table("historial_precios").select("*").execute()
        if res_h.data:
            df_hist = pd.DataFrame(res_h.data)
            prod_sel = st.selectbox("Selecciona producto:", df_hist["identificador"].unique())
            df_f = df_hist[df_hist["identificador"] == prod_sel].sort_values("fecha")
            st.plotly_chart(px.line(df_f, x="fecha", y="precio", markers=True), use_container_width=True)
    except: pass

elif menu == "🛠️ Gestionar Enlaces Pro":
    st.title("🛠️ Gestionar Enlaces Pro")
    lista_tiendas = obtener_tiendas_dinamicas()
    lista_categorias = obtener_categorias_dinamicas()
    with st.container(border=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            tienda_sel = st.selectbox("Tienda", lista_tiendas)
            categoria_sel = st.selectbox("Categoría", lista_categorias)
        with c2:
            nombre = st.text_input("Nombre / Etiqueta")
            url = st.text_input("URL exacta")
        with c3:
            talla = st.text_input("Talla")
            precio_max = st.number_input("Precio Máximo", min_value=1, value=100)
        if st.button("💾 GUARDAR CAMBIOS EN LA NUBE", type="primary", use_container_width=True):
            nuevo_id = f"{tienda_sel}-{categoria_sel}-{nombre.replace(' ', '_')}-{talla if talla else 'TODAS'}"
            supabase.table("radares").insert({"url": url, "precio_max": precio_max, "identificador": nuevo_id}).execute()
            st.rerun()

elif menu == "💥 Forzar Escaneo":
    st.title("💥 Forzar Escaneo Automático COBY & GEMINI")
    if st.button("💥 INICIAR ESCANEO INTENSIVO DE ELITE", type="primary", use_container_width=True):
        try:
            from scraper import revisar_ofertas
            revisar_ofertas()
            st.success("✅ ¡Escaneo completado!")
        except Exception as e: st.error(f"Error: {e}")
