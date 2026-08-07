import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta

def registrar_resultado_salud(supabase_client, tienda, total_productos, url_origen=""):
    """
    Registra o actualiza el estado de salud de un scraper en la tabla 'health_checks'.
    """
    if not supabase_client:
        return

    zona_peru = timezone(timedelta(hours=-5))
    fecha_actual = datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")
    tienda_key = tienda.strip().upper()

    try:
        res = supabase_client.table("health_checks").select("*").eq("tienda", tienda_key).execute()
        
        if res and res.data and len(res.data) > 0:
            reg = res.data[0]
            fallos_act = reg.get("fallos_consecutivos", 0)
            
            if total_productos > 0:
                fallos_act = 0
                estado = "OPERATIVO"
            else:
                fallos_act += 1
                estado = "CAIDO" if fallos_act >= 3 else "ADVERTENCIA"

            datos_update = {
                "fallos_consecutivos": fallos_act,
                "ultimos_productos_count": total_productos,
                "estado": estado,
                "ultimo_escaneo": fecha_actual
            }
            supabase_client.table("health_checks").update(datos_update).eq("tienda", tienda_key).execute()
        else:
            estado = "OPERATIVO" if total_productos > 0 else "CAIDO"
            datos_insert = {
                "tienda": tienda_key,
                "fallos_consecutivos": 0 if total_productos > 0 else 1,
                "ultimos_productos_count": total_productos,
                "estado": estado,
                "ultimo_escaneo": fecha_actual
            }
            supabase_client.table("health_checks").insert(datos_insert).execute()
            
    except Exception as e:
        print(f"⚠️ Error actualizando health_checks para {tienda_key}: {e}")


