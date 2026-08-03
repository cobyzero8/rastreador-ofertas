# scrapers_cupones.py
import os
import re
import requests
from bs4 import BeautifulSoup
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# Mapeo completo ajustado a tu lista de tiendas
MAPA_FUENTES = {
    "ADIDAS": [
        {"url": "https://www.picodi.com/pe/adidas", "origen": "PICODI"},
        {"url": "https://www.cupon.pe/adidas", "origen": "CUPON_PE"}
    ],
    "CARSA": [
        {"url": "https://www.picodi.com/pe/carsa", "origen": "PICODI"}
    ],
    "COOLBOX": [
        {"url": "https://www.picodi.com/pe/coolbox", "origen": "PICODI"},
        {"url": "https://www.cupon.pe/coolbox", "origen": "CUPON_PE"}
    ],
    "CURACAO": [
        {"url": "https://www.picodi.com/pe/la-curacao", "origen": "PICODI"}
    ],
    "CYZONE": [
        {"url": "https://www.picodi.com/pe/cyzone", "origen": "PICODI"}
    ],
    "EFE": [
        {"url": "https://www.picodi.com/pe/tiendas-efe", "origen": "PICODI"}
    ],
    "ESIKA": [
        {"url": "https://www.picodi.com/pe/esika", "origen": "PICODI"}
    ],
    "ESTILOS": [
        {"url": "https://www.picodi.com/pe/estilos", "origen": "PICODI"}
    ],
    "FALABELLA": [
        {"url": "https://www.picodi.com/pe/falabella", "origen": "PICODI"},
        {"url": "https://www.cupon.pe/falabella", "origen": "CUPON_PE"}
    ],
    "FOOTLOOSE": [
        {"url": "https://www.picodi.com/pe/footloose", "origen": "PICODI"},
        {"url": "https://www.cupon.pe/footloose", "origen": "CUPON_PE"}
    ],
    "HIRAOKA": [
        {"url": "https://www.picodi.com/pe/hiraoka", "origen": "PICODI"}
    ],
    "JBL": [
        {"url": "https://www.picodi.com/pe/jbl", "origen": "PICODI"}
    ],
    "JUNTOZ": [
        {"url": "https://www.picodi.com/pe/juntoz", "origen": "PICODI"}
    ],
    "LBEL": [
        {"url": "https://www.picodi.com/pe/lbel", "origen": "PICODI"}
    ],
    "NIKE": [
        {"url": "https://www.picodi.com/pe/nike", "origen": "PICODI"},
        {"url": "https://www.cupon.pe/nike", "origen": "CUPON_PE"}
    ],
    "OECHSLE": [
        {"url": "https://www.picodi.com/pe/oechsle", "origen": "PICODI"},
        {"url": "https://www.cupon.pe/oechsle", "origen": "CUPON_PE"}
    ],
    "PLATANITOS": [
        {"url": "https://www.picodi.com/pe/platanitos", "origen": "PICODI"}
    ],
    "PLAZA_VEA": [
        {"url": "https://www.picodi.com/pe/plaza-vea", "origen": "PICODI"},
        {"url": "https://www.cupon.pe/plaza-vea", "origen": "CUPON_PE"}
    ],
    "PROMART": [
        {"url": "https://www.picodi.com/pe/promart", "origen": "PICODI"},
        {"url": "https://www.cupon.pe/promart", "origen": "CUPON_PE"}
    ],
    "THN": [
        {"url": "https://www.picodi.com/pe/thn", "origen": "PICODI"}
    ],
    "TRIATHLON": [
        {"url": "https://www.picodi.com/pe/triathlon", "origen": "PICODI"}
    ]
}

# Palabras clave a descartar
PALABRAS_IGNORAR = {
    "PICODI", "OFERTA", "VER", "CUPON", "DESCUENTO", "PERU", "ENVIO", 
    "GRATIS", "HASTA", "ONLINE", "TIENDA", "COMPRA", "NUEVO", "PAGINA",
    "PAGO", "DETALLES", "MAS", "MENOS", "TODOS", "SABER", "AQUI", "VERBAL",
    "CUPONES", "OFERTAS", "SITIO", "WEB", "CONSIGUE", "HAZ", "CLIC"
}

def guardar_cupon_db(supabase, tienda, codigo, descripcion, origen):
    try:
        datos = {
            "tienda": tienda.upper(),
            "codigo": codigo.strip().upper(),
            "descripcion": descripcion.strip(),
            "origen": origen,
            "activo": True
        }
        supabase.table("cupones").upsert(datos, on_conflict="codigo").execute()
        print(f"  ✅ Cupón guardado: [{tienda}] {codigo} ({origen})")
    except Exception as e:
        print(f"  ⚠️ Error guardando cupón {codigo}: {e}")

def extraer_cupones_de_url(url, headers):
    try:
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code != 200:
            return []
            
        soup = BeautifulSoup(resp.text, 'html.parser')
        encontrados = []
        
        bloques = soup.find_all(['div', 'article', 'li'], class_=re.compile(r'(offer|coupon|promo|deal)', re.I))
        
        for b in bloques:
            txt = b.get_text()
            
            cand_codigos = re.findall(r'\b[A-Z0-9]{4,15}\b', txt)
            codigos_validos = [c for c in cand_codigos if c not in PALABRAS_IGNORAR and not c.isdigit()]
            
            if codigos_validos:
                tit_el = b.find(['h3', 'h4', 'p', 'span'], class_=re.compile(r'(title|name|desc|header)', re.I))
                desc = tit_el.get_text().strip()[:70] if tit_el else "Descuento en tienda"
                desc = re.sub(r'\s+', ' ', desc)
                
                for cod in codigos_validos:
                    encontrados.append((cod, desc))
                    
        return encontrados
    except Exception as e:
        print(f"  🛑 Error al conectar con {url}: {e}")
        return []

def ejecutar_escaneo_cupones_web():
    if not SUPABASE_KEY or not SUPABASE_URL:
        print("🛑 Error: SUPABASE_URL o SUPABASE_KEY no están configurados.")
        return

    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    print("🚀 Iniciando extracción web de cupones para tiendas monitoreadas...")

    total_guardados = 0
    for tienda, fuentes in MAPA_FUENTES.items():
        print(f"\n🔍 Buscando cupones para {tienda}...")
        for fuente in fuentes:
            cupones = extraer_cupones_de_url(fuente['url'], headers)
            for codigo, descripcion in cupones:
                guardar_cupon_db(supabase, tienda, codigo, descripcion, fuente['origen'])
                total_guardados += 1

    print(f"\n✨ Finalizado. Se procesaron {total_guardados} referencias de cupones.")

if __name__ == "__main__":
    ejecutar_escaneo_cupones_web()
