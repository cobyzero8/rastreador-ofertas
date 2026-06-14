import streamlit as st
import json
import os
import pandas as pd
import requests

st.set_page_config(
    page_title="CobyZero8 - Radar Familiar Pro",
    page_icon="🕵️‍♂️",
    layout="wide"
)

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

# --- INICIALIZAR SESIÓN PARA LIMPIAR CASILLEROS ---
if "tienda" not in st.session_state:
    st.session_state.tienda = "Adidas"
if "seccion" not in st.session_state:
    st.session_state.seccion = "Casacas"
if "url" not in st.session_state:
    st.session_state.url = ""
if "precio" not in st.session_state:
    st.session_state.precio = 100
if "talla" not in st.session_state:
    st.session_state.talla = "M"

def cargar_historial():
    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def cargar_urls():
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            # Retorna la lista tal cual está en el archivo
            return [linea.strip() for linea in f.readlines() if linea.strip() and "," in linea]
    return []

def guardar_urls(lista_lineas):
    with open(URLS_FILE, "w", encoding="utf-8") as f:
        for linea in lista_lineas:
            f.write(f"{linea}\n")

def disparar_escaneo_github():
    try:
        token = st.secrets["GITHUB_TOKEN"]
        repo = st.secrets["GITHUB_REPO"]
        url = f"https://api.github.com/repos/{repo}/actions/workflows/automatizacion.yml/dispatches"
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {"ref": "main"}
        res = requests.post(url, headers=headers, json=data, timeout=10)
        if res.status_code == 204:
            return True, "🚀 ¡Robot despertado con éxito! Revisa tu Telegram en 1 minuto."
        else:
            return False, f"❌ Error de conexión con GitHub (Código {res.status_code})"
    except Exception as e:
        return False, f"⚠️ Configuración incompleta: {str(e)}"

st.title("🕵️‍♂️ CobyZero8 - Radar Familiar Pro")
st.markdown("---")

# 🚨 BOTÓN EXPRESS EN LA BARRA LATERAL
st.sidebar.markdown("### ⚡ Acciones Rápidas")
if st.sidebar.button("💥 FORZAR ESCANEO AHORA"):
    with st.sidebar.spinner("Despertando al robot en la nube..."):
        exito, msg = disparar_escaneo_github()
        if exito:
            st.sidebar.success(msg)
        else:
            st.sidebar.error(msg)

menu = st.sidebar.selectbox("Navegación", [
    "📈 Ver Dashboard", 
    "🛠️ Gestionar Enlaces Pro"
])

if menu == "📈 Ver Dashboard":
    st.subheader("📊 Monitoreo de Ofertas en Tiempo Real")
    datos = cargar_historial()
    
    if not datos:
        st.info("⌛ Base de datos inicializada. Esperando que el robot cargue información.")
    else:
        lista_productos = []
        for clave, precio in datos.items():
            partes_clave = clave.split("_", 3)
            tienda = partes_clave[0] if len(partes_clave) > 0 else "General"
            seccion = partes_clave[1] if len(partes_clave) > 1 else "General"
            talla = partes_clave[2] if len(partes_clave) > 2 else "Cualquiera"
            nombre_producto = partes_clave[3] if len(partes_clave) > 3 else clave
            
            if isinstance(precio, dict):
                fechas_ordenadas = sorted(precio.keys())
                precio_final = precio[fechas_ordenadas[-1]] if fechas_ordenadas else 0
            else:
                precio_final = precio
                
            lista_productos.append({
                "Tienda": tienda,
                "Categoría": seccion,
                "Talla Requerida": talla,
                "Producto": nombre_producto.replace("_", " "),
                "Precio S/.": float(precio_final) if isinstance(precio_final, (int, float)) else precio_final
            })
        
        df = pd.DataFrame(lista_productos)
        
        c1, col2, col3 = st.columns(3)
        c1.metric("📦 Productos vigilados", len(df))
        col2.metric("🏪 Tiendas activas", df["Tienda"].nunique())
        
        filtro_tienda = col3.selectbox("🔍 Filtrar vista por Tienda:", ["Todas"] + list(df["Tienda"].unique()))
        if filtro_tienda != "Todas":
            df = df[df["Tienda"] == filtro_tienda]
            
        st.dataframe(df, use_container_width=True)

