import streamlit as st
import json
import os
import pandas as pd
import requests
import time

st.set_page_config(
    page_title="CobyZero8 - Radar Familiar",
    page_icon="🕵️‍♂️",
    layout="wide"
)

TOKEN_REAL = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
ID_REAL = "8019752668"
HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

def cargar_historial():
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return {}
    return {}

def cargar_urls():
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            return [linea.strip() for linea in f.readlines() if linea.strip() and "," in linea]
    return []

def guardar_urls(lista_lineas):
    with open(URLS_FILE, "w", encoding="utf-8") as f:
        for linea in lista_lineas: f.write(f"{linea}\n")

def enviar_respuesta_telegram(texto):
    url = f"https://api.telegram.org/bot{TOKEN_REAL}/sendMessage"
    payload = {"chat_id": ID_REAL, "text": texto, "parse_mode": "Markdown"}
    try: requests.post(url, json=payload, timeout=10)
    except: pass

# 🔄 BUCLE DE ESCUCHA AUTOMÁTICA EN TIEMPO REAL (SIN BOTONES)
@st.fragment(run_every=30)
def motor_bot_tiempo_real():
    url_get_updates = f"https://api.telegram.org/bot{TOKEN_REAL}/getUpdates"
    try:
        res = requests.get(url_get_updates, timeout=5).json()
        if res.get("ok") and res.get("result"):
            for update in res["result"]:
                msg = update.get("message", {})
                chat_id = str(msg.get("chat", {}).get("id", ""))
                texto_recibido = msg.get("text", "").strip().lower()
                
                if chat_id == ID_REAL and texto_recibido == "/resumen":
                    datos = cargar_historial()
                    urls_activas = cargar_urls()
                    
                    if not datos:
                        reporte = "📭 *Historial de ofertas vacío por hoy.*\n\n📍 *Radares activos esperando rebajas:*\n"
                        for u in urls_activas:
                            p = u.split(",")
                            if len(p) == 3: reporte += f"🔸 `{p[2]}` (Máx: S/. {p[1]})\n"
                    else:
                        reporte = "📋 *Resumen de Precios en el Radar:* \n\n"
                        for item, precio in datos.items():
                            nombre_limpio = item.replace("_", " ")
                            p_f = precio[sorted(precio.keys())[-1]] if isinstance(precio, dict) else precio
                            reporte += f"📦 *{nombre_limpio}*\n💰 Precio: S/. {p_f}\n\n"
                    
                    enviar_respuesta_telegram(reporte)
            
            # Confirmar lectura de mensajes procesados
            last_id = res["result"][-1]["update_id"]
            requests.get(f"{url_get_updates}?offset={last_id + 1}")
    except:
        pass

# Ejecutamos el motor invisible en segundo plano
motor_bot_tiempo_real()

st.title("🕵️‍♂️ CobyZero8 - Radar Familiar")
st.markdown("---")

menu = st.sidebar.selectbox("Navegación", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces (Anti-Caídas)"])

if menu == "📈 Ver Dashboard":
    st.subheader("📊 Monitoreo en Tiempo Real")
    datos = cargar_historial()
    if not datos:
        st.info("⌛ Base de datos inicializada. Esperando datos...")
    else:
        lista_productos = []
        for clave, precio in datos.items():
            seccion, nombre_producto = clave.split("_", 1) if "_" in clave else ("General", clave)
            precio_final = precio[sorted(precio.keys())[-1]] if isinstance(precio, dict) else precio
            lista_productos.append({"Sección": seccion, "Producto": nombre_producto, "Precio S/.": precio_final})
        st.dataframe(pd.DataFrame(lista_productos), use_container_width=True)

elif menu == "🛠️ Gestionar Enlaces (Anti-Caídas)":
    st.subheader("🔗 Administrador Remoto de URLs")
    lineas_actuales = cargar_urls()
    with st.form("form_url"):
        nueva_url = st.text_input("Pegar URL:")
        nuevo_limite = st.number_input("Presupuesto Máximo (S/.)", min_value=1, value=250)
        nuevo_nombre = st.text_input("Nombre sección (Ej: Adidas_Zapatillas):")
        if st.form_submit_button("Guardar"):
            if nueva_url and nuevo_nombre:
                lineas_actuales.append(f"{nueva_url},{nuevo_limite},{nuevo_nombre.replace(' ', '_')}")
                guardar_urls(lineas_actuales)
                st.rerun()
