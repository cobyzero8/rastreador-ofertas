import os
import json
import time
from datetime import datetime, timezone, timedelta
from config import supabase
from scrapers import escanear_tienda
from notifications import enviar_alerta_telegram
from utils import safe_log, es_error_de_precio, safe_float

def revisar_ofertas(filtro_categoria="TODOS"):
    if not supabase:
        safe_log("🛑 No hay conexión con Supabase. Revisa que SUPABASE_URL y SUPABASE_KEY estén configuradas en los Secrets de GitHub.", "error")
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

                link_clean = link.split("?")[0].rstrip("/")
                id_hash = str(abs(hash(link_clean)))[:8]
                identificador_producto = f"{tienda}-{categoria}-{nombre_real.replace(' ', '_')[:30]}-{id_hash}"

                # 🔍 Consultar si el artículo ya existe en Supabase por su URL
                res_existente = supabase.table("historial_precios")\
                    .select("*")\
                    .eq("link_producto", link)\
                    .limit(1)\
                    .execute()

                if not res_existente.data:
                    # 1. CASO: ARTÍCULO NUEVO -> Guarda en BD + Envía Notificación
                    datos_insert = {
                        "identificador": identificador_producto,
                        "nombre_producto": nombre_real,
                        "precio": precio_oferta,
                        "precio_regular": precio_regular,
                        "imagen_producto": imagen,
                        "link_producto": link,
                        "fecha": fecha_actual
                    }
                    supabase.table("historial_precios").insert(datos_insert).execute()
                    total_ofertas_notificadas += 1

                    enviar_alerta_telegram(
                        tienda=tienda,
                        nombre=nombre_real,
                        precio_oferta=precio_oferta,
                        precio_regular=precio_regular,
                        link=link,
                        imagen=imagen
                    )
                    safe_log(f"🆕 Producto nuevo registrado y notificado: {nombre_real}", "success")

                else:
                    reg_guardado = res_existente.data[0]
                    precio_guardado = safe_float(reg_guardado.get("precio"))
                    id_bd = reg_guardado.get("id")

                    if precio_oferta < precio_guardado:
                        # 2. CASO: PRECIO MENOR -> Actualiza Precio + Horario + Envía Notificación
                        datos_update = {
                            "precio": precio_oferta,
                            "precio_regular": max(precio_regular, precio_guardado),
                            "fecha": fecha_actual
                        }
                        if id_bd:
                            supabase.table("historial_precios").update(datos_update).eq("id", id_bd).execute()
                        else:
                            supabase.table("historial_precios").update(datos_update).eq("link_producto", link).execute()
                        
                        total_ofertas_notificadas += 1

                        enviar_alerta_telegram(
                            tienda=tienda,
                            nombre=nombre_real,
                            precio_oferta=precio_oferta,
                            precio_regular=precio_guardado,
                            link=link,
                            imagen=imagen
                        )
                        safe_log(f"📉 Baja de precio (S/. {precio_guardado:.2f} ➔ S/. {precio_oferta:.2f}): {nombre_real}", "success")

                    else:
                        # 3. CASO: PRECIO IGUAL O MAYOR -> Solo modifica la fecha/horario, NO notifica
                        datos_update = {
                            "fecha": fecha_actual
                        }
                        if id_bd:
                            supabase.table("historial_precios").update(datos_update).eq("id", id_bd).execute()
                        else:
                            supabase.table("historial_precios").update(datos_update).eq("link_producto", link).execute()

                        safe_log(f"🕒 Precio constante/mayor. Solo se actualizó el horario para: {nombre_real}", "info")

            except Exception as ex_prod:
                safe_log(f"Error procesando artículo: {ex_prod}", "warning")
                continue

    resumen = f"Patrullaje finalizado. Se notificaron {total_ofertas_notificadas} cambios/novedades de precios."
    safe_log(f"✅ {resumen}", "success")
    return resumen
