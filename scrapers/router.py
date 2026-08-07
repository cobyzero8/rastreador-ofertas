from urllib.parse import urlparse
from utils import sanitizar_url, safe_log

from .thn import motor_thn
from .belcorp import motor_belcorp
from .conecta_retail import motor_conecta_retail
from .falabella import motor_falabella
from .adidas import motor_adidas
from .platanitos import motor_platanitos
from .hiraoka import motor_hiraoka
from .carsas import motor_carsa
from .oechsle import motor_oechsle
from .plazavea import motor_plazavea
from .juntoz import motor_juntoz
from .triathlon import motor_triathlon
from .ripley import motor_ripley
from .footloose import motor_footloose
from .estilos import motor_estilos
from .promart import motor_promart
from .coolbox import motor_coolbox
from .nike import motor_nike
from .general import motor_tradicional_general

def escanear_tienda(url, limite, headers=None):
    url = sanitizar_url(url)
    dominio = urlparse(url).netloc.lower()
    
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
    
    safe_log(f"🔎 [Enrutador] Analizando URL: {url} | Dominio: {dominio}", "info")
    
    if "carsa.pe" in dominio: return motor_carsa(url, limite)
    elif "thn.pe" in dominio: return motor_thn(url, limite)
    elif any(k in dominio for k in ["tiendabelcorp", "cyzone", "lbel", "esika"]): return motor_belcorp(url, limite, headers)
    elif "efe.com.pe" in dominio or "lacuracao.pe" in dominio: return motor_conecta_retail(url, limite, headers, "EFE" if "efe.com.pe" in dominio else "CURACAO")
    elif "falabella.com" in dominio: return motor_falabella(url, limite, headers)
    elif "adidas.pe" in dominio: return motor_adidas(url, limite)
    elif "platanitos.com" in dominio: return motor_platanitos(url, limite)
    elif "hiraoka.com.pe" in dominio: return motor_hiraoka(url, limite)
    elif "oechsle.pe" in dominio: return motor_oechsle(url, limite)
    elif "plazavea.com.pe" in dominio: return motor_plazavea(url, limite, headers=headers)
    elif "juntoz.com" in dominio: return motor_juntoz(url, limite, headers=headers)
    elif "triathlon.com.pe" in dominio: return motor_triathlon(url, limite, headers=headers)
    elif "ripley.com.pe" in dominio: return motor_ripley(url, limite, headers=headers)
    elif "footloose.pe" in dominio: return motor_footloose(url, limite)
    elif "estilos.com.pe" in dominio: return motor_estilos(url, limite)
    elif "promart.pe" in dominio: return motor_promart(url, limite, headers=headers)
    elif "coolbox.pe" in dominio: return motor_coolbox(url, limite, headers=headers)
    elif "nike.com.pe" in dominio: return motor_nike(url, limite)
    else: return motor_tradicional_general(url, limite, headers)
