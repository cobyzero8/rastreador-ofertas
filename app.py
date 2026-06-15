import streamlit as st
import json
import os
import pandas as pd
from supabase import create_client, Client

st.set_page_config(page_title="COBY & GEMINI", layout="wide")

# Conexión básica
try:
    supabase = create_client("https://uxornuepdxqlhzizjnhr.supabase.co", "sb_publishable_LG-EavkoMBYDSCS0xsCccQ_1062w4zq")
except:
    supabase = None

CUPONES_FILE = "cupones.json"

# --- MENÚ ---
menu = st.sidebar.radio("Navegación:", ["Dashboard", "Cuponera"])

# --- DASHBOARD ---
if menu == "Dashboard":
    st.title("Bienvenido a COBY")
    st.write("Sistema operativo.")

# --- CUPONERA ---
elif menu == "Cuponera":
    st.title("🎟️ Cupones")
    if os.path.exists(CUPONES_FILE):
        try:
            with open(CUPONES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # --- AQUÍ ESTÁ EL BLINDAJE DE LA LÍNEA 128 ---
            df = pd.DataFrame(data)
            st.dataframe(
                df,
                use_container_width=True
            )
        except Exception as e:
            st.error(f"Error cargando archivo: {e}")