elif menu == "🛠️ Gestionar Enlaces Pro":
    st.subheader("🔗 Administrador Avanzado de URLs")
    lineas_actuales = cargar_urls()
    
    # INTERFAZ ASOCIADA AL SESSION_STATE
    col_t1, col_t2 = st.columns(2)
    tienda_sel = col_t1.selectbox("1. Elige la Tienda:", ["Adidas", "Falabella", "Ripley", "Marathon", "Platanitos", "Puma", "Nike"], key="tienda")
    seccion_nom = col_t2.text_input("2. Nombre de Sección (Ej: Casacas, Polos):", key="seccion")
    
    nueva_url = st.text_input("3. Pegar URL exacta de la sección:", key="url")
    
    col_p1, col_p2 = st.columns(2)
    nuevo_limite = col_p1.number_input("4. Presupuesto Máximo (S/.)", min_value=1, key="precio")
    talla_filtro = col_p2.text_input("5. Talla específica a vigilar (Ej: 41, M, S):", key="talla")
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    # BOTÓN DE PROCESAMIENTO
    if st.button("🚀 AÑADIR AL RADAR EN TIEMPO REAL", type="primary"):
        if nueva_url and seccion_nom:
            # Limpieza de caracteres y espacios fantasmas
            seccion_limpia = "".join(c for c in seccion_nom if c.isalnum() or c in ("_", "-")).strip("_")
            talla_limpia = "".join(c for c in talla_filtro if c.isalnum()).upper()
            
            if not seccion_limpia:
                seccion_limpia = "Seccion"
            
            identificador_completo = f"{tienda_sel}_{seccion_limpia}_{talla_limpia}"
            nueva_linea = f"{nueva_url.strip()},{int(nuevo_limite)},{identificador_completo}"
            
            # Quitar duplicados si existía el mismo identificador
            lineas_filtradas = [l for l in lineas_actuales if not l.endswith(identificador_completo)]
            
            # 🔥 CRUCIAL: Insertar la nueva línea AL INICIO de la lista (index 0)
            lineas_filtradas.insert(0, nueva_linea)
            
            # Guardar el archivo ordenado
            guardar_urls(lineas_filtradas)
            
            # ✨ MENSAJE FLOTANTE SÚPER SATISFACTORIO DE ÉXITO
            st.toast(f"✅ ¡Guardado satisfactoriamente: {identificador_completo}!", icon="🎯")
            
            # 🧹 LIMPIAR LOS CASILLEROS RESTABLECIENDO EL STATE
            st.session_state.url = ""
            st.session_state.seccion = "Casacas"
            st.session_state.precio = 100
            st.session_state.talla = "M"
            
            st.rerun()
        else:
            st.error("⚠️ Falta rellenar la URL o el Nombre de la Sección.")

    st.markdown("---")
    st.markdown("### 📋 Cola Actual de Escaneo")
    
    # Recargar de nuevo para renderizar
    lineas_render = cargar_urls()
    
    if not lineas_render:
        st.info("No hay enlaces en el radar. Registra tu primer enlace arriba.")
    else:
        for i, linea in enumerate(lineas_render):
            partes = linea.split(",")
            if len(partes) == 3:
                col_info, col_btn = st.columns([8, 2])
                meta = partes[2].split("_")
                tienda_txt = meta[0] if len(meta) > 0 else "Desconocida"
                cat_txt = meta[1] if len(meta) > 1 else "General"
                talla_txt = meta[2] if len(meta) > 2 else "Todas"
                
                col_info.code(f"🏪 {tienda_txt} | 📦 {cat_txt} | 👟 Talla: {talla_txt} | 🚨 Alerta si baja de: S/. {partes[1]}")
                if col_btn.button("🗑️ Borrar", key=f"del_{i}"):
                    lineas_render.pop(i)
                    guardar_urls(lineas_render)
                    st.rerun()
