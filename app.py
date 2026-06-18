import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime

# --- CONFIGURACIÓN DE CONEXIÓN MAESTRA ---
SUPABASE_URL = "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = "sb_secret_jf..." # ⚠️ Reemplaza aquí con tu Service Role Key secreta para gestionar libremente
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ❌ LÍNEA CON ERROR:
# st.set_page_config(page_title="Radar Coby Pro", page_icon="🔥", layout="vertical")

# ✅ LÍNEA CORREGIDA (Cambia "vertical" por "wide"):
st.set_page_config(page_title="Radar Coby Pro", page_icon="🔥", layout="wide")

# ⚡ OPTIMIZACIÓN DE VELOCIDAD: Caché rápido para evitar lentitud entre opciones
@st.cache_data(ttl=10)  # Recarga los selectores rápido de forma interna cada 10 segundos
def obtener_opciones_base():
    try:
        # Traemos radares existentes para deducir tiendas y categorías únicas registradas
        res = supabase.table("radares").select("identificador, url, precio_max").execute()
        df = pd.DataFrame(res.data) if res.data else pd.DataFrame(columns=["identificador", "url", "precio_max"])
        return df
    except:
        return pd.DataFrame(columns=["identificador", "url", "precio_max"])

df_radares = obtener_opciones_base()

# Procesamos las listas para los selectores móviles
tiendas_disponibles = sorted(list(set([r.split("-")[0].upper() for r in df_radares["identificador"] if "-" in r]))) if not df_radares.empty else ["MARATHON", "NIKE", "ADIDAS"]
categorias_disponibles = sorted(list(set([r.split("-")[1].upper() for r in df_radares["identificador"] if "-" in r]))) if not df_radares.empty else ["ZAPATILLAS", "ROPA", "ACCESORIOS"]

st.title("🔥 Panel de Gestión Radar Coby Pro")

# Creamos dos pestañas grandes compatibles con celular
tab_registro, tab_Historial = st.tabs(["📝 Gestionar Enlaces Pro", "📊 Ver Base de Datos"])

