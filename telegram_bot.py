import os
import html
import logging
import asyncio
import streamlit as st
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Cargar automáticamente credenciales desde los secrets de Streamlit
try:
    if hasattr(st, "secrets"):
        for key, value in st.secrets.items():
            if isinstance(value, str):
                os.environ[key] = value
except Exception:
    pass

from config import supabase
from patrol import revisar_ofertas
from utils import analizar_producto_con_gemini

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

ADMIN_IDS_RAW = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_ADMIN_ID", "")
ADMINS_AUTORIZADOS = [aid.strip() for aid in ADMIN_IDS_RAW.split(",") if aid.strip()]


async def es_usuario_valido(update: Update) -> bool:
    if not ADMINS_AUTORIZADOS:
        return False
    chat_actual = str(update.effective_chat.id)
    return chat_actual in ADMINS_AUTORIZADOS


async def borrar_mensaje_usuario(update: Update):
    if update.message:
        try:
            await update.message.delete()
        except Exception:
            pass


async def borrar_menu_previo(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    menu_id = context.user_data.get("menu_message_id")
    if menu_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=menu_id)
        except Exception:
            pass
        context.user_data["menu_message_id"] = None


TIENDAS = [
    "ADIDAS", "CARSA", "COOLBOX", "CURACAO", "CYZONE", "EFE",
    "ESIKA", "ESTILOS", "FALABELLA", "FOOTLOOSE", "HIRAOKA", "JBL",
    "JUNTOZ", "LBEL", "NIKE", "OECHSLE", "PLATANITOS", "PLAZA_VEA",
    "PROMART", "RIPLEY", "SHOPSTAR", "THN", "TRIATHLON"
]

CATEGORIAS_MAP = {
    "PERFUMES": "🧪 PERFUMES", "ZAPATILLAS": "👟 ZAPATILLAS", "POLOS": "👕 POLOS",
    "CASACAS": "🧥 CASACAS", "SHORTS": "🩳 SHORTS", "BUZOS": "👖 BUZOS",
    "MEDIAS": "🧦 MEDIAS", "AUDIFONOS": "🎧 AUDÍFONOS", "TV": "📺 TV",
    "PARLANTE": "🔊 PARLANTE", "BARRA_DE_SONIDO": "🎵 B. SONIDO", "CELULAR": "📱 CELULAR",
    "PC": "💻 PC / LAPTOP", "REFRIGERADORA": "❄️ REFRIGERADORA", "LAVADORA": "🧺 LAVADORA",
    "ELECTRODOMESTICOS": "🔌 ELECTRODOM.", "CAMPANA_EXTRACTORA": "💨 CAMPANA EXT.",
    "CAMA": "🛏️ CAMA", "OTROS": "📦 OTROS"
}

CATEGORIAS = list(CATEGORIAS_MAP.keys())


def obtener_teclado_inicio():
    keyboard = [
        [InlineKeyboardButton("【 🚀 FORZAR PATRULLAJE COMPLETO 】", callback_data="run_TODOS")],
        [InlineKeyboardButton("【 🏬 MENÚ DE TIENDAS 】", callback_data="menu_tiendas")],
        [InlineKeyboardButton("【 🏷️ MENÚ DE CATEGORÍAS 】", callback_data="menu_categorias")]
    ]
    return InlineKeyboardMarkup(keyboard)


