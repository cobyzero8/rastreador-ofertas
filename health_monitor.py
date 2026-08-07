import streamlit as st
import pandas as pd
from datetime import datetime, timezone, timedelta

def registrar_resultado_salud(supabase_client, tienda, total_productos, url_origen=""):
    """
    Registra o actualiza el estado de salud de un scraper en la tabla 'salud_scrapers'.
    """
    if not supabase_client:
        return

    zona_peru = timezone(timedelta(hours=-5))
    fecha_actual = datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")
    tienda_key = tienda.strip().upper()

    try:
        res = supabase_client.table("salud_scrapers").select("*").eq("tienda", tienda_key).execute()
        
        if res and res.data and len(res.data) > 0:
            reg = res.data[0]
            fallos_act = reg.get("fallos", 0)
            exitos_act = reg.get("exitos", 0)
            
            if total_productos > 0:
                exitos_act += 1
                fallos_act = 0
                estado = "OPERATIVO"
            else:
                fallos_act += 1
                estado = "CAIDO" if fallos_act >= 3 else "ADVERTENCIA"

            datos_update = {
                "fallos": fallos_act,
                "exitos": exitos_act,
                "productos_ultimo_escaneo": total_productos,
                "estado": estado,
                "ultimo_escaneo": fecha_actual,
                "url_origen": url_origen
            }
            supabase_client.table("salud_scrapers").update(datos_update).eq("tienda", tienda_key).execute()
        else:
            estado = "OPERATIVO" if total_productos > 0 else "CAIDO"
            datos_insert = {
                "tienda": tienda_key,
                "fallos": 0 if total_productos > 0 else 1,
                "exitos": 1 if total_productos > 0 else 0,
                "productos_ultimo_escaneo": total_productos,
                "estado": estado,
                "ultimo_escaneo": fecha_actual,
                "url_origen": url_origen
            }
            supabase_client.table("salud_scrapers").insert(datos_insert).execute()
            
    except Exception as e:
        print(f"⚠️ Error actualizando salud_scrapers para {tienda_key}: {e}")