def renderizar_dashboard_salud(supabase_client):
    """
    Renderiza el panel de diagnóstico leyendo exactamente los campos de 'health_checks'.
    """
    st.title("🏥 Centro de Mando: Salud de Scrapers")
    st.caption("⚡ *Diagnóstico y rendimiento en vivo de los motores de extracción por tienda.*")
    st.write("---")

    if not supabase_client:
        st.error("🚨 No hay conexión configurada con Supabase.")
        return

    datos_salud = []
    try:
        res = supabase_client.table("health_checks").select("*").order("tienda").execute()
        if res and res.data:
            datos_salud = res.data
    except Exception as e:
        st.warning(f"⚠️ No se pudo consultar la tabla 'health_checks': {e}")

    if not datos_salud:
        st.info("ℹ️ La tabla 'health_checks' está vacía por el momento. Ejecuta un patrullaje para comenzar a poblar las métricas.")
        return

    # Cálculos estadísticos
    total_scrapers = len(datos_salud)
    operativos = sum(1 for item in datos_salud if item.get("ultimos_productos_count", 0) > 0 and item.get("fallos_consecutivos", 0) == 0)
    advertencias = sum(1 for item in datos_salud if item.get("ultimos_productos_count", 0) > 0 and item.get("fallos_consecutivos", 0) > 0)
    caidos = sum(1 for item in datos_salud if item.get("ultimos_productos_count", 0) == 0 or item.get("fallos_consecutivos", 0) >= 3)
    
    tasa_salud = (operativos / total_scrapers * 100) if total_scrapers > 0 else 0.0

    # KPI METRICS
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1: st.metric("🏬 Total Motores", total_scrapers)
    with m2: st.metric("🟢 Operativos", operativos)
    with m3: st.metric("⚠️ Advertencia", advertencias)
    with m4: st.metric("🔴 Caídos", caidos)
    with m5: st.metric("📈 Tasa de Salud", f"{tasa_salud:.0f}%")

    st.progress(tasa_salud / 100.0, text=f"Rendimiento global del sistema: {tasa_salud:.1f}% de motores respondiendo")
    st.write("---")

    # Filtros e interactividad
    col_filtro, col_search = st.columns([3, 2])
    with col_filtro:
        filtro_estado = st.radio(
            "Filtrar por estado:",
            ["TODOS", "🟢 OPERATIVOS", "⚠️ ADVERTENCIA", "🔴 CAÍDOS"],
            horizontal=True
        )
    with col_search:
        busqueda = st.text_input("🔍 Buscar tienda...", "").strip().upper()

    items_filtrados = []
    for item in datos_salud:
        tienda_nombre = str(item.get("tienda", "")).upper()
        fallos = item.get("fallos_consecutivos", 0)
        prods = item.get("ultimos_productos_count", 0)

        if prods > 0 and fallos == 0:
            est = "OPERATIVO"
        elif prods > 0 and fallos > 0:
            est = "ADVERTENCIA"
        else:
            est = "CAIDO"

        item["_est_calc"] = est

        if busqueda and busqueda not in tienda_nombre: continue
        if filtro_estado == "🟢 OPERATIVOS" and est != "OPERATIVO": continue
        if filtro_estado == "⚠️ ADVERTENCIA" and est != "ADVERTENCIA": continue
        if filtro_estado == "🔴 CAÍDOS" and est != "CAIDO": continue

        items_filtrados.append(item)

    st.markdown(f"### 📋 Listado de Motores ({len(items_filtrados)})")

    if not items_filtrados:
        st.warning("No hay scrapers que coincidan con el filtro seleccionado.")
        return

    # Tarjetas en 3 columnas
    cols = st.columns(3)
    for idx, item in enumerate(items_filtrados):
        col = cols[idx % 3]
        tienda = item.get("tienda", "OTRA").upper()
        fallos = item.get("fallos_consecutivos", 0)
        prods = item.get("ultimos_productos_count", 0)
        fecha = str(item.get("ultimo_escaneo", "Sin registro"))
        est = item.get("_est_calc", "OPERATIVO")

        if est == "OPERATIVO":
            badge_html = "<span style='background-color:#d4edda; color:#155724; padding:3px 8px; border-radius:10px; font-weight:bold; font-size:12px;'>🟢 OPERATIVO</span>"
        elif est == "ADVERTENCIA":
            badge_html = "<span style='background-color:#fff3cd; color:#856404; padding:3px 8px; border-radius:10px; font-weight:bold; font-size:12px;'>⚠️ ADVERTENCIA</span>"
        else:
            badge_html = "<span style='background-color:#f8d7da; color:#721c24; padding:3px 8px; border-radius:10px; font-weight:bold; font-size:12px;'>🔴 CAÍDO</span>"

        with col:
            with st.container(border=True):
                c_head1, c_head2 = st.columns([3, 2])
                with c_head1: st.markdown(f"#### `{tienda}`")
                with c_head2: st.markdown(badge_html, unsafe_allow_html=True)

                st.write("")
                col_i1, col_i2 = st.columns(2)
                with col_i1:
                    st.markdown(f"📦 **Productos:** `{prods}`")
                with col_i2:
                    st.markdown(f"🚨 **Fallos:** `{fallos}`")
                
                st.caption(f"🕒 **Última ejecución:** {fecha.split('T')[0] if 'T' in fecha else fecha[:19]}")

    st.write("---")

    # Tabla en vista completa
    with st.expander("📄 Ver Matriz Completa de Auditoría", expanded=False):
        df_health = pd.DataFrame(datos_salud)
        if not df_health.empty:
            cols_def = [c for c in ["tienda", "estado", "ultimos_productos_count", "fallos_consecutivos", "ultimo_escaneo"] if c in df_health.columns]
            st.dataframe(
                df_health[cols_def],
                column_config={
                    "tienda": "🏪 Tienda",
                    "estado": "🏷️ Estado",
                    "ultimos_productos_count": "📦 Prod. Capturados",
                    "fallos_consecutivos": "🚨 Fallos Consecutivos",
                    "ultimo_escaneo": "📅 Última Fecha"
                },
                use_container_width=True,
                hide_index=True
            )
