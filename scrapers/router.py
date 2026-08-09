from urllib.parse import urlparse
from utils import safe_log

# Importar scrapers individuales desde la carpeta scrapers
from .falabella import motor_falabella
from .oechsle import escanear_oechsle
from .hiraoka import escanear_hiraoka
from .plazavea import escanear_plazavea
from .coolbox import escanear_coolbox
from .platanitos import escanear_platanitos
from .adidas import escanear_adidas
from .nike import escanear_nike
from .thn import escanear_thn
from .juntoz import escanear_juntoz
from .estilos import escanear_estilos
from .promart import escanear_promart
from .carsas import escanear_carsas
from .triathlon import escanear_triathlon
from .footloose import escanear_footloose
from .belcorp import escanear_belcorp
from .general import escanear_general


def escanear_tienda(url: str, tienda: str = "GENERAL", precio_max: float = 999999.0):
    """
    Enruta la URL hacia el scraper correspondiente según el dominio o el nombre de la tienda.
    """
    if not url or not url.startswith("http"):
        return []

    tienda_upper = str(tienda).upper().strip()
    domain = urlparse(url).netloc.lower()

    safe_log(f"🔎 [Enrutador] Analizando URL: {url} | Tienda: {tienda_upper}", "info")

    try:
        if "falabella.com" in domain or tienda_upper == "FALABELLA":
            return escanear_falabella(url, precio_max)
        elif "oechsle.pe" in domain or tienda_upper == "OECHSLE":
            return escanear_oechsle(url, precio_max)
        elif "hiraoka.com.pe" in domain or tienda_upper == "HIRAOKA":
            return escanear_hiraoka(url, precio_max)
        elif "plazavea.com.pe" in domain or tienda_upper in ["PLAZA_VEA", "PLAZAVEA"]:
            return escanear_plazavea(url, precio_max)
        elif "coolbox.pe" in domain or tienda_upper == "COOLBOX":
            return escanear_coolbox(url, precio_max)
        elif "platanitos.com" in domain or tienda_upper == "PLATANITOS":
            return escanear_platanitos(url, precio_max)
        elif "adidas.pe" in domain or tienda_upper == "ADIDAS":
            return escanear_adidas(url, precio_max)
        elif "nike.com" in domain or tienda_upper == "NIKE":
            return escanear_nike(url, precio_max)
        elif "thn.pe" in domain or tienda_upper == "THN":
            return escanear_thn(url, precio_max)
        elif "juntoz.com" in domain or tienda_upper == "JUNTOZ":
            return escanear_juntoz(url, precio_max)
        elif "estilos.com.pe" in domain or tienda_upper == "ESTILOS":
            return escanear_estilos(url, precio_max)
        elif "promart.pe" in domain or tienda_upper == "PROMART":
            return escanear_promart(url, precio_max)
        elif "carsa.pe" in domain or tienda_upper == "CARSA":
            return escanear_carsas(url, precio_max)
        elif "triathlon.com.pe" in domain or tienda_upper == "TRIATHLON":
            return escanear_triathlon(url, precio_max)
        elif "footloose.pe" in domain or tienda_upper == "FOOTLOOSE":
            return escanear_footloose(url, precio_max)
        elif "tiendabelcorp.com.pe" in domain or tienda_upper in ["CYZONE", "ESIKA", "LBEL"]:
            return escanear_belcorp(url, precio_max)
        else:
            return escanear_general(url, precio_max)
            
    except Exception as e:
        safe_log(f"❌ Error en enrutador para {tienda_upper}: {e}", "error")
        return []
