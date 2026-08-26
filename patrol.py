import os
import json
import time
import logging
import requests
from datetime import datetime, timezone, timedelta

# Silenciar advertencias de Streamlit en ejecuciones CLI / GitHub Actions / Cron
os.environ["STREAMLIT_LOG_LEVEL"] = "error"
logging.getLogger("streamlit").setLevel(logging.ERROR)
logging.getLogger("streamlit.runtime.scriptrunner.script_runner").setLevel(logging.ERROR)

from config import supabase
from scrapers import escanear_tienda
from notifications import enviar_alerta_telegram
from health_monitor import registrar_resultado_salud
from utils import safe_log, es_error_de_precio, safe_float

# Configuración de horas mínimas entre escaneos por tienda (Protección de créditos)
TIENDAS_CON_ENFRIAMIENTO = {
    "JBL": 4,
    "ADIDAS": 4,
    "PLATANITOS": 4,
    "RIPLEY": 4,
    "SHOPSTAR": 4,
}


def cumple_filtro_categoria(filtro: str, identificador: str) -> bool:
    if not filtro or filtro == "TODOS":
        return True

    filtro_clean = str(filtro).upper().strip()
    ident_clean = str(identificador).upper().strip()

    diccionario_sinonimos = {
        "POLOS": ["POLO", "CAMISETA"],
        "ZAPATILLAS": ["ZAPATILLA", "CALZADO", "SNEAKER"],
        "PERFUMES": ["PERFUME", "COLONIA", "FRAGANCIA"],
        "CASACAS": ["CASACA", "POLERA", "JACKET", "HOODIE"],
        "SHORTS": ["SHORT", "BERMUDA"],
        "BUZOS": ["BUZO", "PANTALON", "JOGGER"],
        "MEDIAS": ["MEDIA", "MEDIAS", "CALCETIN"],
        "AUDIFONOS": ["AUDIFONO", "AURICULAR", "HEADPHONE"],
        "TV": ["TV", "TELEVISOR", "SMART"],
        "PARLANTE": ["PARLANTE", "SPEAKER"],
        "BARRA DE SONIDO": ["BARRA", "SOUNDBAR"],
        "CELULAR": ["CELULAR", "PHONE", "SMARTPHONE"],
        "PC": ["PC", "LAPTOP", "NOTEBOOK", "COMPUTADORA"],
        "REFRIGERADORA": ["REFRIGERADORA", "REFRIG", "NEVERA"],
        "LAVADORA": ["LAVADORA", "LAVADO", "LAVASECADORA"],
        "ELECTRODOMESTICOS": ["ELECTRO"],
        "CAMA": ["CAMA", "COLCHON", "TARIMA"],
        "CAMPANA EXTRACTORA": ["CAMPANA", "EXTRACTORA", "EXTRACTOR", "CAMPANAS"],
        "CAMPANA": ["CAMPANA", "EXTRACTORA", "EXTRACTOR", "CAMPANAS"],
    }

    palabras_clave = diccionario_sinonimos.get(filtro_clean, [filtro_clean])
    return any(kw in ident_clean for kw in palabras_clave)


def tienda_necesita_patrullaje(supabase_client, tienda: str, horas_espera: float = 1.5) -> bool:
    tienda_clean = str(tienda).upper().strip()
    try:
        res = (
            supabase_client.table("health_checks")
            .select("ultimo_escaneo")
            .eq("tienda", tienda_clean)
            .execute()
        )

        if res.data and len(res.data) > 0:
            raw_fecha = res.data[0].get("ultimo_escaneo")
            if raw_fecha:
                str_fecha = str(raw_fecha).replace("Z", "+00:00")
                ultimo_scan = datetime.fromisoformat(str_fecha)
                if ultimo_scan.tzinfo is None:
                    ultimo_scan = ultimo_scan.replace(tzinfo=timezone.utc)

                ahora = datetime.now(timezone.utc)
                horas_pasadas = (ahora - ultimo_scan).total_seconds() / 3600.0

                if horas_pasadas < horas_espera:
                    safe_log(
                        f"⏳ [{tienda_clean}] Omitido: Se escaneó hace {horas_pasadas:.1f}h "
                        f"(esperando mínimo {horas_espera}h para cuidar créditos).",
                        "info",
                    )
                    return False
    except Exception as e:
        safe_log(f"⚠️ No se pudo verificar timestamp de enfriamiento para {tienda_clean}: {e}", "warning")

    return True


