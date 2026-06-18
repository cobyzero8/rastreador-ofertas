import streamlit as st
import json
import os
import pandas as pd
import requests
from datetime import datetime
import plotly.express as px
from supabase import create_client, Client

st.set_page_config(page_title="COBY & GEMINI - Sistema Inteligente", layout="wide")

SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_publishable_LG-EavkoMBYDSCS0xsCccQ_1062w4zq"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HISTORIAL_FILE = "historial_precios.json"
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

# --- MEJORA DE VELOCIDAD: EVITAR CONSULTAR TELEGRAM EN CADA CLIC ---
if "ultimo_escaneo_telegram" not in st.session_state:
    st.session_state.ultimo_escaneo_telegram = 0

def procesar_comandos_telegram_pendientes():
    # Solo consulta a Telegram una vez por render para no poner lenta la app
    time_actual = datetime.now().timestamp()
    if time_actual - st.session_state.ultimo_escaneo_telegram < 5:
        return
    st.session_state.ultimo_escaneo_telegram = time_actual
    
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/getUpdates"
    try:
        resp = requests.get(url, timeout=3).json()
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
                        requests.post(f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage", json={"chat_id": CHAT_ID_TELEGRAM, "text": f"✅ ¡Base de datos actualizada desde el celular!\nRadar `{r_nom}` guardado con tope S/. {r_top}"})
    except: pass

try: procesar_comandos_telegram_pendientes()
except: pass

# --- BARRA LATERAL (TUS 5 OPCIONES ORIGINALES INTACTAS) ---
st.sidebar.markdown("## 🧠 COBY & GEMINI")
st.sidebar.caption("🚀 _Central de Inteligencia Avanzada v9.0_")
st.sidebar.caption("⚡ Estatus: **12 Mejoras Premium Totales**")
st.sidebar.write("---")

menu = st.sidebar.radio("Selecciona una opción:", ["📈 Ver Dashboard", "💰 Métricas de Ahorro", "📊 Inteligencia Horaria", "🛠️ Gestionar Enlaces Pro", "💥 Forzar Escaneo"])

if "mod_url" not in st.session_state: st.session_state.mod_url = ""
if "mod_nombre" not in st.session_state: st.session_state.mod_nombre = ""
if "mod_talla" not in st.session_state: st.session_state.mod_talla = ""
if "mod_precio" not in st.session_state: st.session_state.mod_precio = 100

# --- DASHBOARD ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Central COBY & GEMINI")
    st.subheader("📊 Dashboard de Control e Inteligencia Flotante")
    
    links_mapeados = {}
    try:
        res_l = supabase.table("radares").select("url", "identificador").execute()
        if res_l.data:
            for item in res_l.data: links_mapeados[item["identificador"]] = item["url"]
    except: pass

    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f: data = json.load(f)
            lista_hogar, lista_personal = [], []
            
            for id_prod, hist in data.items():
                if id_prod in ["TOTAL_AHORRADO_SISTEMA", "LOG_HORARIOS_DETECCION"]: continue
                parts = id_prod.split("-")
                tienda_txt = parts[0] if len(parts) > 0 else "N/A"
                cat_txt = parts[1].upper() if len(parts) > 1 else "OTROS"
                prod_txt = parts[2] if len(parts) > 2 else "N/A"
                talla_txt = parts[3] if len(parts) > 3 else "N/A"
                
                clave_link = f"{tienda_txt}-{cat_txt}-{prod_txt}-{talla_txt}"
                link_final = links_mapeados.get(clave_link, "#")
                
                precios_reales = [v for k, v in hist.items() if isinstance(v, (int, float)) and not k.startswith("hora_")]
                ultimo_precio = precios_reales[-1] if precios_reales else "N/A"
                
                item_dict = {
                    "Tienda": tienda_txt.upper(), "Categoría": cat_txt,
                    "Elemento": prod_txt.replace("_", " "), "Detalle/Talla": talla_txt,
                    "Precio Actual": f"S/. {ultimo_precio}" if ultimo_precio != "N/A" else "N/A", "Compra": link_final
                }
                
                if cat_txt in PRIMERA_NECESIDAD: lista_hogar.append(item_dict)
                else: lista_personal.append(item_dict)
            
            tab1, tab2, tab3 = st.tabs(
