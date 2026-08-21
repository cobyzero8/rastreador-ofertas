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

# ---------------------------------------------------------
# Control de Acceso Privado (Administradores)
# ---------------------------------------------------------
ADMIN_IDS_RAW = os.environ.get("TELEGRAM_CHAT_ID") or os.environ.get("TELEGRAM_ADMIN_ID", "")
ADMINS_AUTORIZADOS = [aid.strip() for aid in ADMIN_IDS_RAW.split(",") if aid.strip()]


async def es_usuario_valido(update: Update) -> bool:
    if not ADMINS_AUTORIZADOS:
        logger.warning("⚠️ No hay IDs de Administrador configurados. Acceso totalmente bloqueado.")
        return False

    chat_actual = str(update.effective_chat.id)

    if chat_actual in ADMINS_AUTORIZADOS:
        return True

    logger.warning(f"⚠️ Intento de acceso no autorizado desde ID: [{chat_actual}]")

    mensaje_bloqueo = "🚫 <b>Acceso Restringido.</b>\nEste bot es privado y solo responde a administradores autorizados."

    if update.callback_query:
        await update.callback_query.answer("🚫 No tienes permisos.", show_alert=True)
    elif update.message:
        await update.message.reply_html(mensaje_bloqueo)

    return False


async def borrar_mensaje_usuario(update: Update):
    """Borra inmediatamente el comando escrito por el usuario para dejar el chat limpio."""
    if update.message:
        try:
            await update.message.delete()
        except Exception:
            pass


async def borrar_menu_previo(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    """Borra el mensaje del menú interactivo anterior para evitar duplicados."""
    menu_id = context.user_data.get("menu_message_id")
    if menu_id:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=menu_id)
        except Exception:
            pass
        context.user_data["menu_message_id"] = None


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
# Controladores Principales (/coby e /itzel)
# ---------------------------------------------------------

async def comando_coby(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra el menú principal, elimina el texto /coby y borra el menú anterior."""
    if not await es_usuario_valido(update): return
    chat_id = update.effective_chat.id

    await borrar_mensaje_usuario(update)
    await borrar_menu_previo(context, chat_id)

    texto = "🤖 <b>CENTRAL DE CONTROL - COBY CAZADOR</b>\n\nSelecciona una opción para patrullar en tiempo real:"

    if update.callback_query:
        query = update.callback_query
        await query.answer()

    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=texto,
        reply_markup=obtener_teclado_inicio(),
        parse_mode="HTML"
    )
    context.user_data["menu_message_id"] = msg.message_id


async def comando_itzel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Elimina el menú activo y el comando /itzel escrito por el usuario."""
    if not await es_usuario_valido(update): return
    chat_id = update.effective_chat.id

    await borrar_mensaje_usuario(update)
    await borrar_menu_previo(context, chat_id)


async def ejecutar_escaneo(update: Update, context: ContextTypes.DEFAULT_TYPE, filtro: str):
    """Ejecuta el escaneo borrando la orden escrita por el usuario."""
    if not await es_usuario_valido(update): return
    chat_id = update.effective_chat.id

    await borrar_mensaje_usuario(update)

    filtro_limpio = filtro.replace("_", " ")

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        try:
            await query.edit_message_text(f"🔍 Escaneando filtro: *{filtro_limpio}*...", parse_mode="Markdown")
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=f"🔍 Escaneando filtro: *{filtro_limpio}*...", parse_mode="Markdown")
    else:
        await context.bot.send_message(chat_id=chat_id, text=f"🔍 Escaneando filtro: *{filtro_limpio}*...", parse_mode="Markdown")

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
    """Despliega la lista de tiendas borrando el mensaje del usuario."""
    if not await es_usuario_valido(update): return
    chat_id = update.effective_chat.id

    await borrar_mensaje_usuario(update)
    await borrar_menu_previo(context, chat_id)

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

    texto = "🏢 <b>SELECCIONA UNA TIENDA PARA PATRULLAR:</b>"
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()

    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=texto,
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    context.user_data["menu_message_id"] = msg.message_id


async def menu_categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Despliega la lista de categorías borrando el mensaje del usuario."""
    if not await es_usuario_valido(update): return
    chat_id = update.effective_chat.id

    await borrar_mensaje_usuario(update)
    await borrar_menu_previo(context, chat_id)

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

    texto = "🏷️ <b>SELECCIONA UNA CATEGORÍA PARA PATRULLAR:</b>"
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()

    msg = await context.bot.send_message(
        chat_id=chat_id,
        text=texto,
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
    await borrar_mensaje_usuario(update)
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
