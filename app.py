import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Radar Coby Pro", page_icon="🔥", layout="wide")

# --- CONFIGURACIÓN DE CONEXIÓN MAESTRA ---
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_secret_jf..."  # ⚠️ Reemplaza aquí con tu Service Role Key secreta
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ⚡ OPTIMIZACIÓN DE VELOCIDAD: Caché rápido de 10 segundos
@st.cache_data(ttl=10)
def obtener_opciones_base():
    try:
        res = supabase.table("radares").select("identificador, url, precio_max").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame(columns=["identificador", "url", "precio_max"])
    except:
        return pd.DataFrame(columns=["identificador", "url", "precio_max"])

df_radares = obtener_opciones_base()

# Procesamos datos para las listas desplegables
tiendas_disponibles = sorted(list(set([r.split("-")[0].upper() for r in df_radares["identificador"] if "-" in r]))) if not df_radares.empty else ["MARATHON", "NIKE", "ADIDAS"]
categorias_disponibles = sorted(list(set([r.split("-")[1].upper() for r in df_radares["identificador"] if "-" in r]))) if not df_radares.empty else ["ZAPATILLAS", "ROPA", "ACCESORIOS"]


# ==========================================
# 🛠️ LAS 5 OPCIONES DE TU MENÚ LATERAL IZQUIERDO (SIDEBAR RESTAURADO)
# ==========================================
st.sidebar.title("🔥 Radar Coby de Élite")
st.sidebar.markdown("---")

opcion_menu = st.sidebar.radio(
    "Selecciona una sección:",
    [
        "📈 Ver Dashboard", 
        "💥 Forzar Escaneo", 
        "📝 Gestionar Enlaces Pro", 
        "📊 Ver Base de Datos", 
        "👟 Gustos Personales y Viajes"
    ]
)

st.sidebar.markdown("---")
st.sidebar.info("Socio, el sistema está optimizado para cambiar de opción sin ponerse lento en el celular.")


# ==========================================
# 📈 OPCIÓN 1: VER DASHBOARD
# ==========================================
if opcion_menu == "📈 Ver Dashboard":
    st.title("📈 Dashboard de Monitoreo")
    st.write("Aquí puedes visualizar el comportamiento global de tus radares y análisis de variaciones.")
    # Coloca aquí el código o las gráficas originales de tu pestaña Dashboard

# ==========================================
# 💥 OPCIÓN 2: FORZAR ESCANEO
# ==========================================
elif opcion_menu == "💥 Forzar Escaneo":
    st.title("💥 Forzar Escaneo Intensivo")
    st.write("Presiona el botón para despertar al robot manualmente y lanzar las alertas a Telegram.")
    # Coloca aquí tu botón de "💥 INICIAR ESCANEO INTENSIVO DE ELITE"