# ==========================================
# 📝 PESTAÑA 1: GESTIONAR ENLACES PRO (MÓVIL COMPATIBLE)
# ==========================================
with tab_registro:
    st.subheader("🚀 Registrar / Modificar Radar")
    
    # Selector de Tienda
    tienda_sel = st.selectbox("🏪 Selecciona la Tienda", tiendas_disponibles)
    
    # ➕ CAJA DE INGRESO NUEVA TIENDA (Perfecto para celular)
    with st.expander("➕ ¿No está tu tienda en la lista? Agrégala aquí"):
        nueva_tienda_input = st.text_input("Escribe el nombre de la nueva tienda (Ej: Ripley, Saga):").strip().upper()
        if st.button("💾 Confirmar Nueva Tienda"):
            if nueva_tienda_input and nueva_tienda_input not in tiendas_disponibles:
                tiendas_disponibles.append(nueva_tienda_input)
                st.success(f"✅ ¡Tienda '{nueva_tienda_input}' añadida temporalmente! Ya puedes seleccionarla arriba.")
                st.cache_data.clear()
    
    # Selector de Categoría
    cat_sel = st.selectbox("📦 Selecciona la Categoría / Producto", categorias_disponibles)
    
    # ➕ CAJA DE INGRESO NUEVA CATEGORÍA
    with st.expander("➕ ¿Falta tu categoría/producto? Agrégalo aquí"):
        nueva_cat_input = st.text_input("Escribe la nueva categoría (Ej: CASACAS, URBANAS):").strip().upper()
        if st.button("💾 Confirmar Nueva Categoría"):
            if nueva_cat_input and nueva_cat_input not in categorias_disponibles:
                categorias_disponibles.append(nueva_cat_input)
                st.success(f"✅ ¡Categoría '{nueva_cat_input}' añadida! Búscala en la lista de arriba.")
                st.cache_data.clear()

    # Campos de Entrada Estándar
    nombre_prod = st.text_input("✏️ Nombre detallado del producto o palabra clave:", placeholder="Ej: Air Max Alpha 5")
    talla_sel = st.text_input("🏷️ Talla o Filtro específico (Opcional):", placeholder="Ej: 41 o S")
    url_radar = st.text_input("🔗 URL exacta de la Tienda a rastrear:")
    precio_tope = st.number_input("🎯 Precio Máximo Permitido (Tope S/.)", min_value=1.0, step=5.0)

    # Armamos el Identificador Único
    tienda_final = nueva_tienda_input if nueva_tienda_input else tienda_sel
    cat_final = nueva_cat_input if nueva_cat_input else cat_sel
    nombre_limpio = nombre_prod.strip().replace(" ", "_").lower() if nombre_prod else "producto"
    talla_limpia = talla_sel.strip() if talla_sel else "todas"
    
    nuevo_identificador = f"{tienda_final}-{cat_final}-{nombre_limpio}-{talla_limpia}"

    # BOTÓN GUARDAR CON MENSAJE DE CONFIRMACIÓN
    if st.button("💥 GUARDAR ENLACE EN LA NUBE", use_container_width=True):
        if url_radar:
            datos_radar = {
                "identificador": nuevo_identificador,
                "url": url_radar,
                "precio_max": precio_tope
            }
            try:
                # Insertar o actualizar si ya existe el identificador (Upsert)
                supabase.table("radares").upsert(datos_radar).execute()
                st.success(f"🎉 ¡ÉXITO TOTAL! El producto '{nombre_prod}' ha sido registrado en el radar correctamente.")
                st.cache_data.clear() # Limpia la caché para actualizar la tabla rápido
                st.rerun()
            except Exception as e:
                st.error(f"❌ Error de conexión con Supabase: {e}")
        else:
            st.warning("⚠️ Por favor ingresa una URL válida antes de guardar.")

    st.markdown("---")
    
    # ⚙️ SECCIÓN INFERIOR: MODIFICAR O BORRAR ENLACES VIEJOS
    st.subheader("⚙️ Modificar o Eliminar Radares Activos")
    if not df_radares.empty:
        for idx, row in df_radares.iterrows():
            with st.container():
                st.write(f"🏷️ **ID:** `{row['identificador']}` | 🎯 **Tope:** S/.{row['precio_max']:.2f}")
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("✏️ Cargar para Modificar", key=f"mod_{idx}", use_container_width=True):
                        st.info("Variables cargadas arriba. Ajusta los precios o textos y presiona 'GUARDAR EN LA NUBE'.")
                with col_btn2:
                    if st.button("🗑️ Borrar Radar", key=f"del_{idx}", use_container_width=True):
                        try:
                            supabase.table("radares").delete().eq("identificador", row['identificador']).execute()
                            st.success("🗑️ ¡Radar eliminado con éxito de la base de datos!")
                            st.cache_data.clear()
                            st.rerun()
                        except:
                            st.error("No se pudo eliminar el elemento.")
    else:
        st.write("No hay radares registrados actualmente.")


# ==========================================
# 📊 PESTAÑA 2: VISUALIZACIÓN BASE DE DATOS (ORDEN ASCENDENTE/RECUPERACIÓN RECIENTE)
# ==========================================
with tab_Historial:
    st.subheader("📈 Monitoreo en Tiempo Real (Últimos ingresos primero)")
    
    try:
        # 🔄 CONSULTA OPTIMIZADA: Trae el historial ordenado de forma que el último ingresado salga arriba (en primera fila)
        # Cambiar 'id' por 'created_at' o 'fecha' si manejas esa columna en tu tabla 'historial_precios'
        res_historial = supabase.table("historial_precios").select("*").order("id", ascending=False).limit(50).execute()
        
        if res_historial.data:
            df_historial = pd.DataFrame(res_historial.data)
            
            # Formateamos bonito las columnas para que se entienda mejor en celular
            df_historial.rename(columns={
                "identificador": "📦 Identificador del Producto",
                "precio": "💵 Precio Registrado",
                "fecha": "📅 Fecha de Captura"
            }, inplace=True)
            
            # Mostramos la tabla interactiva de Streamlit
            st.dataframe(df_historial, use_container_width=True)
        else:
            st.info("ℹ️ Aún no hay registros de precios en el historial automático. Esperando el patrullaje de GitHub.")
    except Exception as e:
        st.error(f"No se pudo cargar la tabla de visualización: {e}")
