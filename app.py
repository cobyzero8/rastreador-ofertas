import streamlit as st
import pandas as pd
import json
import os

def mostrar_dashboard():
    st.subheader("📊 Monitoreo de Ofertas en Tiempo Real")
    
    if not os.path.exists("historial_precios.json"):
        st.info("⏳ Base de datos inicializada. Esperando que el robot cargue información.")
        return

    with open("historial_precios.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    
    # Convertimos los datos del historial a un formato que Streamlit pueda mostrar en tabla
    lista_productos = []
    for id_prod, historico in data.items():
        tienda, cat, talla, nombre = id_prod.split("_", 3)
        ultimos_precios = list(historico.values())
        precio_actual = ultimos_precios[-1]
        
        lista_productos.append({
            "Tienda": tienda.upper(),
            "Producto": nombre.replace("_", " "),
            "Talla": talla,
            "Precio": f"S/. {precio_actual}",
            "Historial": ultimos_precios
        })
    
    df = pd.DataFrame(lista_productos)
    
    # Creamos una columna interactiva con enlace para comprar
    st.dataframe(
        df,
        column_config={
            "Precio": st.column_config.TextColumn("Precio Actual"),
            "Historial": st.column_config.LineChartColumn("Tendencia (Últimos días)")
        },
        hide_index=True,
        use_container_width=True
    )
    
    st.write("---")
    st.write("👉 *Puedes ver el detalle histórico de cada producto en la tabla superior.*")
