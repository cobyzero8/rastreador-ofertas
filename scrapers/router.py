from urllib.parse import urlparse
from utils import safe_log

from .falabella import motor_falabella
from .oechsle import motor_oechsle
from .hiraoka import motor_hiraoka
from .plazavea import motor_plazavea
from .coolbox import motor_coolbox
from .platanitos import motor_platanitos
from .adidas import motor_adidas
from .nike import motor_nike
from .thn import motor_thn
from .juntoz import motor_juntoz
from .estilos import motor_estilos
from .promart import motor_promart
from .carsa import motor_carsa
from .triathlon import motor_triathlon
from .footloose import motor_footloose
from .conecta_retail import motor_conecta_retail
from .general import motor_tradicional_general
from .belcorp import motor_belcorp
from .jbl import motor_jbl



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
        # 🟢 1. CURACAO y EFE (Conecta Retail)
        if "lacuracao.pe" in domain or "efe.com.pe" in domain or tienda_upper in ["CURACAO", "EFE", "CONECTA_RETAIL"]:
            return motor_conecta_retail(url, precio_max)

        # 2. Demás tiendas individuales
        elif "falabella.com" in domain or tienda_upper == "FALABELLA":
            return motor_falabella(url, precio_max)
        elif "oechsle.pe" in domain or tienda_upper == "OECHSLE":
            return motor_oechsle(url, precio_max)
        elif "hiraoka.com.pe" in domain or tienda_upper == "HIRAOKA":
            return motor_hiraoka(url, precio_max)
        elif "plazavea.com.pe" in domain or tienda_upper in ["PLAZA_VEA", "PLAZAVEA"]:
            return motor_plazavea(url, precio_max)
        elif "coolbox.pe" in domain or tienda_upper == "COOLBOX":
            return motor_coolbox(url, precio_max)
        elif "platanitos.com" in domain or "PLATANITOS" in tienda_upper:
            return motor_platanitos(url, precio_max)
        elif "adidas.pe" in domain or tienda_upper == "ADIDAS":
            return motor_adidas(url, precio_max)
        elif "nike.com" in domain or tienda_upper == "NIKE":
            return motor_nike(url, precio_max)
        elif "thn.pe" in domain or tienda_upper == "THN":
            return motor_thn(url, precio_max)
        elif "juntoz.com" in domain or tienda_upper == "JUNTOZ":
            return motor_juntoz(url, precio_max)
        elif "estilos.com.pe" in domain or tienda_upper == "ESTILOS":
            return motor_estilos(url, precio_max)
        elif "promart.pe" in domain or tienda_upper == "PROMART":
            return motor_promart(url, precio_max)
        elif "carsa.pe" in domain or tienda_upper == "CARSA":
            return motor_carsa(url, precio_max)
        elif "triathlon.com.pe" in domain or tienda_upper == "TRIATHLON":
            return motor_triathlon(url, precio_max)
        elif "footloose.pe" in domain or tienda_upper == "FOOTLOOSE":
            return motor_footloose(url, precio_max)
        elif "tiendabelcorp.com.pe" in domain or tienda_upper in ["CYZONE", "ESIKA", "LBEL", "BELCORP"]:
            return motor_belcorp(url, precio_max)
        elif "jbl.com.pe" in domain or "JBL" in tienda_upper:
            return motor_jbl(url, precio_max)
        
        else:
            return motor_tradicional_general(url, precio_max)
            
    except Exception as e:
        safe_log(f"❌ Error en enrutador para {tienda_upper}: {e}", "error")
        return []