def revisar_ofertas(filtro_categoria="TODOS"):
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

    tiendas_permitidas = {}
    for t_nombre, t_horas in TIENDAS_CON_ENFRIAMIENTO.items():
        tiendas_permitidas[t_nombre] = tienda_necesita_patrullaje(supabase, t_nombre, horas_espera=t_horas)

    zona_peru = timezone(timedelta(hours=-5))
    fecha_actual = datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")
    total_ofertas_notificadas = 0
    total_productos_procesados = 0

    desactivados_acumulados = []
    vistos_en_este_escaneo = set()

    for radar in radares:
        url = radar.get("url", "").strip()
        precio_max = safe_float(radar.get("precio_max", 999999))
        identificador_base = str(radar.get("identificador", "GENERAL-OTROS-PRODUCTO-TODAS")).upper()

        if not url or not url.startswith("http"):
            continue

        if not cumple_filtro_categoria(filtro_categoria, identificador_base):
            continue

        parts = identificador_base.split("-")
        tienda = parts[0] if parts else "GENERAL"
        categoria = parts[1] if len(parts) > 1 else "OTROS"
        tag = parts[2] if len(parts) > 2 else "PRODUCTO"

        es_activo = radar.get("activo", True)
        if es_activo is False:
            desactivados_acumulados.append({"tienda": tienda, "tag": tag, "url": url})
            continue

        if tienda in tiendas_permitidas and not tiendas_permitidas[tienda]:
            continue

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

                link_raw = str(prod.get("link", url)).strip()
                if not link_raw or not link_raw.startswith("http"):
                    continue
                link_prod = link_raw.split("?")[0].split("#")[0].rstrip("/")

                # Prevenir duplicados dentro del mismo lote de escaneo
                if link_prod in vistos_en_este_escaneo:
                    continue
                vistos_en_este_escaneo.add(link_prod)

                imagen = str(prod.get("imagen", prod.get("img", ""))).strip()

                if precio_oferta <= 0 or es_error_de_precio(precio_oferta, precio_regular):
                    continue

                res_existente = (
                    supabase.table("historial_precios")
                    .select("id, precio, precio_regular, nombre_producto, imagen_producto")
                    .eq("link_producto", link_prod)
                    .limit(1)
                    .execute()
                )

                if not res_existente.data:
                    # 🟢 PRODUCTO NUEVO: Notificar a Telegram
                    exito_telegram = enviar_alerta_telegram(
                        tienda=tienda,
                        nombre=nombre_real,
                        precio_oferta=precio_oferta,
                        precio_regular=precio_regular,
                        link=link_prod,
                        imagen=imagen,
                        tipo_alerta="NUEVO_PRODUCTO",
                    )

                    if exito_telegram:
                        datos_insert = {
                            "identificador": f"{tienda}-{categoria}",
                            "nombre_producto": nombre_real,
                            "precio": precio_oferta,
                            "precio_regular": precio_regular,
                            "imagen_producto": imagen,
                            "link_producto": link_prod,
                            "fecha": fecha_actual,
                            "tipo_evento": "NUEVO",
                        }
                        res_ins = supabase.table("historial_precios").insert(datos_insert).execute()
                        if res_ins and res_ins.data:
                            total_productos_procesados += 1
                            total_ofertas_notificadas += 1
                            safe_log(f"🆕 Producto nuevo notificado y guardado: {nombre_real}", "success")
                            time.sleep(1.2)

                else:
                    # 🟡 PRODUCTO EXISTENTE EN BASE DE DATOS
                    reg_guardado = res_existente.data[0]
                    precio_guardado = safe_float(reg_guardado.get("precio"))
                    id_bd = reg_guardado.get("id")

                    if precio_oferta < precio_guardado:
                        # 📉 BAJA DE PRECIO (Notificar a Telegram)
                        exito_telegram = enviar_alerta_telegram(
                            tienda=tienda,
                            nombre=nombre_real,
                            precio_oferta=precio_oferta,
                            precio_regular=precio_guardado,
                            link=link_prod,
                            imagen=imagen,
                            tipo_alerta="BAJA_PRECIO",
                        )

                        if exito_telegram:
                            datos_update = {
                                "nombre_producto": nombre_real,
                                "precio": precio_oferta,
                                "precio_regular": max(precio_regular, precio_guardado),
                                "imagen_producto": imagen if imagen else reg_guardado.get("imagen_producto", ""),
                                "fecha": fecha_actual,
                                "tipo_evento": "BAJA_PRECIO",
                            }
                            supabase.table("historial_precios").update(datos_update).eq("id", id_bd).execute()
                            total_productos_procesados += 1
                            total_ofertas_notificadas += 1
                            safe_log(
                                f"📉 Baja de precio (S/. {precio_guardado:.2f} ➔ S/. {precio_oferta:.2f}): {nombre_real}",
                                "success",
                            )
                            time.sleep(1.2)

                    elif precio_oferta > precio_guardado:
                        # 📈 PRECIO SUBIÓ: Actualizar BD en silencio (Sin mensaje a Telegram)
                        datos_update = {
                            "precio": precio_oferta,
                            "precio_regular": max(precio_regular, precio_guardado),
                            "fecha": fecha_actual,
                            "tipo_evento": "SUBIDA_PRECIO",
                        }
                        if not reg_guardado.get("nombre_producto"):
                            datos_update["nombre_producto"] = nombre_real

                        supabase.table("historial_precios").update(datos_update).eq("id", id_bd).execute()
                        total_productos_procesados += 1
                        safe_log(
                            f"📈 El precio subió (S/. {precio_guardado:.2f} ➔ S/. {precio_oferta:.2f}). BD actualizada en silencio.",
                            "info",
                        )

                    else:
                        # 🕒 PRECIO IGUAL (CONSTANTE)
                        datos_update = {
                            "fecha": fecha_actual,
                            "tipo_evento": "CONSTANTE",
                        }
                        if not reg_guardado.get("nombre_producto"):
                            datos_update["nombre_producto"] = nombre_real

                        supabase.table("historial_precios").update(datos_update).eq("id", id_bd).execute()
                        total_productos_procesados += 1

            except Exception as ex_prod:
                safe_log(f"⚠️ Error procesando producto individual: {ex_prod}", "warning")
                continue

    resumen = (
        f"Patrullaje [{filtro_categoria}] finalizado. "
        f"Procesados: {total_productos_procesados} productos | "
        f"Notificaciones enviadas: {total_ofertas_notificadas} | "
        f"Radares pausados omitidos: {len(desactivados_acumulados)}."
    )
    safe_log(f"✅ {resumen}", "success")
    return resumen
