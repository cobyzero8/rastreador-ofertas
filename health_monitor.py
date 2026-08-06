import os
import requests
from datetime import datetime, timezone, timedelta
from supabase import Client

# Chat ID privado del desarrollador para alertas de infraestructura
TELEGRAM_DEV_CHAT_ID = os.environ.get("TELEGRAM_DEV_CHAT_ID") or os.environ.get("TELEGRAM_CHAT_ID")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

def notificar_desarrollador_caida(tienda: str, fallos: int, url_prueba: str):
    """Envía un reporte privado al desarrollador cuando un scraper falla repetidamente."""
    if not TELEGRAM_TOKEN or not TELEGRAM_DEV_CHAT_ID:
        return
        
    mensaje_html = (
        f"🚨 <b>ALERTA DE INFRAESTRUCTURA (HEALTH CHECK)</b> 🚨\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🛠️ <b>Motor Afectado:</b> <code>{tienda}</code>\n"
        f"❌ <b>Fallos Consecutivos:</b> {fallos}\n"
        f"⚠️ <b>Diagnóstico:</b> El scraper devolvió 0 productos en {fallos} patrullajes seguidos.\n"
        f"🔍 <b>Causa probable:</b> Cambio en la estructura DOM/CSS o bloqueo anti-bot.\n\n"
        f"🔗 <a href='{url_prueba}'><b>Probar URL manualmente en navegador</b></a>"
    )
    
    url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_DEV_CHAT_ID,
        "text": mensaje_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url_api, json=payload, timeout=10)
    except Exception as e:
        print(f"Error enviando alerta dev: {e}")

def registrar_resultado_salud(supabase: Client, tienda: str, total_productos: int, url_origen: str):
    """
    Actualiza el estado de salud de la tienda.
    - Si total_productos > 0: Resetea fallos a 0 y marca GREEN.
    - Si total_productos == 0: Incrementa fallos acumulados (YELLOW con 1-2, RED con >= 3).
    """
    zona_peru = timezone(timedelta(hours=-5))
    ahora_iso = datetime.now(zona_peru).isoformat()
    
    # 1. Consultar estado actual
    res = supabase.table("health_checks").select("*").eq("tienda", tienda).execute()
    registro_previo = res.data[0] if res.data else None
    
    fallos_actuales = registro_previo.get("fallos_consecutivos", 0) if registro_previo else 0
    
    if total_productos > 0:
        nuevos_fallos = 0
        nuevo_estado = "GREEN"
    else:
        nuevos_fallos = fallos_actuales + 1
        if nuevos_fallos >= 3:
            nuevo_estado = "RED"
        else:
            nuevo_estado = "YELLOW"

    datos_actualizar = {
        "tienda": tienda,
        "estado": nuevo_estado,
        "fallos_consecutivos": nuevos_fallos,
        "ultimo_escaneo": ahora_iso,
        "ultimos_productos_count": total_productos,
        "ultimo_error": "0 productos extraídos" if total_productos == 0 else None
    }

    # 2. Persistir en Supabase
    supabase.table("health_checks").upsert(datos_actualizar, on_conflict="tienda").execute()

    # 3. Notificar únicamente en el cruce del umbral crítico (exactamente en el fallo 3)
    if nuevos_fallos == 3:
        notificar_desarrollador_caida(tienda, nuevos_fallos, url_origen)