def renderizar_dashboard_salud(supabase_client):
    """
    Renderiza el panel de diagnóstico técnico con diseño de tarjetas en cuadrícula,
    métricas clave y filtros por estado.
    """
    st.title("🏥 Centro de Mando: Salud de Scrapers")
    st.caption("⚡ *Diagnóstico y rendimiento en vivo de los motores de extracción por tienda.*")
    st.write("---")

    if not supabase_client:
        st.error("🚨 No hay conexión configurada con Supabase.")
        return

    datos_salud = []
    try:
        res = supabase_client.table("salud_scrapers").select("*").order("tienda").execute()
        if res and res.data:
            datos_salud = res.data
    except Exception as e:
        st.warning(f"⚠️ No se pudo consultar la tabla 'salud_scrapers': {e}")

    if not datos_salud:
        st.info("ℹ️ No hay métricas registradas aún. Ejecuta un patrullaje para calcular el estado de los motores.")
        return

    # Cálculos estadísticos
    total_scrapers = len(datos_salud)
    operativos = sum(1 for item in datos_salud if item.get("productos_ultimo_escaneo", 0) > 0 and item.get("fallos", 0) == 0)
    advertencias = sum(1 for item in datos_salud if item.get("productos_ultimo_escaneo", 0) > 0 and item.get("fallos", 0) > 0)
    caidos = sum(1 for item in datos_salud if item.get("productos_ultimo_escaneo", 0) == 0 or item.get("fallos", 0) >= 3)
    
    tasa_salud = (operativos / total_scrapers * 100) if total_scrapers > 0 else 0.0

    # 📊 KPI METRICS HEADERS
    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("🏬 Total Motores", total_scrapers)
    with m2:
        st.metric("🟢 Operativos", operativos)
    with m3:
        st.metric("⚠️ Advertencia", advertencias)
    with m4:
        st.metric("🔴 Caídos", caidos)
    with m5:
        st.metric("📈 Tasa de Salud", f"{tasa_salud:.0f}%")

    st.progress(tasa_salud / 100.0, text=f"Rendimiento global del sistema: {tasa_salud:.1f}% de motores respondiendo correctamente")
    st.write("---")

    # 🔍 FILTROS E INTERACTIVIDAD
    col_filtro, col_search = st.columns([3, 2])
    with col_filtro:
        filtro_estado = st.radio(
            "Filtrar por estado:",
            ["TODOS", "🟢 OPERATIVOS", "⚠️ ADVERTENCIA", "🔴 CAÍDOS"],
            horizontal=True
        )
    with col_search:
        busqueda = st.text_input("🔍 Buscar tienda...", "").strip().upper()

    # Procesamiento y filtrado de la lista
    items_filtrados = []
    for item in datos_salud:
        tienda_nombre = str(item.get("tienda", "")).upper()
        fallos = item.get("fallos", 0)
        prods = item.get("productos_ultimo_escaneo", 0)

        if prods > 0 and fallos == 0:
            est = "OPERATIVO"
        elif prods > 0 and fallos > 0:
            est = "ADVERTENCIA"
        else:
            est = "CAIDO"

        item["_est_calc"] = est

        if busqueda and busqueda not in tienda_nombre:
            continue
        if filtro_estado == "🟢 OPERATIVOS" and est != "OPERATIVO":
            continue
        if filtro_estado == "⚠️ ADVERTENCIA" and est != "ADVERTENCIA":
            continue
        if filtro_estado == "🔴 CAÍDOS" and est != "CAIDO":
            continue

        items_filtrados.append(item)

    st.markdown(f"### 📋 Listado de Motores ({len(items_filtrados)})")

    if not items_filtrados:
        st.warning("No hay scrapers que coincidan con el filtro seleccionado.")
        return

    # 🎴 GRID DE TARJETAS EN 3 COLUMNAS
    cols = st.columns(3)
    for idx, item in enumerate(items_filtrados):
        col = cols[idx % 3]
        tienda = item.get("tienda", "OTRA").upper()
        fallos = item.get("fallos", 0)
        prods = item.get("productos_ultimo_escaneo", 0)
        exitos = item.get("exitos", 0)
        fecha = item.get("ultimo_escaneo", "Sin registro")
        url_orig = item.get("url_origen", "")
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
                with c_head1:
                    st.markdown(f"#### `{tienda}`")
                with c_head2:
                    st.markdown(badge_html, unsafe_allow_html=True)

                st.write("")
                col_i1, col_i2 = st.columns(2)
                with col_i1:
                    st.markdown(f"📦 **Productos:** `{prods}`")
                    st.markdown(f"✅ **Éxitos:** `{exitos}`")
                with col_i2:
                    st.markdown(f"🚨 **Fallos:** `{fallos}`")
                    st.caption(f"🕒 **Fecha:** {fecha.split(' ')[1] if ' ' in str(fecha) else fecha}")

                if url_orig:
                    st.markdown(f"🔗 [🌐 Probar URL Externa]({url_orig})")

    st.write("---")

    # 📊 TABLA DETALLADA DE AUDITORÍA TÉCNICA
    with st.expander("📄 Ver Matriz Completa de Auditoría", expanded=False):
        df_health = pd.DataFrame(datos_salud)
        if not df_health.empty:
            cols_def = [c for c in ["tienda", "estado", "productos_ultimo_escaneo", "fallos", "exitos", "ultimo_escaneo", "url_origen"] if c in df_health.columns]
            st.dataframe(
                df_health[cols_def],
                column_config={
                    "tienda": "🏪 Tienda",
                    "estado": "🏷️ Estado",
                    "productos_ultimo_escaneo": "📦 Prod. Capturados",
                    "fallos": "🚨 Conteo Fallos",
                    "exitos": "✅ Conteo Éxitos",
                    "ultimo_escaneo": "📅 Última Fecha",
                    "url_origen": st.column_config.LinkColumn("🔗 Enlace Target")
                },
                use_container_width=True,
                hide_index=True
            )
