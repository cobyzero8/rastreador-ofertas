import requests
from datetime import datetime, timezone, timedelta
from supabase import Client
import streamlit as st
from config import TELEGRAM_DEV_CHAT_ID, TELEGRAM_CHAT_ID, TELEGRAM_TOKEN
from utils import safe_log

def notificar_desarrollador_caida(tienda: str, fallos: int, url_prueba: str):
    dev_chat = TELEGRAM_DEV_CHAT_ID or TELEGRAM_CHAT_ID
    if not TELEGRAM_TOKEN or not dev_chat: return
        
    mensaje_html = (
        f"🚨 <b>ALERTA DE INFRAESTRUCTURA (HEALTH CHECK)</b> 🚨\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🛠️ <b>Motor Afectado:</b> <code>{tienda}</code>\n"
        f"❌ <b>Fallos Consecutivos:</b> {fallos}\n"
        f"⚠️ <b>Diagnóstico:</b> 0 productos extraídos repetidamente.\n\n"
        f"🔗 <a href='{url_prueba}'><b>Probar URL en navegador</b></a>"
    )
    payload = {"chat_id": dev_chat, "text": mensaje_html, "parse_mode": "HTML", "disable_web_page_preview": True}
    try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json=payload, timeout=10)
    except Exception as e: safe_log(f"Error enviando alerta dev: {e}", "warning")

def registrar_resultado_salud(supabase_client: Client, tienda: str, total_productos: int, url_origen: str):
    zona_peru = timezone(timedelta(hours=-5))
    ahora_iso = datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")
    fallos_actuales = 0
    try:
        res = supabase_client.table("health_checks").select("fallos_consecutivos").eq("tienda", tienda).execute()
        if res.data and len(res.data) > 0:
            fallos_actuales = res.data[0].get("fallos_consecutivos", 0)
    except Exception: pass
    
    nuevos_fallos = 0 if total_productos > 0 else fallos_actuales + 1
    nuevo_estado = "GREEN" if total_productos > 0 else ("RED" if nuevos_fallos >= 3 else "YELLOW")

    datos = {
        "tienda": tienda, "estado": nuevo_estado, "fallos_consecutivos": nuevos_fallos,
        "ultimo_escaneo": ahora_iso, "ultimos_productos_count": total_productos,
        "ultimo_error": "0 productos extraídos" if total_productos == 0 else None
    }
    try: supabase_client.table("health_checks").upsert(datos, on_conflict="tienda").execute()
    except Exception as e: safe_log(f"⚠️ Salud no registrada para {tienda}: {e}", "caption")

    if nuevos_fallos == 3: notificar_desarrollador_caida(tienda, nuevos_fallos, url_origen)

def renderizar_dashboard_salud(supabase_client: Client):
    st.markdown("## 🏥 Panel de Salud de Scrapers")
    try:
        res = supabase_client.table("health_checks").select("*").order("tienda").execute()
        data = res.data if res.data else []
    except Exception as e:
        st.error(f"Error cargando registros de salud: {e}")
        return

    if not data:
        st.info("No hay registros de salud disponibles.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Scrapers", len(data))
    col2.metric("🟢 Operativos", sum(1 for d in data if d.get('estado') == 'GREEN'))
    col3.metric("🟡 Advertencia", sum(1 for d in data if d.get('estado') == 'YELLOW'))
    col4.metric("🔴 Caídos", sum(1 for d in data if d.get('estado') == 'RED'))

    for item in data:
        estado = item.get('estado', 'GREEN')
        icon = "🟢" if estado == "GREEN" else "🟡" if estado == "YELLOW" else "🔴"
        st.write(f"{icon} **{item.get('tienda')}** | Fallos: {item.get('fallos_consecutivos', 0)} | Productos: {item.get('ultimos_productos_count', 0)}")
