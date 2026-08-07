import time
import hashlib
import re
from datetime import datetime, timezone, timedelta
import streamlit as st

from config import supabase
from utils import sanitizar_url, safe_log, es_error_de_precio
from notifications import enviar_telegram_real
from health_monitor import registrar_resultado_salud
from scrapers import escanear_tienda
from gestor_cupones import obtener_bloque_cupones_telegram

def revisar_ofertas(filtro_objetivo="TODOS"):
    try: 
        res = supabase.table("radares").select("*").execute()
    except Exception as e: 
        safe_log(f"🛑 Error de conexión con Supabase (Tabla radares): {e}", "error")
        return f"Fallo Supabase: {e}"
        
    if not res or not res.data:
        return "Sin radares activos."
    
    total, alertas = 0, 0
    enviados = set()
    lista_html_streamlit = []
    zona_peru = timezone(timedelta(hours=-5))
    fecha_hoy = datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")
    target = str(filtro_objetivo).strip().upper()
    
    mapa_emojis = {
        "PERFUMES": "🧪", "ZAPATILLAS": "👟", "MEDIAS": "🧦", "POLOS": "👕", 
        "CASACAS": "🧥", "SHORTS": "🩳", "BUZOS": "👖", "AUDIFONOS": "🎧", 
        "TV": "📺", "PARLANTE": "🔊", "BARRA DE SONIDO": "🎵", "CELULAR": "📱", 
        "PC": "💻", "REFRIGERADORA": "❄️", "LAVADORA": "🧺", "ELECTRODOMESTICOS": "🔌", 
        "CAMA": "🛏️", "OTROS": "📦"
    }
    
    safe_log("🔍 **Iniciando Patrullaje y Diagnóstico en Vivo...**", "info")
    
    for item in res.data:
        ident = item['identificador'].upper()
        url_low = sanitizar_url(item['url']).lower()
        
        es_accesorio = any(acc in ident or acc.lower() in url_low for acc in [
            "FILTRO", "DETERGENTE", "LIMPIADOR", "PROTECTOR", "FUNDA", "CABLE", 
            "SOPORTE", "AMORTIGUADOR", "REPUESTO", "ADAPTADOR", "PASTILLA", "JABON"
        ])

        if es_accesorio: grupo = "OTROS"
        elif "SHORT" in ident or "short" in url_low: grupo = "SHORTS"
        elif "PERFUME" in ident or "perfume" in url_low: grupo = "PERFUMES"
        elif "ZAPATILLA" in ident or "zapatilla" in url_low or "calzado" in url_low or "nike.com.pe" in url_low: grupo = "ZAPATILLAS"
        elif "MEDIAS" in ident or "medias" in url_low: grupo = "MEDIAS"
        elif "POLO" in ident or "polo" in url_low: grupo = "POLOS"
        elif "CASACA" in ident or "casaca" in url_low or "polera" in url_low: grupo = "CASACAS"
        elif "BUZO" in ident or "buzo" in url_low or "pantalon" in url_low: grupo = "BUZOS"
        elif "AUDIFONO" in ident or "audifono" in url_low: grupo = "AUDIFONOS"
        elif "TV" in ident or "smart-tv" in url_low: grupo = "TV"
        elif "PARLANTE" in ident or "speaker" in url_low: grupo = "PARLANTE"
        elif "BARRA" in ident or "soundbar" in url_low: grupo = "BARRA DE SONIDO"
        elif "CELULAR" in ident or "phone" in url_low or "celular" in url_low: grupo = "CELULAR"
        elif "PC" in ident or "laptop" in url_low: grupo = "PC"
        elif "REFRIGERADORA" in ident or "refrig" in url_low: grupo = "REFRIGERADORA"
        elif "LAVADORA" in ident: grupo = "LAVADORA"
        elif "ELECTRO" in ident: grupo = "ELECTRODOMESTICOS"
        elif "CAMA" in ident or "colchon" in url_low: grupo = "CAMA"
        else: grupo = "OTROS"

        if target != "TODOS" and target != grupo:
            continue
            
        tienda_actual = ident.replace('_', '-').split('-')[0]
        safe_log(f"🔄 Patrullando Tienda: {tienda_actual} | Categoría: {grupo}...", "info")
        
        prods = escanear_tienda(item['url'], item['precio_max'])
        
        registrar_resultado_salud(
            supabase_client=supabase,
            tienda=tienda_actual,
            total_productos=len(prods),
            url_origen=item['url']
        )

        bloque_cupones = obtener_bloque_cupones_telegram(tienda_actual)
        bloque_cupones_str = f"\n{bloque_cupones}" if bloque_cupones else ""

        try:
            supabase.table("radares").update({"ultimo_escaneo": fecha_hoy}).eq("identificador", item['identificador']).execute()
        except Exception:
            pass

        for p in prods:
            try:
                n_u = re.sub(r'\s+', ' ', p['nombre']).strip().upper()
                
                if grupo in ["BARRA DE SONIDO", "PARLANTE", "AUDIFONOS"]:
                    palabras_prohibidas = ["SABANA", "SÁBANA", "ALMOHADA", "COLCHON", "COLCHÓN", "EDREDON", "EDREDÓN", "CAMA", "FRAZADA", "MANTA"]
                    if any(bad in n_u for bad in palabras_prohibidas): continue
                
                if n_u in enviados: continue
                enviados.add(n_u)
                total += 1
                p_v = float(p['precio'])
                p_r = max(float(p.get('precio_regular', p_v)), p_v)
                
                p['tienda_origen'] = tienda_actual
                lista_html_streamlit.append(p)
                
                url_limpia = sanitizar_url(p['link']).split('?')[0]
                hash_url = hashlib.md5(url_limpia.encode('utf-8')).hexdigest()[:12]
                id_registro = f"{item['identificador']}-{hash_url}".upper()
                
                precio_anterior = None
                try:
                    res_ant = supabase.table("historial_precios").select("precio").eq("identificador", id_registro).execute()
                    if res_ant.data and len(res_ant.data) > 0:
                        precio_anterior = float(res_ant.data[0]['precio'])
                except Exception as e_sel:
                    safe_log(f"⚠️ Error consultando precio en Supabase: {e_sel}", "caption")

                img_limpia = sanitizar_url(p.get('img', ''))
                if not img_limpia or img_limpia.lower() in ['empty', 'none', 'null']:
                    img_limpia = None

                datos_guardar = {
                    "identificador": id_registro, 
                    "precio": p_v, 
                    "precio_regular": p_r, 
                    "link_producto": sanitizar_url(p['link']), 
                    "imagen_producto": img_limpia, 
                    "fecha": fecha_hoy
                }
                
                emoji = mapa_emojis.get(grupo, "🔥")

                if precio_anterior is None:
                    try: 
                        supabase.table("historial_precios").upsert(datos_guardar, on_conflict="identificador").execute()
                    except Exception as e_up: 
                        safe_log(f"🚨 Error insertando en Supabase: {e_up}", "error")

                    msg_t = (
                        f"✨ <b>¡NUEVO PRODUCTO ENCONTRADO!</b> ✨\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📦 <b>Producto:</b> <code>{p['nombre']}</code>\n"
                        f"🏪 <b>Tienda:</b> <code>{tienda_actual}</code>\n"
                        f"💰 <b>Precio Encontrado:</b> S/. {p_v:.2f}"
                        f"{bloque_cupones_str}"
                    )
                    if enviar_telegram_real(msg_t, p['link'], img_limpia or ""): 
                        alertas += 1
                        time.sleep(0.3)

                elif p_v < precio_anterior:
                    try: 
                        supabase.table("historial_precios").upsert(datos_guardar, on_conflict="identificador").execute()
                    except Exception as e_up: 
                        safe_log(f"🚨 Error actualizando bajada en Supabase: {e_up}", "error")

                    es_bug, pct_descuento = es_error_de_precio(
                        precio_actual=p_v, 
                        precio_regular=p_r, 
                        precio_anterior=precio_anterior, 
                        categoria=grupo
                    )

                    if es_bug:
                        msg_out = (
                            f"🚨🚨 <b>¡POSIBLE ERROR DE PRECIO / BUG!</b> 🚨🚨\n"
                            f"‼️ <b>¡COMPRA RÁPIDO ANTES QUE LO CORRIJAN!</b> ‼️\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"📦 <b>Producto:</b> <code>{p['nombre']}</code>\n"
                            f"🏪 <b>Tienda:</b> <code>{tienda_actual}</code>\n"
                            f"💥 <b>Precio BUG:</b> <b>S/. {p_v:.2f}</b>\n"
                            f"❌ <b>Precio Normal:</b> S/. {p_r:.2f}\n"
                            f"🔥 <b>Descuento Brutal:</b> {pct_descuento:.0f}%\n\n"
                            f"⏰ <i>Nota: Los errores de sistema suelen durar pocos minutos.</i>"
                            f"{bloque_cupones_str}"
                        )
                    else:
                        ahorro = precio_anterior - p_v
                        msg_out = (
                            f"{emoji} <b>¡OFERTA: BAJÓ DE PRECIO!</b> {emoji}\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"📦 <b>Producto:</b> <code>{p['nombre']}</code>\n"
                            f"🏪 <b>Tienda:</b> <code>{tienda_actual}</code>\n"
                            f"❌ <b>Precio Anterior:</b> S/. {precio_anterior:.2f}\n"
                            f"💰 <b>Nuevo Precio Oferta:</b> S/. {p_v:.2f}\n"
                            f"📉 <b>Te Ahorras:</b> S/. {ahorro:.2f}"
                            f"{bloque_cupones_str}"
                        )

                    if enviar_telegram_real(msg_out, p['link'], img_limpia or ""): 
                        alertas += 1
                        time.sleep(0.3)

                else:
                    try: 
                        supabase.table("historial_precios").upsert(datos_guardar, on_conflict="identificador").execute()
                    except Exception: 
                        pass

            except Exception: continue

    safe_log("✅ **¡Patrullaje y Diagnóstico Finalizados con Éxito!**", "success")

    if len(lista_html_streamlit) > 0:
        try:
            st.markdown("---")
            st.markdown(f"### 🎯 Modelos encontrados e indexados en vivo ({len(lista_html_streamlit)}):")
            for prod in lista_html_streamlit:
                with st.container(border=True):
                    col1, col2 = st.columns([2, 8])
                    with col1:
                        if prod.get('img') and len(prod['img']) > 5: st.image(prod['img'], width=120)
                        else: st.write("📷 _Sin Foto_")
                    with col2:
                        st.markdown(f"#### `{prod['nombre']}`")
                        st.markdown(f"🏪 **Tienda de Origen:** `{prod['tienda_origen']}`")
                        p_oferta = prod['precio']
                        p_regular = prod.get('precio_regular', p_oferta)
                        if p_regular > p_oferta:
                            ahorro_soles = p_regular - p_oferta
                            porcentaje = (ahorro_soles / p_regular) * 100
                            st.markdown(f"❌ ~~Precio Regular: S/. {p_regular:.2f}~~")
                            st.markdown(f"💰 **Precio Oferta: S/. {prod['precio']:.2f}**")
                            st.markdown(f"🔥 **¡Ahorraste S/. {ahorro_soles:.2f}! ({porcentaje:.0f}% de Descuento)**")
                        else:
                            st.markdown(f"💰 **Precio Actual: S/. {prod['precio']:.2f}**")
                        st.markdown(f"🔗 [🌐 IR A COMPRAR DIRECTO]({prod['link']})")
        except Exception: pass

    return f"Éxito. Modelos procesados: {total}. Alertas Telegram: {alertas}."
