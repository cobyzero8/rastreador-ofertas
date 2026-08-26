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


def enviar_reporte_inactivos_telegram(lista_desactivados, filtro_aplicado="TODOS"):
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    try:
        import streamlit as st
        if hasattr(st, "secrets"):
            if not token:
                token = st.secrets.get("TELEGRAM_TOKEN")
            if not chat_id:
                chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
    except Exception:
        pass

    if not token or not chat_id:
        safe_log("⚠️ No se enviará reporte a Telegram: faltan credenciales.", "warning")
        return

    cant = len(lista_desactivados)
    lineas = []
    for item in lista_desactivados[:8]:
        lineas.append(
            f"• <b>{item['tienda']}</b> | <code>{item['tag']}</code>\n  └ 🔗 <a href='{item['url']}'>Ver URL Pausada</a>"
        )

    if cant > 8:
        lineas.append(f"<i>...y {cant - 8} URLs pausadas más.</i>")

    cuerpo = "\n".join(lineas)
    mensaje = (
        f"<b>⏸️ REPORTE DE PATRULLAJE - RADARES PAUSADOS [{filtro_aplicado}]</b>\n\n"
        f"Se han omitido <b>{cant} URL(s)</b> de esta categoría por estar desactivadas:\n\n"
        f"{cuerpo}\n\n"
        f"💡 <i>Si deseas volver a rastrearlas, actívalas desde la UI.</i>"
    )

    url_api = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": mensaje,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    try:
        requests.post(url_api, json=payload, timeout=10)
        safe_log("📲 Reporte de URLs inactivas enviado a Telegram.", "info")
    except Exception as e:
        safe_log(f"❌ Falló el envío del reporte de inactivos a Telegram: {e}", "error")


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
                        f"(esperando mínimo {horas_espera}h para cuidar créditos de ScraperAPI).",
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
            safe_log(
                f"⏸️ [{tienda}] OMITIDO: El radar '{identificador_base}' ({url}) está DESACTIVADO.",
                "warning",
            )
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
                    # 🟢 PRODUCTO NUEVO: Intentar notificar a Telegram primero
                    exito_telegram = enviar_alerta_telegram(
                        tienda=tienda,
                        nombre=nombre_real,
                        precio_oferta=precio_oferta,
                        precio_regular=precio_regular,
                        link=link_prod,
                        imagen=imagen,
                        tipo_alerta="NUEVO_PRODUCTO",
                    )

                    # 🎯 SOLO si Telegram responde True, guardamos en la BD
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
                            safe_log(
                                f"🆕 Producto nuevo notificado a Telegram y guardado: {nombre_real}",
                                "success",
                            )
                            time.sleep(1.5)
                    else:
                        safe_log(
                            f"⚠️ Telegram no entregó la alerta para {nombre_real}. No se guarda en BD para reintentar.",
                            "warning",
                        )

                else:
                    # 🟡 PRODUCTO EXISTENTE: Evaluar si bajó de precio
                    reg_guardado = res_existente.data[0]
                    precio_guardado = safe_float(reg_guardado.get("precio"))
                    id_bd = reg_guardado.get("id")

                    if precio_oferta < precio_guardado:
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
                                "imagen_producto": (
                                    imagen if imagen else reg_guardado.get("imagen_producto", "")
                                ),
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
                            time.sleep(1.5)
                        else:
                            safe_log(
                                f"⚠️ Telegram no entregó la baja de precio para: {nombre_real}. Se reintentará luego.",
                                "warning",
                            )

                    else:
                        datos_update = {
                            "fecha": fecha_actual,
                            "tipo_evento": "CONSTANTE",
                        }
                        if not reg_guardado.get("nombre_producto"):
                            datos_update["nombre_producto"] = nombre_real

                        supabase.table("historial_precios").update(datos_update).eq("id", id_bd).execute()
                        total_productos_procesados += 1
                        safe_log(
                            f"🕒 Producto constante (S/. {precio_oferta:.2f}). Fecha actualizada.",
                            "info",
                        )

            except Exception as ex_prod:
                safe_log(f"⚠️ Error procesando producto individual: {ex_prod}", "warning")
                continue

    if desactivados_acumulados:
        enviar_reporte_inactivos_telegram(desactivados_acumulados, filtro_categoria)

    resumen = (
        f"Patrullaje [{filtro_categoria}] finalizado. "
        f"Procesados: {total_productos_procesados} productos | "
        f"Notificaciones enviadas: {total_ofertas_notificadas} | "
        f"Radares pausados omitidos: {len(desactivados_acumulados)}."
    )
    safe_log(f"✅ {resumen}", "success")
    return resumen
