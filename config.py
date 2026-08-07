import os
import streamlit as st
from supabase import create_client, Client

SUPABASE_URL = ""
SUPABASE_KEY = ""

# 1. Intentar obtener credenciales desde Streamlit Secrets
try:
    if hasattr(st, "secrets"):
        SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
        SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")
except Exception:
    pass

# 2. Si no existen en Streamlit, leer desde las variables de entorno (GitHub Actions)
if not SUPABASE_URL:
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
if not SUPABASE_KEY:
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

SUPABASE_URL = str(SUPABASE_URL).strip()
SUPABASE_KEY = str(SUPABASE_KEY).strip()

# 3. Validar y crear el cliente únicamente si las credenciales son válidas
if not SUPABASE_URL or not SUPABASE_KEY:
    print("🚨 ERROR CRÍTICO: 'SUPABASE_URL' o 'SUPABASE_KEY' no están configuradas.")
    supabase = None
else:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

LISTA_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0"
]
