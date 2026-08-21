import os
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from patrol import revisar_ofertas

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Permite obtener la ID de chat autorizada desde TELEGRAM_CHAT_ID o TELEGRAM_ADMIN_ID
CHAT_ID_AUTORIZADO = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_ADMIN_ID", "")

# 🖼️ Enlace de la imagen banner principal para los menús
URL_BANNER_TIENDAS = "https://images.unsplash.com/photo-1526304640581-d334cdbbf45e?q=80&w=1000"


async def es_usuario_valido(update: Update) -> bool:
    if not CHAT_ID_AUTORIZADO:
        return True

    chat_actual = str(update.effective_chat.id)
    chat_permitido = str(CHAT_ID_AUTORIZADO).strip()

    if chat_actual == chat_permitido:
        return True

    logger.warning(f"⚠️ Acceso denegado en Telegram. Tu ID es: [{chat_actual}] | Configurado: [{chat_permitido}]")

    mensaje_denegado = (
        f"🚫 *Acceso no autorizado*\n\n"
        f"Tu ID actual de Telegram es: `{chat_actual}`\n"
        f"ID configurado: `{chat_permitido}`\n\n"
        f"Asegúrate de registrar tu ID en `TELEGRAM_CHAT_ID`."
    )

    if update.callback_query:
        await update.callback_query.answer("Acceso denegado", show_alert=True)
        if update.callback_query.message:
            await update.callback_query.message.reply_text(mensaje_denegado, parse_mode="Markdown")
    elif update.message:
        await update.message.reply_text(mensaje_denegado, parse_mode="Markdown")

    return False


# ---------------------------------------------------------
# Listas Oficiales de Tiendas Monitoreadas
# ---------------------------------------------------------
TIENDAS = [
    "ADIDAS", "CARSA", "COOLBOX", "CURACAO", "CYZONE", "EFE",
    "ESIKA", "ESTILOS", "FALABELLA", "FOOTLOOSE", "HIRAOKA", "JBL",
    "JUNTOZ", "LBEL", "NIKE", "OECHSLE", "PLATANITOS", "PLAZA_VEA",
    "PROMART", "RIPLEY", "THN", "TRIATHLON"
]

# ---------------------------------------------------------
# Mapeo Oficial de Categorías
# ---------------------------------------------------------
CATEGORIAS_MAP = {
    "PERFUMES": "🧪 PERFUMES",
    "ZAPATILLAS": "👟 ZAPATILLAS",
    "POLOS": "👕 POLOS",
    "CASACAS": "🧥 CASACAS",
    "SHORTS": "🩳 SHORTS",
    "BUZOS": "👖 BUZOS",
    "MEDIAS": "🧦 MEDIAS",
    "AUDIFONOS": "🎧 AUDÍFONOS",
    "TV": "📺 TV",
    "PARLANTE": "🔊 PARLANTE",
    "BARRA_DE_SONIDO": "🎵 B. SONIDO",
    "CELULAR": "📱 CELULAR",
    "PC": "💻 PC / LAPTOP",
    "REFRIGERADORA": "❄️ REFRIGERADORA",
    "LAVADORA": "🧺 LAVADORA",
    "ELECTRODOMESTICOS": "🔌 ELECTRODOM.",
    "CAMA": "🛏️ CAMA",
    "OTROS": "📦 OTROS"
}

CATEGORIAS = list(CATEGORIAS_MAP.keys())


