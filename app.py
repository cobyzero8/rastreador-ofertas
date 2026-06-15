import streamlit as st
import json
import os
from supabase import create_client, Client

# Configuración inicial
st.set_page_config(page_title="COBY & GEMINI", layout="wide")

SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_publishable_LG-EavkoMBYDSCS0xsCccQ_1062w4zq"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

HISTORIAL_FILE = "historial_precios.json"
CUPONES_FILE = "cupones.json"

# --- BARRA LATERAL ---
st.sidebar.title("🧠 COBY & GEMINI")
menu = st.sidebar.radio("Selecciona:", ["📈 Dashboard", "📊 Inteligencia", "💰 Ahorro", "🛠️ Enlaces", "💥 Escaneo"])

# --- DASHBOARD ---
if menu == "📈 Dashboard":
    st.title("🕵️‍♂️ Dashboard")
    st.info("Sistema cargado correctamente.")

# --- INTELIGENCIA COMERCIAL ---
elif menu == "📊 Inteligencia":
    st.title("📊 Inteligencia Comercial")
    st.info("Análisis de mercado.")

# --- MÈTRICAS DE AHORRO ---
elif menu == "💰 Ahorro":
    st.title("💰 Balance de Ahorro")
    st.write("Métricas generales.")

# --- GESTIONAR ENLACES PRO ---
elif menu == "🛠️ Enlaces":
    st.title("🛠️ Gestionar Enlaces")
    st.write("Gestión de radares.")

# --- FORZAR ESCANEO ---
elif menu == "💥 Escaneo":
    st.title("💥 Forzar Escaneo")
    if st.button("Iniciar"):
        try:
            from scraper import revisar_ofertas
            revisar_ofertas()
            st.success("Escaneo exitoso.")
        except Exception as e:
            st.error(f"Error: {e}")