async def comando_coby(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_usuario_valido(update): return
    chat_id = update.effective_chat.id
    await borrar_mensaje_usuario(update)
    await borrar_menu_previo(context, chat_id)

    msg = await context.bot.send_message(
        chat_id=chat_id,
        text="🤖 <b>CENTRAL DE CONTROL - COBY CAZADOR</b>\n\nSelecciona una opción para patrullar:",
        reply_markup=obtener_teclado_inicio(),
        parse_mode="HTML"
    )
    context.user_data["menu_message_id"] = msg.message_id


async def comando_itzel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_usuario_valido(update): return
    chat_id = update.effective_chat.id
    await borrar_mensaje_usuario(update)
    await borrar_menu_previo(context, chat_id)


async def comando_pausados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_usuario_valido(update): return
    chat_id = update.effective_chat.id
    await borrar_mensaje_usuario(update)

    try:
        res = supabase.table("radares").select("identificador, url, activo").eq("activo", False).execute()
        inactivos = res.data or []
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text=f"🚨 Error consultando Supabase: `{e}`", parse_mode="Markdown")
        return

    cant = len(inactivos)
    if cant == 0:
        await context.bot.send_message(chat_id=chat_id, text="✅ *Todos los radares están activos.*", parse_mode="Markdown")
        return

    lineas = [f"• <b>{item.get('identificador', 'RADAR')}</b>\n  └ 🔗 <a href='{item.get('url', '#')}'>Ver URL</a>" for item in inactivos[:10]]
    mensaje = f"<b>⏸️ RADARES PAUSADOS ({cant})</b>\n\n" + "\n".join(lineas)
    await context.bot.send_message(chat_id=chat_id, text=mensaje, parse_mode="HTML", disable_web_page_preview=True)


async def ejecutar_escaneo(update: Update, context: ContextTypes.DEFAULT_TYPE, filtro: str):
    if not await es_usuario_valido(update): return
    chat_id = update.effective_chat.id
    await borrar_mensaje_usuario(update)

    filtro_limpio = filtro.replace("_", " ")
    await context.bot.send_message(chat_id=chat_id, text=f"🔍 Escaneando filtro: *{filtro_limpio}*...", parse_mode="Markdown")

    try:
        resumen = await asyncio.to_thread(revisar_ofertas, filtro)
        await context.bot.send_message(chat_id=chat_id, text=f"✅ Escaneo [{filtro_limpio}] finalizado:\n\n{resumen}")
    except Exception as e:
        logger.error(f"Error escaneo: {e}")


