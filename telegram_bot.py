import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from patrol import revisar_ofertas

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Seguridad: Restringe el uso exclusivo a tu chat personal
CHAT_ID_AUTORIZADO = os.environ.get("TELEGRAM_CHAT_ID", "")

def es_usuario_valido(update: Update) -> bool:
    if not CHAT_ID_AUTORIZADO:
        return True
    return str(update.effective_chat.id) == str(CHAT_ID_AUTORIZADO)

# ---------------------------------------------------------
# Listas Oficiales
# ---------------------------------------------------------
TIENDAS = [
    "JUNTOZ", "CYZONE", "ADIDAS", "PLATANITOS", "JBL", "ESIKA", "RIPLEY", 
    "LBEL", "COOLBOX", "FALABELLA", "PROMART", "HIRAOKA", "THN", "ESTILOS", 
    "FOOTLOOSE", "EFE", "NIKE", "TRIATHLON", "PLAZA_VEA", "CURACAO", "OECHSLE", "CARSA"
]

CATEGORIAS = [
    "PERFUMES", "ZAPATILLAS", "POLOS", "CASACAS", "SHORTS", "BUZOS", 
    "MEDIAS", "AUDIFONOS", "TV", "PARLANTE", "CELULAR", "LAVADORA", "CAMA"
]

def obtener_teclado_inicio():
    keyboard = [
        [InlineKeyboardButton("🚀 Forzar Patrullaje Completo", callback_data="run_TODOS")],
        [InlineKeyboardButton("🏬 Menú de Tiendas", callback_data="menu_tiendas"),
         InlineKeyboardButton("🏷️ Menú de Categorías", callback_data="menu_categorias")]
    ]
    return InlineKeyboardMarkup(keyboard)

# ---------------------------------------------------------
# Controladores
# ---------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not es_usuario_valido(update): return
    
    texto = "🤖 *Central de Control - Cazador de Ofertas*\n\nSelecciona una opción interactiva o usa los comandos directos:"
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(texto, reply_markup=obtener_teclado_inicio(), parse_mode="Markdown")
    else:
        await update.message.reply_text(texto, reply_markup=obtener_teclado_inicio(), parse_mode="Markdown")

async def ejecutar_escaneo(update: Update, context: ContextTypes.DEFAULT_TYPE, filtro: str):
    filtro_limpio = filtro.replace("_", " ")
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(f"🔍 Escaneando filtro: *{filtro_limpio}*...", parse_mode="Markdown")
        chat_id = query.message.chat_id
    else:
        await update.message.reply_text(f"🔍 Escaneando filtro: *{filtro_limpio}*...", parse_mode="Markdown")
        chat_id = update.effective_chat.id
        
    resumen = revisar_ofertas(filtro)
    
    await context.bot.send_message(
        chat_id=chat_id, 
        text=f"✅ Escaneo [{filtro_limpio}] finalizado:\n\n{resumen}"
    )

async def menu_tiendas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not es_usuario_valido(update): return

    keyboard = [[InlineKeyboardButton(TIENDAS[i], callback_data=f"run_{TIENDAS[i]}"),
                 InlineKeyboardButton(TIENDAS[i+1], callback_data=f"run_{TIENDAS[i+1]}")] 
                for i in range(0, len(TIENDAS)-1, 2)]
    if len(TIENDAS) % 2 != 0:
        keyboard.append([InlineKeyboardButton(TIENDAS[-1], callback_data=f"run_{TIENDAS[-1]}")])
        
    keyboard.append([InlineKeyboardButton("⬅️ Volver al Menú", callback_data="menu_start")])
    
    texto = "🏬 *Selecciona una Tienda:*"
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(texto, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(texto, reply_markup=reply_markup, parse_mode="Markdown")

async def menu_categorias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not es_usuario_valido(update): return

    keyboard = [[InlineKeyboardButton(CATEGORIAS[i], callback_data=f"run_{CATEGORIAS[i]}"),
                 InlineKeyboardButton(CATEGORIAS[i+1], callback_data=f"run_{CATEGORIAS[i+1]}")] 
                for i in range(0, len(CATEGORIAS)-1, 2)]
    if len(CATEGORIAS) % 2 != 0:
        keyboard.append([InlineKeyboardButton(CATEGORIAS[-1], callback_data=f"run_{CATEGORIAS[-1]}")])
        
    keyboard.append([InlineKeyboardButton("⬅️ Volver al Menú", callback_data="menu_start")])
    
    texto = "🏷️ *Selecciona una Categoría:*"
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(texto, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(texto, reply_markup=reply_markup, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not es_usuario_valido(update): return
    query = update.callback_query
    data = query.data
    
    if data == "menu_start":
        await start(update, context)
    elif data == "menu_tiendas":
        await menu_tiendas(update, context)
    elif data == "menu_categorias":
        await menu_categorias(update, context)
    elif data.startswith("run_"):
        filtro = data.replace("run_", "")
        await ejecutar_escaneo(update, context, filtro)

# ---------------------------------------------------------
# Inicialización
# ---------------------------------------------------------
def main():
    token = os.environ.get("TELEGRAM_TOKEN")
    if not token:
        print("❌ Error: TELEGRAM_TOKEN no configurado en variables de entorno.")
        return
    
    app = ApplicationBuilder().token(token).build()
    
    # Comandos Principales
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tiendas", menu_tiendas))
    app.add_handler(CommandHandler("categorias", menu_categorias))
    app.add_handler(CommandHandler("forzar_todo", lambda u, c: ejecutar_escaneo(u, c, "TODOS")))
    
    # Comandos por Tienda (/tienda_ripley, /tienda_nike, etc.)
    for tienda in TIENDAS:
        cmd = f"tienda_{tienda.lower()}"
        app.add_handler(CommandHandler(cmd, lambda u, c, t=tienda: ejecutar_escaneo(u, c, t)))
        
    # Comandos por Categoría (/cat_zapatillas, /cat_tv, etc.)
    for cat in CATEGORIAS:
        cmd = f"cat_{cat.lower()}"
        app.add_handler(CommandHandler(cmd, lambda u, c, cat_val=cat: ejecutar_escaneo(u, c, cat_val)))
        
    app.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Bot de Telegram activo y escuchando comandos...")
    app.run_polling()

if __name__ == "__main__":
    main()
