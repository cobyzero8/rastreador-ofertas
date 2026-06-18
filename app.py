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

# --- MEJORA 1: PROCESAR COMANDOS DESDE TELEGRAM (PASARELA WEB) ---
def procesar_comandos_telegram_pendientes():
    url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/getUpdates"
    try:
        resp = requests.get(url, timeout=5).json()
        if resp.get("ok") and resp.get("result"):
            for update in resp["result"]:
                msg = update.get("message", {})
                txt = msg.get("text", "")
                if txt.startswith("/guardar "):
                    # Formato esperado: /guardar URL Tienda Categoria Nombre Tope
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

# --- BARRA LATERAL ---
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
            for item in res
