import os
import json
import time
from datetime import datetime, timezone, timedelta
from config import supabase
from scrapers import escanear_tienda
from notifications import enviar_alerta_telegram
from utils import safe_log, es_error_de_precio, safe_float

def revisar_ofertas(filtro_categoria="TODOS"):
    """
    Recorre los radares activos en Supabase, ejecuta el scraper correspondiente
    y guarda el producto con su nombre real en la tabla 'historial_precios'.
    """
    safe_log(f"🕵️‍♂️ Iniciando patrullaje con filtro: '{filtro_categoria}'", "info")
    
    try:
        query = supabase.table("radares").select("*")
        res_radares = query.execute()
        if not res_radares.data:
            return "No hay radares registrados en la base de datos."
        
        radares = res_radares.data
    except Exception as e:
        return f"Error leyendo radares desde Supabase: {e}"

    zona_peru = timezone(timedelta(hours=-5))
    fecha_actual = datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")
    total_ofertas_registradas = 0

    for radar in radares:
        url = radar.get("url", "").strip()
        precio_max = safe_float(radar.get("precio_max", 99999))
        identificador_base = radar.get("identificador", "GENERAL-OTROS-PRODUCTO-TODAS").upper()

        # Filtrar por categoría si no es 'TODOS'
        if filtro_categoria != "TODOS" and filtro_categoria not in identificador_base:
            continue

        parts = identificador_base.split("-")
        tienda = parts[0] if parts else "GENERAL"
        categoria = parts[1] if len(parts) > 1 else "OTROS"

        # Ejecutar el scraper correspondiente a la tienda
        productos_encontrados = escanear_tienda(tienda, url, precio_max)
        
        if not productos_encontrados:
            continue

        for prod in productos_encontrados:
            try:
                nombre_real = prod.get("nombre", "").strip()
                if not nombre_real or nombre_real == "NONE":
                    continue

                precio_oferta = safe_float(prod.get("precio"))
                precio_regular = safe_float(prod.get("precio_regular", precio_oferta))
                link = prod.get("link", url)
                imagen = prod.get("img", "")

                # Identificador único por producto para no duplicar
                link_clean = link.split("?")[0].rstrip("/")
                id_hash = str(abs(hash(link_clean)))[:8]
                identificador_producto = f"{tienda}-{categoria}-{nombre_real.replace(' ', '_')[:30]}-{id_hash}"

                # 📌 PAYLOAD CORREGIDO PARA SUPABASE
                datos_historial = {
                    "identificador": identificador_producto,
                    "nombre_producto": nombre_real,  # 👈 AQUÍ SE ASIGNA EL NOMBRE REAL
                    "precio": precio_oferta,
                    "precio_regular": precio_regular,
                    "imagen_producto": imagen,
                    "link_producto": link,
                    "fecha": fecha_actual
                }

                # Guardar en Supabase
                supabase.table("historial_precios").insert(datos_historial).execute()
                total_ofertas_registradas += 1

                # Evaluar y enviar alerta a Telegram si aplica
                es_bug, pct_desc = es_error_de_precio(precio_oferta, precio_regular, precio_oferta, categoria)
                if es_bug or precio_oferta <= precio_max:
                    enviar_alerta_telegram(
                        tienda=tienda,
                        nombre=nombre_real,
                        precio_oferta=precio_oferta,
                        precio_regular=precio_regular,
                        link=link,
                        imagen=imagen
                    )

            except Exception as ex_prod:
                safe_log(f"Error procesando producto individual: {ex_prod}", "warning")
                continue

    resumen = f"Patrullaje completado. Se registraron {total_ofertas_registradas} ofertas válidas."
    safe_log(f"✅ {resumen}", "success")
    return resumen
