import os
import json
import time
from datetime import datetime, timezone, timedelta

from config import supabase
from scrapers import escanear_tienda
from notifications import enviar_alerta_telegram
from health_monitor import registrar_resultado_salud
from utils import safe_log, es_error_de_precio, safe_float

def revisar_ofertas(filtro_categoria="TODOS"):
    """
    Recorre los radares activos en Supabase, ejecuta el scraper correspondiente,
    actualiza el historial de precios y registra el estado de salud de los motores.
    
    Lógica de negocio:
    1. Artículo Nuevo: Se inserta en 'historial_precios' + Notificación Telegram.
    2. Precio Menor: Se actualizan precio, precio regular y hora + Notificación Telegram.
    3. Precio Igual o Mayor: Solo se actualiza la hora (silencioso, sin Telegram).
    """
    # 1. Validar conexión previa con Supabase
    if not supabase:
        safe_log("🛑 No hay conexión con Supabase. Revisa SUPABASE_URL y SUPABASE_KEY en los Secrets.", "error")
        return "Fallo de conexión con Supabase: Credenciales faltantes."

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
    total_ofertas_notificadas = 0

    for radar in radares:
        url = radar.get("url", "").strip()
        precio_max = safe_float(radar.get("precio_max", 99999))
        identificador_base = radar.get("identificador", "GENERAL-OTROS-PRODUCTO-TODAS").upper()

        if filtro_categoria != "TODOS" and filtro_categoria not in identificador_base:
            continue

        parts = identificador_base.split("-")
        tienda = parts[0] if parts else "GENERAL"
        categoria = parts[1] if len(parts) > 1 else "OTROS"

        safe_log(f"🔍 Escaneando radar [{tienda}] -> {url}", "info")
        
        # 2. Ejecutar Scraper
        productos_encontrados = escanear_tienda(tienda, url, precio_max)
        
        # 3. Actualizar la tabla de salud de scrapers
        cant_prods = len(productos_encontrados) if productos_encontrados else 0
        registrar_resultado_salud(supabase, tienda, cant_prods, url)

        if not productos_encontrados:
            continue

        # 4. Procesar productos extraídos
        for prod in productos_encontrados:
            try:
                nombre_real = prod.get("nombre", "").strip()
                if not nombre_real or nombre_real == "NONE":
                    continue

                precio_oferta = safe_float(prod.get("precio"))
                precio_regular = safe_float(prod.get("precio_regular", precio_oferta))
                link = prod.get("link", url)
                imagen = prod.get("img", "")

                if precio_oferta <= 0:
                    continue

                # 5. Buscar en Supabase si el producto ya existe por su URL (link_producto)
                res_existente = supabase.table("historial_precios")\
                    .select("id, precio, precio_regular, imagen_producto")\
                    .eq("link_producto", link)\
                    .limit(1)\
                    .execute()

                if not res_existente.data:
                    # -------------------------------------------------------------
                    # 🆕 CASO 1: ARTÍCULO NUEVO -> Inserta en BD + Notifica Telegram
                    # -------------------------------------------------------------
                    datos_insert = {
                        "identificador": f"{tienda}-{categoria}",
                        "nombre_producto": nombre_real,
                        "precio": precio_oferta,
                        "precio_regular": precio_regular,
                        "imagen_producto": imagen,
                        "link_producto": link,
                        "fecha": fecha_actual
                    }
                    supabase.table("historial_precios").insert(datos_insert).execute()
                    
                    enviar_alerta_telegram(
                        tienda=tienda,
                        nombre=nombre_real,
                        precio_oferta=precio_oferta,
                        precio_regular=precio_regular,
                        link=link,
                        imagen=imagen
                    )
                    total_ofertas_notificadas += 1
                    safe_log(f"🆕 Producto nuevo registrado y notificado: {nombre_real} (S/. {precio_oferta:.2f})", "success")

                else:
                    reg_guardado = res_existente.data[0]
                    precio_guardado = safe_float(reg_guardado.get("precio"))
                    id_bd = reg_guardado.get("id")

                    if precio_oferta < precio_guardado:
                        # -------------------------------------------------------------
                        # 📉 CASO 2: PRECIO MENOR -> Actualiza Precio/Fecha + Telegram
                        # -------------------------------------------------------------
                        datos_update = {
                            "nombre_producto": nombre_real,
                            "precio": precio_oferta,
                            "precio_regular": max(precio_regular, precio_guardado),
                            "imagen_producto": imagen if imagen else reg_guardado.get("imagen_producto", ""),
                            "fecha": fecha_actual
                        }
                        supabase.table("historial_precios").update(datos_update).eq("id", id_bd).execute()

                        enviar_alerta_telegram(
                            tienda=tienda,
                            nombre=nombre_real,
                            precio_oferta=precio_oferta,
                            precio_regular=precio_guardado,
                            link=link,
                            imagen=imagen
                        )
                        total_ofertas_notificadas += 1
                        safe_log(f"📉 Baja de precio (S/. {precio_guardado:.2f} ➔ S/. {precio_oferta:.2f}): {nombre_real}", "success")

                    else:
                        # -------------------------------------------------------------
                        # 🕒 CASO 3: PRECIO IGUAL O MAYOR -> Solo actualiza fecha/hora
                        # -------------------------------------------------------------
                        datos_update = {
                            "fecha": fecha_actual
                        }
                        supabase.table("historial_precios").update(datos_update).eq("id", id_bd).execute()
                        safe_log(f"🕒 Precio constante (S/. {precio_oferta:.2f}). Horario actualizado para: {nombre_real}", "info")

            except Exception as ex_prod:
                safe_log(f"⚠️ Error procesando artículo individual: {ex_prod}", "warning")
                continue

    resumen = f"Patrullaje finalizado con éxito. Se notificaron {total_ofertas_notificadas} novedades/bajas de precio."
    safe_log(f"✅ {resumen}", "success")
    return resumen
