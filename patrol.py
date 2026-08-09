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
    Recorre los radares en Supabase, actualiza el historial de precios
    y notifica únicamente si hay un descuento real o una baja de precio.
    """
    if not supabase:
        safe_log("🛑 No hay conexión con Supabase. Revisa SUPABASE_URL y SUPABASE_KEY.", "error")
        return "Fallo de conexión con Supabase: Credenciales faltantes."

    safe_log(f"🕵️‍♂️ Iniciando patrullaje con filtro: '{filtro_categoria}'", "info")
    
    try:
        query = supabase.table("radares").select("*")
        res_radares = query.execute()
        if not res_radares.data:
            safe_log("⚠️ No se encontraron radares en la tabla 'radares'.", "warning")
            return "No hay radares registrados en la base de datos."
        
        radares = res_radares.data
    except Exception as e:
        safe_log(f"🚨 Error leyendo la tabla 'radares': {e}", "error")
        return f"Error leyendo radares desde Supabase: {e}"

    zona_peru = timezone(timedelta(hours=-5))
    fecha_actual = datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")
    total_ofertas_notificadas = 0
    total_productos_procesados = 0

    for radar in radares:
        url = radar.get("url", "").strip()
        precio_max = safe_float(radar.get("precio_max", 999999))
        identificador_base = str(radar.get("identificador", "GENERAL-OTROS-PRODUCTO-TODAS")).upper()

        if not url or not url.startswith("http"):
            continue

        if filtro_categoria != "TODOS" and filtro_categoria not in identificador_base:
            continue

        parts = identificador_base.split("-")
        tienda = parts[0] if parts else "GENERAL"
        categoria = parts[1] if len(parts) > 1 else "OTROS"

        safe_log(f"🔍 Escaneando radar [{tienda}] -> {url} (Límite S/. {precio_max:.2f})", "info")
        
        productos_encontrados = []
        try:
            productos_encontrados = escanear_tienda(url, tienda, precio_max)
        except Exception as ex_scrap:
            safe_log(f"❌ Error durante la extracción en {tienda}: {ex_scrap}", "error")
        
        cant_prods = len(productos_encontrados) if productos_encontrados else 0
        safe_log(f"📊 [{tienda}] Productos válidos extraídos: {cant_prods}", "info")

        try:
            registrar_resultado_salud(supabase, tienda, cant_prods, url)
        except Exception as ex_health:
            safe_log(f"⚠️ No se pudo registrar salud para {tienda}: {ex_health}", "warning")

        if not productos_encontrados:
            continue

        for prod in productos_encontrados:
            try:
                nombre_real = str(prod.get("nombre", "")).strip()
                if not nombre_real or nombre_real.upper() in ["NONE", "NULL", ""]:
                    continue

                precio_oferta = safe_float(prod.get("precio"))
                precio_regular = safe_float(prod.get("precio_regular", precio_oferta))
                link_prod = str(prod.get("link", url)).strip()
                imagen = str(prod.get("img", "")).strip()

                if precio_oferta <= 0 or not link_prod:
                    continue

                res_existente = supabase.table("historial_precios")\
                    .select("id, precio, precio_regular, nombre_producto, imagen_producto")\
                    .eq("link_producto", link_prod)\
                    .limit(1)\
                    .execute()

                if not res_existente.data:
                    # -------------------------------------------------------------
                    # 🆕 CASO 1: PRODUCTO NUEVO
                    # -------------------------------------------------------------
                    datos_insert = {
                        "identificador": f"{tienda}-{categoria}",
                        "nombre_producto": nombre_real,
                        "precio": precio_oferta,
                        "precio_regular": precio_regular,
                        "imagen_producto": imagen,
                        "link_producto": link_prod,
                        "fecha": fecha_actual
                    }
                    res_ins = supabase.table("historial_precios").insert(datos_insert).execute()
                    
                    if res_ins and res_ins.data:
                        total_productos_procesados += 1
                        
                        # 🚨 SOLO Notificar por Telegram si el producto nuevo tiene un descuento real
                        if precio_oferta < precio_regular:
                            enviar_alerta_telegram(
                                tienda=tienda,
                                nombre=nombre_real,
                                precio_oferta=precio_oferta,
                                precio_regular=precio_regular,
                                link=link_prod,
                                imagen=imagen,
                                tipo_alerta="NUEVA_OFERTA"
                            )
                            total_ofertas_notificadas += 1
                            safe_log(f"✨ Oferta nueva guardada y notificada: {nombre_real} (S/. {precio_oferta:.2f})", "success")
                        else:
                            safe_log(f"📦 Producto nuevo registrado silenciosamente (sin descuento): {nombre_real}", "info")

                else:
                    # -------------------------------------------------------------
                    # CASO 2: PRODUCTO EXISTENTE EN BD
                    # -------------------------------------------------------------
                    reg_guardado = res_existente.data[0]
                    precio_guardado = safe_float(reg_guardado.get("precio"))
                    id_bd = reg_guardado.get("id")

                    if precio_oferta < precio_guardado:
                        # 📉 BAJA DE PRECIO -> Actualizar y Notificar Telegram
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
                            link=link_prod,
                            imagen=imagen,
                            tipo_alerta="BAJA_PRECIO"
                        )
                        total_ofertas_notificadas += 1
                        total_productos_procesados += 1
                        safe_log(f"📉 Baja de precio (S/. {precio_guardado:.2f} ➔ S/. {precio_oferta:.2f}): {nombre_real}", "success")

                    else:
                        # 🕒 PRECIO IGUAL O MAYOR -> Solo actualizar fecha
                        datos_update = {"fecha": fecha_actual}
                        if not reg_guardado.get("nombre_producto"):
                            datos_update["nombre_producto"] = nombre_real

                        supabase.table("historial_precios").update(datos_update).eq("id", id_bd).execute()
                        total_productos_procesados += 1

            except Exception as ex_prod:
                safe_log(f"⚠️ Error procesando artículo: {ex_prod}", "warning")
                continue

    resumen = f"Patrullaje finalizado. Procesados: {total_productos_procesados} productos | Notificaciones enviadas: {total_ofertas_notificadas}."
    safe_log(f"✅ {resumen}", "success")
    return resumen
