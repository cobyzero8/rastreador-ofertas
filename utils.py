import re
import logging
import streamlit as st
from urllib.parse import urlparse, urlunparse
from streamlit.runtime.scriptrunner import get_script_run_ctx

# Desactivar registros globales de Streamlit en modo CLI
logging.getLogger("streamlit.runtime.scriptrunner.script_runner").setLevel(logging.ERROR)
logging.getLogger("streamlit").setLevel(logging.ERROR)

def safe_log(mensaje, tipo="info"):
    """Imprime mensajes en consola y los envía a Streamlit únicamente si la UI está activa."""
    prefijos = {
        "info": "ℹ️",
        "success": "✅",
        "warning": "⚠️",
        "error": "🚨",
        "caption": "💬"
    }
    icono = prefijos.get(tipo, "📌")
    print(f"[{tipo.upper()}] {mensaje}")

    # Validar presencia de contexto web de Streamlit
    try:
        if get_script_run_ctx() is not None:
            if tipo == "caption":
                st.caption(mensaje)
            elif tipo == "error":
                st.error(mensaje)
            elif tipo == "warning":
                st.warning(mensaje)
            elif tipo == "success":
                st.success(mensaje)
            else:
                st.info(mensaje)
    except Exception:
        pass
