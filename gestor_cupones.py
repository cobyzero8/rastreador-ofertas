# gestor_cupones.py
import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

def obtener_bloque_cupones_telegram(tienda_nombre):
    """
    Consulta en Supabase si existen cupones activos para la tienda indicada.
    Retorna un texto listo en HTML para Telegram o una cadena vacía si no hay cupones.
    """
    if not SUPABASE_KEY or not SUPABASE_URL:
        return ""

    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        tienda_clean = str(tienda_nombre).strip().upper()

        # Consulta hasta 3 cupones activos recientes para la tienda
        res = supabase.table("cupones") \
            .select("codigo, descripcion") \
            .eq("tienda", tienda_clean) \
            .eq("activo", True) \
            .order("fecha_registro", descending=True) \
            .limit(3) \
            .execute()

        if not res.data or len(res.data) == 0:
            return ""

        cupones_lineas = []
        for item in res.data:
            cod = item['codigo']
            desc = f" ({item['descripcion']})" if item.get('descripcion') else ""
            cupones_lineas.append(f"• <code>{cod}</code>{desc}")

        texto_bloque = "\n🎟️ <b>¡Prueba estos cupones para mayor descuento!</b>\n" + "\n".join(cupones_lineas) + "\n"
        return texto_bloque

    except Exception as e:
        print(f"Aviso en gestor_cupones: {e}")
        return ""
