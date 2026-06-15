import streamlit as st
import json
import os
import pandas as pd
from supabase import create_client, Client

st.set_page_config(page_title="COBY & GEMINI", layout="wide")

SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_publishable_LG-EavkoMBYDSCS0xsCccQ_1062w4zq"

try:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
except:
    supabase = None

HISTORIAL_FILE = "historial_precios.json"
CUPONES_FILE = "cupones.json"

# --- BARRA LATERAL ---
menu = st.sidebar.radio("Menú:", [
    "📈 Dashboard", "📊 Inteligencia", "💰 Ahorro", "🛠️ Enlaces", "💥 Escaneo"
])

# --- DASHBOARD ---
if menu == "📈 Dashboard":
    st.title("Central COBY")
    
    if os.path.exists(CUPONES_FILE):
        try:
            with open(CUPONES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # --- PARCHE DE SEGURIDAD LÍNEA 128 ---
            df = pd.DataFrame(data)
            st.dataframe(
                df, 
                use_container_width=True
            )
        except:
            st.info("Cuponera vacía.")

# --- INTELIGENCIA COMERCIAL ---
elif menu == "📊 Inteligencia":
    st.title("Análisis")
    st.info("Módulo activo.")

# --- MÈTRICAS DE AHORRO ---
elif menu == "💰 Ahorro":
    st.title("Balance")

# --- GESTIONAR ENLACES PRO ---
elif menu == "🛠️ Enlaces":
    st.title("Radares")

# --- FORZAR ESCANEO ---
elif menu == "💥 Escaneo":
    st.title("Motor")
    if st.button("Ejecutar"):
        st.success("Iniciado.")