def obtener_teclado_inicio():
    keyboard = [
        [InlineKeyboardButton("【 🚀 FORZAR PATRULLAJE COMPLETO 】", callback_data="run_TODOS")],
        [InlineKeyboardButton("【 🏬 MENÚ DE TIENDAS 】", callback_data="menu_tiendas")],
        [InlineKeyboardButton("【 🏷️ MENÚ DE CATEGORÍAS 】", callback_data="menu_categorias")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ---------------------------------------------------------
# Controladores Principales (/coby y /itzel)
# ---------------------------------------------------------

async def comando_coby(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú principal con banner y botones llamativos."""
    if not await es_usuario_valido(update): return
    chat_id = update.effective_chat.id

    # Si había un menú activo previo, lo borramos para evitar duplicados
    menu_previo_id = context.user_data.get("menu_message_id")
    if menu_previo_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=menu_previo_id)
        except Exception:
            pass

    texto = "<b>🤖 CENTRAL DE CONTROL - COBY CAZADOR</b>\n\nSelecciona una opción para patrullar en tiempo real:"

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass

    msg = await context.bot.send_photo(
        chat_id=chat_id,
        photo=URL_BANNER_TIENDAS,
        caption=texto,
        reply_markup=obtener_teclado_inicio(),
        parse_mode="HTML"
    )
    context.user_data["menu_message_id"] = msg.message_id


async def comando_itzel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elimina el menú interactivo activo del chat."""
    if not await es_usuario_valido(update): return
    chat_id = update.effective_chat.id

    # Borrar la orden /itzel que escribió el usuario para dejar el chat impecable
    if update.message:
        try:
            await update.message.delete()
        except Exception:
            pass

    # Borrar el mensaje del menú activo
    menu_id = context.user_data.get("menu_message_id")
    if menu_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=menu_id)
        except Exception as e:
            logger.warning(f"No se pudo borrar el menú: {e}")
        context.user_data["menu_message_id"] = None


async def ejecutar_escaneo(update: Update, context: ContextTypes.DEFAULT_TYPE, filtro: str):
    if not await es_usuario_valido(update): return

    filtro_limpio = filtro.replace("_", " ")

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        chat_id = query.message.chat_id
        
        if query.message.photo:
            await context.bot.send_message(chat_id=chat_id, text=f"🔍 Escaneando filtro: *{filtro_limpio}*...", parse_mode="Markdown")
        else:
            await query.edit_message_text(f"🔍 Escaneando filtro: *{filtro_limpio}*...", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"🔍 Escaneando filtro: *{filtro_limpio}*...", parse_mode="Markdown")
        chat_id = update.effective_chat.id

    try:
        resumen = await asyncio.to_thread(revisar_ofertas, filtro)

        await context.bot.send_message(
            chat_id=chat_id, 
            text=f"✅ Escaneo [{filtro_limpio}] finalizado:\n\n{resumen}"
        )
    except Exception as e:
        logger.error(f"Error ejecutando escaneo para {filtro}: {e}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Ocurrió un error al procesar el escaneo de *{filtro_limpio}*:\n`{e}`",
            parse_mode="Markdown"
        )


async def menu_tiendas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_usuario_valido(update): return

    keyboard = []
    for i in range(0, len(TIENDAS), 2):
        fila = []
        btn1 = InlineKeyboardButton(f"【 🏪 {TIENDAS[i]} 】", callback_data=f"run_{TIENDAS[i]}")
        fila.append(btn1)
        if i + 1 < len(TIENDAS):
            btn2 = InlineKeyboardButton(f"【 🏪 {TIENDAS[i+1]} 】", callback_data=f"run_{TIENDAS[i+1]}")
            fila.append(btn2)
        keyboard.append(fila)

    keyboard.append([InlineKeyboardButton("【 ⬅️ VOLVER AL MENÚ 】", callback_data="menu_start")])

    texto = "<b>🏢 SELECCIONA UNA TIENDA PARA PATRULLAR:</b>"
    reply_markup = InlineKeyboardMarkup(keyboard)

    query = update.callback_query
    if query:
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass

    msg = await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=URL_BANNER_TIENDAS,
        caption=texto,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    context.user_data["menu_message_id"] = msg.message_id


async def menu_categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_usuario_valido(update): return

    keyboard = []
    keys = list(CATEGORIAS_MAP.keys())
    for i in range(0, len(keys), 2):
        fila = []
        k1 = keys[i]
        fila.append(InlineKeyboardButton(f"【 {CATEGORIAS_MAP[k1]} 】", callback_data=f"run_{k1}"))
        if i + 1 < len(keys):
            k2 = keys[i+1]
            fila.append(InlineKeyboardButton(f"【 {CATEGORIAS_MAP[k2]} 】", callback_data=f"run_{k2}"))
        keyboard.append(fila)

    keyboard.append([InlineKeyboardButton("【 ⬅️ VOLVER AL MENÚ 】", callback_data="menu_start")])

    texto = "<b>🏷️ SELECCIONA UNA CATEGORÍA PARA PATRULLAR:</b>"
    reply_markup = InlineKeyboardMarkup(keyboard)

    query = update.callback_query
    if query:
        await query.answer()
        try:
            await query.message.delete()
        except Exception:
            pass

    msg = await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=URL_BANNER_TIENDAS,
        caption=texto,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
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
        filtro = data.replace("run_", "")
        await ejecutar_escaneo(update, context, filtro)


async def comando_desconocido(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_usuario_valido(update): return
    await update.message.reply_text(
        "⚠️ *Comando no reconocido o mal escrito.*\n\n"
        "Usa `/coby` para abrir el menú principal de ofertas o `/itzel` para ocultarlo.",
        parse_mode="Markdown"
    )


async def manejador_errores(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"🚨 Error no capturado en Telegram: {context.error}")


# ---------------------------------------------------------
# Inicialización
# ---------------------------------------------------------
def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        print("❌ Error: TELEGRAM_TOKEN no configurado en variables de entorno.")
        return

    app = ApplicationBuilder().token(token).build()

    # Comandos Especiales de Mostrar / Ocultar
    app.add_handler(CommandHandler(["coby", "start"], comando_coby))
    app.add_handler(CommandHandler("itzel", comando_itzel))

    # Comandos Directos
    app.add_handler(CommandHandler("tiendas", menu_tiendas))
    app.add_handler(CommandHandler("categorias", menu_categorias))
    app.add_handler(CommandHandler("forzar_todo", lambda u, c: ejecutar_escaneo(u, c, "TODOS")))

    # Comandos por Tienda
    for tienda in TIENDAS:
        cmd = f"tienda_{tienda.lower()}"
        app.add_handler(CommandHandler(cmd, lambda u, c, t=tienda: ejecutar_escaneo(u, c, t)))

    # Comandos por Categoría
    for cat in CATEGORIAS:
        cmd = f"cat_{cat.lower()}"
        app.add_handler(CommandHandler(cmd, lambda u, c, cat_val=cat: ejecutar_escaneo(u, c, cat_val)))

    app.add_handler(CallbackQueryHandler(button_handler))

    # Manejador para comandos no registrados
    app.add_handler(MessageHandler(filters.COMMAND, comando_desconocido))

    # Manejador global de excepciones
    app.add_error_handler(manejador_errores)

    print("🤖 Bot de Telegram activo y escuchando comandos...")
    app.run_polling()


if __name__ == "__main__":
    main()
