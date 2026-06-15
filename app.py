import streamlit as st
import json
import os
import pandas as pd
import requests
import plotly.express as px
from supabase import create_client, Client

st.set_page_config(page_title="COBY & GEMINI - Inteligencia", layout="wide")

# Conexión Supabase
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_publishable_LG-EavkoMBYDSCS0xsCccQ_1062w4zq"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

HISTORIAL_FILE = "historial_precios.json"

st.sidebar.markdown("## 🧠 COBY & GEMINI v9.4")
menu = st.sidebar.radio("Selección:", ["📈 Dashboard", "📊 Inteligencia Horaria", "🛠️ Radares", "💥 Forzar Escaneo"])

if menu == "📈 Dashboard":
    st.title("🕵️‍♂️ Dashboard Principal")
    if os.path.exists(HISTORIAL_FILE):
        with open(HISTORIAL_FILE, "r", encoding="utf-8") as f: data = json.load(f)
        # Mostrar datos... (aquí va tu lógica de tablas)
        st.write("Dashboard cargado...")

elif menu == "📊 Inteligencia Horaria":
    st.title("📊 Análisis de Inteligencia Horaria")
    # Gráfica de mejores horas
    
elif menu == "🛠️ Radares":
    st.title("🛠️ Gestionar Radares")
    # Tu formulario de registro
    
elif menu == "💥 Forzar Escaneo":
    st.title("💥 Forzar Escaneo")
    if st.button("💥 INICIAR ESCANEO", type="primary"):
        with st.status("Ejecutando motor...", expanded=True) as status:
            try:
                from scraper import revisar_ofertas
                st.write("Conectando motor...")
                revisar_ofertas()
                status.update(label="✅ Escaneo finalizado", state="complete")
                st.success("¡Reporte enviado a Telegram!")
            except Exception as e:
                status.update(label="❌ Error crítico", state="error")
                st.error(f"El motor falló: {e}")
