import os
import json
import requests
from datetime import datetime, timezone, timedelta
from config import supabase
from utils import safe_log

def obtener_top_ofertas_del_dia():
    """Consulta en Supabase las ofertas más destacadas registradas hoy."""
    if not supabase:
        safe_log("🛑 No hay conexión con Supabase.", "error")
        return []

    # Zona horaria de Perú (UTC-5)
    zona_peru = timezone(timedelta(hours=-5))
    hoy_str = datetime.now(zona_peru).strftime("%Y-%m-%d")

    try:
        # Buscar productos del día ordenados por fecha o descuento
        res = (
            supabase.table("historial_precios")
            .select("identificador, nombre_producto, precio, precio_regular, link_producto")
            .gte("fecha", f"{hoy_str} 00:00:00")
            .order("fecha", desc=True)
            .limit(15)
            .execute()
        )

        productos = res.data if res and res.data else []
        
        # Filtrar y ordenar por porcentaje de descuento real
        top_productos = []
        for p in productos:
            p_o = float(p.get("precio") or 0)
            p_r = float(p.get("precio_regular") or p_o)
            
            if p_o > 0 and p_r > p_o:
                descuento_pct = ((p_r - p_o) / p_r) * 100
                top_productos.append({
                    "nombre": p.get("nombre_producto") or p.get("identificador"),
                    "precio_oferta": p_o,
                    "precio_regular": p_r,
                    "descuento_pct": round(descuento_pct, 1),
                    "link": p.get("link_producto")
                })

        # Ordenar de mayor a menor porcentaje de descuento y tomar los mejores 10
        top_productos.sort(key=lambda x: x["descuento_pct"], reverse=True)
        return top_productos[:10]

    except Exception as e:
        safe_log(f"🚨 Error consultando top ofertas: {e}", "error")
        return []


def generar_reporte_con_gemini(productos):
    """Envia el listado consolidado a Gemini para redactar un resumen ejecutivo."""
    try:
        import google.generativeai as genai
    except ImportError:
        return None

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return None

    genai.configure(api_key=api_key)

    # Convertir productos a texto para el prompt
    lista_txt = ""
    for idx, p in enumerate(productos, 1):
        lista_txt += (
            f"{idx}. {p['nombre']} | Precio Oferta: S/ {p['precio_oferta']:.2f} | "
            f"Precio Regular: S/ {p['precio_regular']:.2f} (-{p['descuento_pct']}%)\n"
        )

    prompt = f"""
    Actúa como un editor experto en e-commerce y ofertas en Perú.
    Sintetiza las siguientes 10 ofertas detectadas hoy en nuestro sistema:

    {lista_txt}

    Genera un reporte diario breve para enviar por Telegram con este formato exacto en HTML:

    🗞️ <b>RESUMEN DE CHOLLOS DEL DÍA</b>

    🌟 <b>Lo más destacado:</b> (Menciona en 1 frase el producto con el descuento más real o tentador).
    ⚠️ <b>Cuidado con:</b> (Menciona si algún precio regular parece haber sido inflado para simular descuento).
    💡 <b>Conclusión:</b> (1 recomendación general de compra para hoy).

    Sé directivo, amigable y directo. No agregues saludos iniciales ni despedidas.
    """

    modelos_disponibles = [
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-1.5-flash-latest',
        'gemini-1.5-flash-001'
    ]

    for nombre_modelo in modelos_disponibles:
        try:
            model = genai.GenerativeModel(nombre_modelo)
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
        except Exception:
            continue

    return None


def enviar_resumen_telegram(reporte_html):
    """Publica el reporte diario en el canal/chat de Telegram."""
    token = os.environ.get("TELEGRAM_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        safe_log("⚠️ Faltan credenciales de Telegram.", "warning")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": reporte_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    try:
        resp = requests.post(url, json=payload, timeout=12)
        if resp.status_code == 200:
            safe_log("✅ Resumen diario enviado exitosamente a Telegram.", "success")
    except Exception as e:
        safe_log(f"🚨 Error enviando resumen a Telegram: {e}", "error")


def ejecutar():
    safe_log("🗞️ Generando Resumen Ejecutivo Diario...", "info")
    top_prods = obtener_top_ofertas_del_dia()

    if not top_prods:
        safe_log("ℹ️ No hay suficientes ofertas registradas hoy para generar el resumen.", "info")
        return

    reporte = generar_reporte_con_gemini(top_prods)
    if reporte:
        enviar_resumen_telegram(reporte)
    else:
        safe_log("⚠️ No se pudo generar el reporte con Gemini.", "warning")


if __name__ == "__main__":
    ejecutar()
