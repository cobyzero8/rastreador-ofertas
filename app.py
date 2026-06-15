import streamlit as st
import json
import os
import pandas as pd

st.set_page_config(page_title="Radar Pro - Panel Central", layout="wide")

HISTORIAL_FILE = "historial_precios.json"
URLS_FILE = "urls.txt"

TOKEN_TELEGRAM = "8941748787:AAHBNGK3IFVzB-nEwm_HOkSxhtotplpplxI"
CHAT_ID_TELEGRAM = "8019752668"

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
                    meta = p[2].split("_")
                    # Resguardo seguro si la línea vieja no tiene categoría
                    cat_check = meta[1].lower() if len(meta) > 2 else "otros"
                    if cat_check not in categorias_disponibles:
                        categorias_disponibles.append(cat_check)

    categoria_seleccionada = st.selectbox("🔍 Filtrar visualización por Categoría:", categorias_disponibles)

    if os.path.exists(HISTORIAL_FILE):
        try:
            with open(HISTORIAL_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                lista = []
                for id_prod, hist in data.items():
                    parts = id_prod.split("_")
                    
                    # Control y blindaje estricto de índices para el Dashboard
                    tienda_txt = parts[0] if len(parts) > 0 else "N/A"
                    if len(parts) >= 4:
                        cat_txt = parts[1]
                        prod_txt = parts[2].replace("-", " ")
                        talla_txt = parts[3]
                    else:
                        cat_txt = "otros"
                        prod_txt = parts[1].replace("-", " ") if len(parts) > 1 else "N/A"
                        talla_txt = parts[2] if len(parts) > 2 else "N/A"
                    
                    clave_link = f"{tienda_txt}_{cat_txt}_{prod_txt.replace(' ', '-')}_{talla_txt}"
                    link_final = links_mapeados.get(clave_link, "#")
                    if link_final == "#" and links_mapeados:
                        # Búsqueda de respaldo por si el ID cambió de formato
                        for k, v in links_mapeados.items():
                            if prod_txt.replace(" ", "-") in k:
                                link_final = v
                                break

                    if categoria_seleccionada != "Todos" and cat_txt.lower() != categoria_seleccionada.lower():
                        continue

                    lista.append({
                        "Tienda": tienda_txt.upper().replace("-", " "),
                        "Categoría": cat_txt.upper(),
                        "Producto": prod_txt,
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
            categoria = st.selectbox("Categoría del Objeto", ["Zapatillas", "Polos", "Poleras", "Casacas", "Perfumes", "Shampoo", "Otros"])
        with c2:
            nombre = st.text_input("Nombre del producto (Usa guiones, ej: Perfume-Bleu-Intense)")
            url = st.text_input("URL exacta del artículo")
        with c3:
            talla = st.text_input("Talla/Volumen (Ej: 9.5US, M, 100ml)")
            precio_max = st.number_input("Precio máximo (Tope S/.)", value=100, min_value=1)
            
        st.write("###")
        if st.button("💾 GUARDAR ARTÍCULO CLASIFICADO", type="primary", use_container_width=True):
            if nombre and url:
                nombre_limpio = nombre.replace(" ", "-").strip()
                cat_limpia = categoria.lower().strip()
                tienda_limpia = tienda.replace(" ", "-").strip()
                
                nueva_linea = f"{url},{precio_max},{tienda_limpia}_{cat_limpia}_{nombre_limpio}_{talla}\n"
                
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
                    url_display = partes[0]
                    precio_display = partes[1]
                    meta_parts = partes[2].split("_")
                    
                    # --- ESCUDO ANTI INDICE FUERA DE RANGO ---
                    tnd = meta_parts[0].upper().replace("-", " ")
                    
                    # Si tiene el nuevo formato de 4 partes usa la estructura normal
                    if len(meta_parts) >= 4:
                        cat = meta_parts[1].upper()
                        prod = meta_parts[2].replace("-", " ")
                        tll = meta_parts[3]
                    else:
                        # Si es una línea antigua de 3 partes, le asigna "OTROS" automáticamente
                        cat = "OTROS"
                        prod = meta_parts[1].replace("-", " ") if len(meta_parts) > 1 else "N/A"
                        tll = meta_parts[2] if len(meta_parts) > 2 else "N/A"
                    
                    col_info, col_btn = st.columns([8, 2])
                    with col_info:
                        st.markdown(f"**{index + 1}. [{tnd}]** {prod} | Categoría: `{cat}` | Talla: `{tll}` | Tope: `S/. {precio_display}`")
                    with col_btn:
                        if st.button(f"🗑️ Eliminar", key=f"del_{index}", type="secondary", use_container_width=True):
                            lineas.pop(index)
                            with open(URLS_FILE, "w", encoding="utf-8") as f_web:
                                for l_restante in lineas:
                                    f_web.write(l_restante + "\n")
                            st.toast("🗑️ Artículo eliminado del radar con éxito.")
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
