import os
import urllib3
import streamlit as st
from supabase import create_client, Client

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TELEGRAM_DEV_CHAT_ID = os.environ.get("TELEGRAM_DEV_CHAT_ID") or TELEGRAM_CHAT_ID

try:
    if hasattr(st, "secrets"):
        if "SUPABASE_URL" in st.secrets and st.secrets["SUPABASE_URL"]:
            SUPABASE_URL = st.secrets["SUPABASE_URL"]
        if "SUPABASE_KEY" in st.secrets and st.secrets["SUPABASE_KEY"]:
            SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
        if "TELEGRAM_TOKEN" in st.secrets and st.secrets["TELEGRAM_TOKEN"]:
            TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
        if "TELEGRAM_CHAT_ID" in st.secrets and st.secrets["TELEGRAM_CHAT_ID"]:
            TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
        if "TELEGRAM_DEV_CHAT_ID" in st.secrets and st.secrets["TELEGRAM_DEV_CHAT_ID"]:
            TELEGRAM_DEV_CHAT_ID = st.secrets["TELEGRAM_DEV_CHAT_ID"]
except Exception:
    pass

if not SUPABASE_URL or not SUPABASE_KEY or not SUPABASE_URL.startswith("http"):
    raise ValueError(f"Error crítico: Configuración de Supabase inválida. URL: '{SUPABASE_URL}'")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

LISTA_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0"
]
