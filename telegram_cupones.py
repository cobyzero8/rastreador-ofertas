# telegram_cupones.py
import os
import re
import asyncio
from telethon import TelegramClient, events
from supabase import create_client, Client

# Credenciales de acceso a la API de Telegram (Obtenidas en https://my.telegram.org)
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")

SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if (SUPABASE_URL and SUPABASE_KEY) else None

# Mapa de tiendas estandarizadas para vinculación precisa
TIENDAS_MAPA = [
    "ADIDAS", "CARSA", "COOLBOX", "CURACAO", "CYZONE", "EFE", "ESIKA", 
    "ESTILOS", "FALABELLA", "FOOTLOOSE", "HIRAOKA", "JBL", "JUNTOZ", 
    "LBEL", "NIKE", "OECHSLE", "PLATANITOS", "PLAZA_VEA", "PROMART", 
    "THN", "TRIATHLON"
]

# Canales públicos de ofertas en Perú a monitorear
CANALES_PUBLICOS = ['chollosperu', 'ofertaspe', 'descuentosperu']

def detectar_tienda_en_texto(texto):
    texto_upper = texto.upper()
    for tienda in TIENDAS_MAPA:
        tienda_busqueda = tienda.replace("_", " ")
        if tienda_busqueda in texto_upper or tienda in texto_upper:
            return tienda
    return "GENERAL"

def guardar_cupon_telegram(tienda, codigo, descripcion):
    if not supabase:
        print("⚠️ Supabase no está configurado.")
        return
    try:
        datos = {
            "tienda": tienda,
            "codigo": codigo.strip().upper(),
            "descripcion": descripcion[:100],
            "origen": "TELEGRAM",
            "activo": True
        }
        supabase.table("cupones").upsert(datos, on_conflict="codigo").execute()
        print(f"✅ Cupón guardado desde Telegram: [{tienda}] {codigo}")
    except Exception as e:
        print(f"⚠️ Error al guardar cupón en Supabase: {e}")

async def main():
    if not API_ID or not API_HASH:
        print("🛑 Error: TELEGRAM_API_ID y TELEGRAM_API_HASH son obligatorios.")
        return

    print("🤖 Capturador de cupones de Telegram iniciado. Escuchando canales...")
    client = TelegramClient('sesion_cupones', API_ID, API_HASH)

    @client.on(events.NewMessage(chats=CANALES_PUBLICOS))
    async def manejador_mensajes(event):
        texto = event.raw_text
        if not texto:
            return

        # Detección mediante expresión regular (Ejemplos: "CUPON: YAPE10", "CODIGO: NIKE20")
        match_cupon = re.search(r'(?:CUP[OÓ]N|C[OÓ]DIGO|USA EL C[OÓ]DIGO):\s*([A-Z0-9]{4,15})', texto, re.I)

        if match_cupon:
            codigo = match_cupon.group(1).upper()
            tienda = detectar_tienda_en_texto(texto)
            
            # Limpieza básica de la primera línea como descripción
            lineas = [l.strip() for l in texto.split('\n') if l.strip()]
            desc = lineas[0] if lineas else "Cupón capturado de Telegram"

            print(f"📩 Cupón detectado: [{tienda}] -> {codigo}")
            guardar_cupon_telegram(tienda, codigo, desc)

    await client.start()
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