async def menu_tiendas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_usuario_valido(update): return
    chat_id = update.effective_chat.id
    await borrar_mensaje_usuario(update)
    await borrar_menu_previo(context, chat_id)

    keyboard = []
    for i in range(0, len(TIENDAS), 2):
        fila = [InlineKeyboardButton(f"【 🏪 {TIENDAS[i]} 】", callback_data=f"run_{TIENDAS[i]}")]
        if i + 1 < len(TIENDAS):
            fila.append(InlineKeyboardButton(f"【 🏪 {TIENDAS[i+1]} 】", callback_data=f"run_{TIENDAS[i+1]}"))
        keyboard.append(fila)

    keyboard.append([InlineKeyboardButton("【 ⬅️ VOLVER AL MENÚ 】", callback_data="menu_start")])
    msg = await context.bot.send_message(chat_id=chat_id, text="🏢 <b>SELECCIONA UNA TIENDA:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    context.user_data["menu_message_id"] = msg.message_id


async def menu_categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_usuario_valido(update): return
    chat_id = update.effective_chat.id
    await borrar_mensaje_usuario(update)
    await borrar_menu_previo(context, chat_id)

    keyboard = []
    keys = list(CATEGORIAS_MAP.keys())
    for i in range(0, len(keys), 2):
        k1 = keys[i]
        fila = [InlineKeyboardButton(f"【 {CATEGORIAS_MAP[k1]} 】", callback_data=f"run_{k1}")]
        if i + 1 < len(keys):
            k2 = keys[i+1]
            fila.append(InlineKeyboardButton(f"【 {CATEGORIAS_MAP[k2]} 】", callback_data=f"run_{k2}"))
        keyboard.append(fila)

    keyboard.append([InlineKeyboardButton("【 ⬅️ VOLVER AL MENÚ 】", callback_data="menu_start")])
    msg = await context.bot.send_message(chat_id=chat_id, text="🏷️ <b>SELECCIONA UNA CATEGORÍA:</b>", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    context.user_data["menu_message_id"] = msg.message_id


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_usuario_valido(update): return
    query = update.callback_query
    data = query.data

    if data == "menu_start":
        await comando_coby(update, context)
    elif data == "menu_tiendas":
        await menu_tiendas(update, context)
    elif data == "menu_categorias":
        await menu_categorias(update, context)
    elif data.startswith("run_"):
        await ejecutar_escaneo(update, context, data.replace("run_", ""))

    elif data == "analizar_ia":
        await query.answer("🧠 Analizando oferta e historial...", show_alert=False)
        
        texto_html = query.message.caption_html if query.message.caption else (query.message.text_html or "")
        texto_plano = query.message.caption or query.message.text or ""

        if "VEREDICTO IA" in texto_html:
            await query.answer("⚠️ Esta oferta ya fue analizada.", show_alert=True)
            return

        # 1. Extraer palabras clave del producto para buscar su historial real en Supabase
        historial_texto = ""
        try:
            lineas = texto_plano.split('\n')
            nombre_busqueda = ""
            for l in lineas:
                if "Producto:" in l:
                    nombre_busqueda = l.replace("Producto:", "").strip()
                    break
            
            if not nombre_busqueda:
                nombre_busqueda = texto_plano[:30]

            res_historia = supabase.table("historial_precios").select("precio, fecha").ilike("nombre_producto", f"%{nombre_busqueda[:20]}%").order("fecha", desc=True).limit(5).execute()
            registros = res_historia.data or []
            
            if registros:
                lineas_hist = [f"- S/. {r.get('precio')} ({r.get('fecha', 'Fecha pasada')})" for r in registros]
                historial_texto = "\n".join(lineas_hist)
        except Exception:
            pass

        # 2. Enviar a Gemini junto con el historial recolectado
        veredicto = await asyncio.to_thread(analizar_producto_con_gemini, texto_plano, historial_texto)

        try:
            if query.message.caption:
                limite_max = 1024
                nuevo_texto = f"{texto_html}\n\n{veredicto}"
                
                if len(nuevo_texto) > limite_max:
                    espacio_disponible = limite_max - len(veredicto) - 10
                    texto_cortado = texto_html[:espacio_disponible].rsplit('\n', 1)[0]
                    nuevo_texto = f"{texto_cortado}\n\n{veredicto}"

                await query.edit_message_caption(
                    caption=nuevo_texto, 
                    parse_mode="HTML",
                    reply_markup=query.message.reply_markup
                )
            else:
                nuevo_texto = f"{texto_html}\n\n{veredicto}"
                await query.edit_message_text(
                    text=nuevo_texto, 
                    parse_mode="HTML", 
                    disable_web_page_preview=True,
                    reply_markup=query.message.reply_markup
                )
        except Exception as e:
            if "Message is not modified" in str(e):
                await query.answer("⚠️ Este análisis ya está en el mensaje.", show_alert=True)
            else:
                logger.error(f"Error IA: {e}")
                await query.answer(f"🚨 Error: {e}", show_alert=True)


def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        print("❌ Error: TELEGRAM_TOKEN no configurado.")
        return

    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler(["coby", "start"], comando_coby))
    app.add_handler(CommandHandler("itzel", comando_itzel))
    app.add_handler(CommandHandler(["pausados", "inactivos"], comando_pausados))
    app.add_handler(CommandHandler("tiendas", menu_tiendas))
    app.add_handler(CommandHandler("categorias", menu_categorias))
    app.add_handler(CommandHandler("forzar_todo", lambda u, c: ejecutar_escaneo(u, c, "TODOS")))

    for tienda in TIENDAS:
        app.add_handler(CommandHandler(f"tienda_{tienda.lower()}", lambda u, c, t=tienda: ejecutar_escaneo(u, c, t)))

    for cat in CATEGORIAS:
        app.add_handler(CommandHandler(f"cat_{cat.lower()}", lambda u, c, cat_val=cat: ejecutar_escaneo(u, c, cat_val)))

    app.add_handler(CallbackQueryHandler(button_handler))

    print("🤖 Bot de Telegram activo y escuchando...")
    app.run_polling()


if __name__ == "__main__":
    main()
