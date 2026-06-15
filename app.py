import streamlit as st
import json
import os
import pandas as pd

st.set_page_config(page_title="Radar Pro - Panel Central", layout="wide")

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

st.sidebar.title("💥 Radar Familiar Pro")
menu = st.sidebar.radio("Selecciona una opción:", ["📈 Ver Dashboard", "🛠️ Gestionar Enlaces Pro", "💥 Forzar Escaneo"])

# --- OPCIÓN 1: DASHBOARD CON BOTONES DE FILTRO ---
if menu == "📈 Ver Dashboard":
    st.title("🕵️‍♂️ Radar Familiar Pro")
    st.subheader("📊 Dashboard de Artículos")
    
    links_mapeados = {}
    categorias_disponibles = ["Todos"]
    
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            for line in f.readlines():
                p = line.strip().split(",")
                if len(p) >= 3:
                    links_mapeados[p[2]] = p[0]
                    meta = p[2].split("-")
                    cat_check = meta[1].upper() if len(meta) > 1 else "OTROS"
                    if cat_check not in categorias_disponibles:
                        categorias_disponibles.append(cat_check)

    categoria_seleccionada = st.selectbox("🔍 Filtrar visualización por Categoría:", categorias_disponibles)

    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                lista = []
                for id_prod, hist in data.items():
                    parts = id_prod.split("-")
                    
                    tienda_txt = parts[0] if len(parts) > 0 else "N/A"
                    cat_txt = parts[1] if len(parts) > 1 else "OTROS"
                    prod_txt = parts[2] if len(parts) > 2 else "N/A"
                    talla_txt = parts[3] if len(parts) > 3 else "N/A"
                    
                    clave_link = f"{tienda_txt}-{cat_txt}-{prod_txt}-{talla_txt}"
                    link_final = links_mapeados.get(clave_link, "#")
                    
                    if link_final == "#" and links_mapeados:
                        for k, v in links_mapeados.items():
                            if prod_txt in k:
                                link_final = v
                                break

                    if categoria_seleccionada != "Todos" and cat_txt.upper() != categoria_seleccionada.upper():
                        continue

                    lista.append({
                        "Tienda": tienda_txt.upper(),
                        "Categoría": cat_txt.upper(),
                        "Producto": prod_txt.replace("_", " "),
                        "Talla": talla_txt,
                        "Precio Final": f"S/. {list(hist.values())[-1]}" if hist else "N/A",
                        "Link de Compra": link_final
                    })
                
                df = pd.DataFrame(lista)
                if not df.empty:
                    st.data_editor(
                        df,
                        column_config={"Link de Compra": st.column_config.LinkColumn("Compra Directa")},
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("No hay productos en esta categoría.")
        except Exception as e:
            st.error(f"Error al cargar el historial: {e}")
    else:
        st.info("No hay datos históricos disponibles.")

# --- OPCIÓN 2: GESTIONAR ENLACES PRO ---
elif menu == "🛠️ Gestionar Enlaces Pro":
    st.title("🛠️ Gestionar Enlaces Pro")
    
    with st.container(border=True):
        st.write("### 📝 Registrar nuevo artículo clasificado")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            tienda = st.selectbox("Tienda", [
                "Adidas", "Falabella", "Marathon", "Ripley", "Puma", "Nike", 
                "Natura", "Mifarma", "Inkafarma", "Mercado Libre", "Triathlon", "JBL", "Samsung",
                "Lbel", "Esika", "Cyzone"
            ])
            # AQUÍ AGREGUÉ TUS NUEVAS CATEGORÍAS MANUALMENTE
            categoria = st.selectbox("Categoría del Objeto", [
                "Zapatillas", "Polos", "Poleras", "Casacas", "Pantalon deportivo", 
                "Perfumes", "Shampoo", "Desodorante", "Jabon", "Otros"
            ])
        with c2:
            nombre = st.text_input("Nombre del producto (Usa guiones abajo si deseas, ej: Short_Negro)")
            url = st.text_input("URL exacta del artículo")
        with c3:
            talla = st.text_input("Talla/Volumen (Ej: 9.5US, M, 100ml)")
            precio_max = st.number_input("Precio máximo (Tope S/.)", value=100, min_value=1)
            
        st.write("###")
        if st.button("💾 GUARDAR ARTÍCULO CLASIFICADO", type="primary", use_container_width=True):
            if nombre and url:
                nombre_limpio = nombre.replace(" ", "_").strip()
                cat_limpia = categoria.upper().strip()
                tienda_limpia = tienda.upper().strip()
                talla_limpia = talla.strip() if talla.strip() else "TODAS"
                
                nueva_linea = f"{url},{precio_max},{tienda_limpia}-{cat_limpia}-{nombre_limpio}-{talla_limpia}\n"
                
                with open(URLS_FILE, "a", encoding="utf-8") as f:
                    f.write(nueva_linea)
                    
                st.toast(f"✅ ¡{tienda} - {categoria} guardado correctamente!")
                st.rerun()
            else:
                st.error("❌ Completa los campos requeridos (Nombre y URL).")

    st.write("---")
    st.subheader("📋 Panel de Control de Radares (Modificar / Eliminar)")
    
    if os.path.exists(URLS_FILE):
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            lineas = [l.strip() for l in f.readlines() if l.strip()]
            
        if lineas:
            for index, linea in enumerate(lineas):
                partes = linea.split(",")
                if len(partes) >= 3:
                    precio_display = partes[1]
                    meta_parts = partes[2].split("-")
                    
                    tnd = meta_parts[0] if len(meta_parts) > 0 else "GENERAL"
                    cat = meta_parts[1] if len(meta_parts) > 1 else "OTROS"
                    prod = meta_parts[2].replace("_", " ") if len(meta_parts) > 2 else "PRODUCTO"
                    tll = meta_parts[3] if len(meta_parts) > 3 else "N/A"
                    
                    col_info, col_btn = st.columns([8, 2])
                    with col_info:
                        st.markdown(f"**{index + 1}. [{tnd}]** {prod} | Categoría: `{cat}` | Talla: `{tll}` | Tope: `S/. {precio_display}`")
                    with col_btn:
                        if st.button(f"🗑️ Eliminar", key=f"del_{index}", type="secondary", use_container_width=True):
                            lineas.pop(index)
                            with open(URLS_FILE, "w", encoding="utf-8") as f_web:
                                for l_restante in lineas:
                                    f_web.write(l_restante + "\n")
                            st.toast("🗑️ Artículo eliminado con éxito.")
                            st.rerun()
                st.write("")
        else:
            st.info("No hay artículos en tu lista de monitoreo.")
    else:
        st.info("Aún no se ha creado el archivo de enlaces.")

# --- OPCIÓN 3: FORZAR ESCANEO ---
elif menu == "💥 Forzar Escaneo":
    st.title("💥 Forzar Escaneo Automático")
    st.write("Presiona el botón para escanear. Las ofertas llegarán organizadas con botones de acción directa en Telegram.")
    
    contenedor_mensaje = st.empty()
    if st.button("💥 INICIAR ESCANEO INTENSIVO", type="primary", use_container_width=True):
        contenedor_mensaje.info("⏳ Ejecutando orden de rastreo por categorías... Por favor espera.")
        try:
            from scraper import revisar_ofertas
            revisar_ofertas()
            contenedor_mensaje.success("✅ ¡Escaneo completado! Revisa tu Telegram y el Dashboard.")
            st.rerun()
        except Exception as e:
            contenedor_mensaje.error(f"❌ Error: {e}")