# ==========================================
# 📝 OPCIÓN 3: GESTIONAR ENLACES PRO (MEJORADO PARA CELULAR)
# ==========================================
elif opcion_menu == "📝 Gestionar Enlaces Pro":
    st.title("📝 Gestionar Enlaces Pro")
    st.subheader("🚀 Registrar / Modificar Radar de Ofertas")
    
    # Selector de Tienda
    tienda_sel = st.selectbox("🏪 Selecciona la Tienda", tiendas_disponibles)
    
    # ➕ CAJA DE INGRESO NUEVA TIENDA (Formato móvil colapsable)
    with st.expander("➕ ¿No está tu tienda en la lista? Agrégala aquí"):
        nueva_tienda_input = st.text_input("Escribe el nombre de la nueva tienda (Ej: RIPLEY, FALABELLA):").strip().upper()
        if st.button("💾 Confirmar Nueva Tienda"):
            if nueva_tienda_input and nueva_tienda_input not in tiendas_disponibles:
                tiendas_disponibles.append(nueva_tienda_input)
                st.success(f"✅ ¡Tienda '{nueva_tienda_input}' añadida! Ya puedes seleccionarla arriba.")
                st.cache_data.clear()
    
    # Selector de Categoría
    cat_sel = st.selectbox("📦 Selecciona la Categoría / Producto", categorias_disponibles)
    
    # ➕ CAJA DE INGRESO NUEVA CATEGORÍA
    with st.expander("➕ ¿Falta tu categoría/producto? Agrégalo aquí"):
        nueva_cat_input = st.text_input("Escribe la nueva categoría (Ej: RUNNING, CASACAS):").strip().upper()
        if st.button("💾 Confirmar Nueva Categoría"):
            if nueva_cat_input and nueva_cat_input not in categorias_disponibles:
                categorias_disponibles.append(nueva_cat_input)
                st.success(f"✅ ¡Categoría '{nueva_cat_input}' añadida! Búscala en la lista de arriba.")
                st.cache_data.clear()

    # Campos de Entrada estándar
    nombre_prod = st.text_input("✏️ Nombre detallado del producto:", placeholder="Ej: Air Max Alpha 5")
    talla_sel = st.text_input("🏷️ Talla o Filtro específico (Opcional):", placeholder="Ej: 41 o S")
    url_radar = st.text_input("🔗 URL exacta de la Tienda a rastrear:")
    precio_tope = st.number_input("🎯 Precio Máximo Permitido (Tope S/.)", min_value=1.0, step=5.0)

    # Armamos el Identificador Único
    tienda_final = nueva_tienda_input if nueva_tienda_input else tienda_sel
    cat_final = nueva_cat_input if nueva_cat_input else cat_sel
    nombre_limpio = nombre_prod.strip().replace(" ", "_").lower() if nombre_prod else "producto"
    talla_limpia = talla_sel.strip() if talla_sel else "todas"
    
    nuevo_identificador = f"{tienda_final}-{cat_final}-{nombre_limpio}-{talla_limpia}"

    # BOTÓN GUARDAR CON MENSAJE DE CONFIRMACIÓN EN VERDE
    if st.button("💥 GUARDAR ENLACE EN LA NUBE", use_container_width=True):
        if url_radar:
            datos_radar = {
                "identificador": nuevo_identificador,
                "url": url_radar,
                "precio_max": precio_tope
            }
            try:
                supabase.table("radares").upsert(datos_radar).execute()
                st.success(f"🎉 ¡CONFIRMADO, SOCIO! El producto '{nombre_prod}' se guardó correctamente en la nube.")
                st.cache_data.clear()
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error con Supabase: {e}")
        else:
            st.warning("⚠️ Ingresa una URL antes de guardar.")

    st.markdown("---")
    
    # ⚙️ SECCIÓN PARA MODIFICAR O ELIMINAR LOS ENLACES AGREGADOS
    st.subheader("⚙️ Modificar o Eliminar Radares Activos")
    if not df_radares.empty:
        for idx, row in df_radares.iterrows():
            with st.container():
                st.write(f"🏷️ **ID:** `{row['identificador']}` | 🎯 **Tope:** S/.{row['precio_max']:.2f}")
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("✏️ Cargar para Modificar", key=f"mod_{idx}", use_container_width=True):
                        st.info("🔄 Datos cargados arriba. Ajusta el precio o campos y presiona 'GUARDAR EN LA NUBE'.")
                with col_btn2:
                    if st.button("🗑️ Borrar Radar", key=f"del_{idx}", use_container_width=True):
                        try:
                            supabase.table("radares").delete().eq("identificador", row['identificador']).execute()
                            st.success("🗑️ Enlace eliminado correctamente de la base de datos.")
                            st.cache_data.clear()
                            st.rerun()
                        except:
                            st.error("No se pudo eliminar.")
    else:
        st.write("No hay radares registrados.")

# ==========================================
# 📊 OPCIÓN 4: VISUALIZACIÓN BASE DE DATOS (ORDEN ASCENDENTE REAL)
# ==========================================
elif opcion_menu == "📊 Ver Base de Datos":
    st.title("📊 Base de Datos Histórica")
    st.subheader("📈 Monitoreo de Precios (Últimos ingresos en la primera fila)")
    
    try:
        # 🔄 CONSULTA ASCENDENTE POR REGISTRO RECIENTE (Últimos escaneos arriba)
        res_historial = supabase.table("historial_precios").select("*").order("id", ascending=False).limit(50).execute()
        
        if res_historial.data:
            df_historial = pd.DataFrame(res_historial.data)
            
            df_historial.rename(columns={
                "identificador": "📦 Identificador del Producto",
                "precio": "💵 Precio Registrado",
                "fecha": "📅 Fecha de Captura"
            }, inplace=True)
            
            st.dataframe(df_historial, use_container_width=True)
        else:
            st.info("ℹ️ Esperando los primeros datos del historial automático de GitHub Actions.")
    except Exception as e:
        st.error(f"Error al cargar el historial: {e}")

# ==========================================
# 👟 OPCIÓN 5: GUSTOS PERSONALES Y
