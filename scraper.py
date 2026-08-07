import os
import subprocess
import json
import requests
import httpx
from bs4 import BeautifulSoup
import re
import time
import random
import hashlib
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse, parse_qs, quote, urlunparse, urlencode, unquote
from supabase import create_client, Client
import urllib3
import streamlit as st
from gestor_cupones import obtener_bloque_cupones_telegram

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# =======================================================
# 🛡️ CONFIGURACIÓN DE ENTORNO BLINDADA (CLI Y STREAMLIT)
# =======================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://uxornuepdxqlhzizjnhr.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
TELEGRAM_DEV_CHAT_ID = os.environ.get("TELEGRAM_DEV_CHAT_ID") or TELEGRAM_CHAT_ID

try:
    if hasattr(st, "secrets"):
        if "SUPABASE_URL" in st.secrets and st.secrets["SUPABASE_URL"]:
            SUPABASE_URL = st.secrets["SUPABASE_URL"]
        if "SUPABASE_KEY" in st.secrets and st.secrets["SUPABASE_KEY"]:
            SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
        if "TELEGRAM_TOKEN" in st.secrets and st.secrets["TELEGRAM_TOKEN"]:
            TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
        if "TELEGRAM_CHAT_ID" in st.secrets and st.secrets["TELEGRAM_CHAT_ID"]:
            TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
        if "TELEGRAM_DEV_CHAT_ID" in st.secrets and st.secrets["TELEGRAM_DEV_CHAT_ID"]:
            TELEGRAM_DEV_CHAT_ID = st.secrets["TELEGRAM_DEV_CHAT_ID"]
except Exception:
    pass

if not SUPABASE_URL or not SUPABASE_KEY or not SUPABASE_URL.startswith("http"):
    raise ValueError(f"Error crítico: Configuración de Supabase inválida. URL obtenida: '{SUPABASE_URL}'")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

LISTA_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0"
]

# =======================================================
# 🛠️ HERRAMIENTAS AUXILIARES GLOBALES
# =======================================================
def sanitizar_url(url_raw):
    """Limpia URLs de espacios, corchetes, marcas de formato Markdown o caracteres no deseados."""
    if not url_raw: return ""
    url = str(url_raw).strip()
    match = re.search(r'\((https?://[^\s)]+)\)', url)
    if match:
        url = match.group(1)
    url = re.sub(r'^[\[\'"]+|[\]\'"]+$', '', url).strip()
    return url

def safe_log(texto, tipo="text"):
    try:
        if tipo == "text" or tipo == "write": st.write(texto)
        elif tipo == "caption": st.caption(texto)
        elif tipo == "info": st.info(texto)
        elif tipo == "error": st.error(texto)
        elif tipo == "success": st.success(texto)
        elif tipo == "warning": st.warning(texto)
        elif tipo == "toast": st.toast(texto)
    except Exception:
        print(f"[{tipo.upper()}] {texto}")

def limpiar_precio_pnp(texto_precio):
    if not texto_precio: return 0.0
    try:
        texto = re.sub(r'[^\d.,]', '', texto_precio).strip()
        if not texto: return 0.0
        if ',' in texto and '.' in texto:
            if texto.rfind('.') > texto.rfind(','): texto = texto.replace(',', '')
            else: texto = texto.replace('.', '').replace(',', '.')
        else:
            if ',' in texto and len(texto.split(',')[-1]) != 2: texto = texto.replace(',', '')
            elif '.' in texto and len(texto.split('.')[-1]) != 2: texto = texto.replace('.', '')
            elif ',' in texto: texto = texto.replace(',', '.')
        match = re.findall(r'\d+\.\d+|\d+', texto)
        return float(match[0]) if match else 0.0
    except Exception: return 0.0

def safe_float(val):
    if val is None: return 0.0
    if isinstance(val, (int, float)): return float(val)
    return limpiar_precio_pnp(str(val))

def enviar_telegram_real(mensaje, link_producto="", url_imagen=""):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID: return False
    link_producto = sanitizar_url(link_producto)
    url_imagen = sanitizar_url(url_imagen)
    mensaje_html = f"{mensaje}\n\n👉 <a href='{link_producto}'><b>¡COMPRAR AQUÍ!</b></a>"
    url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto" if url_imagen else f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "parse_mode": "HTML"}
    
    if url_imagen: 
        if len(mensaje_html) > 1000:
            mensaje_html = mensaje[:850] + f"...\n\n👉 <a href='{link_producto}'><b>¡COMPRAR AQUÍ!</b></a>"
        payload["photo"], payload["caption"] = url_imagen, mensaje_html
    else: 
        payload["text"] = mensaje_html
        
    try: return requests.post(url_api, json=payload, timeout=10).status_code == 200
    except Exception: return False

def es_error_de_precio(precio_actual, precio_regular, precio_anterior=None, categoria="OTROS"):
    """
    Evalúa de forma precisa si una caída corresponde a un error/bug real.
    Exige un porcentaje de descuento real y un ahorro mínimo en Soles para evitar falsas alarmas.
    Retorna (Es_Error_Bool, Porcentaje_Descuento_o_Caida)
    """
    if precio_actual <= 0:
        return False, 0.0

    p_reg = max(precio_regular, precio_actual)
    ahorro_soles = p_reg - precio_actual
    descuento_pct = (ahorro_soles / p_reg) * 100.0 if p_reg > 0 else 0.0

    # Si la web usa un precio regular inflado (>= 9999.0 o >4x precio oferta), es un precio dummy
    es_precio_reg_ficticio_web = (p_reg >= 9999.0 or p_reg > precio_actual * 4.0)

    # Criterio 1: Descuento masivo publicado en la web (>= 75%) con ahorro significativo (>= S/. 30.00)
    if descuento_pct >= 75.0 and ahorro_soles >= 30.0 and not es_precio_reg_ficticio_web:
        return True, descuento_pct

    # Criterio 2: Caída brusca respecto al último precio en BD (>= 70%) con ahorro significativo
    if precio_anterior and precio_anterior > 0:
        caida_historica = ((precio_anterior - precio_actual) / precio_anterior) * 100.0
        ahorro_historico = precio_anterior - precio_actual
        if caida_historica >= 70.0 and ahorro_historico >= 30.0:
            return True, caida_historica

    # Criterio 3: Productos de alto valor vendidos a precio insólito (ej. TV/PC de S/. 300+ vendida a <= S/. 50)
    categorias_alto_valor = ["TV", "PC", "CELULAR", "REFRIGERADORA", "LAVADORA", "BARRA DE SONIDO"]
    if categoria in categorias_alto_valor and precio_actual <= 50.0 and p_reg >= 300.0 and not es_precio_reg_ficticio_web:
        return True, descuento_pct

    return False, descuento_pct

def extraer_productos_json_universal(nodo):
    coleccion = []
    if isinstance(nodo, dict):
        if any(k in nodo for k in ['displayName', 'productName', 'title', 'name']) and any(k in nodo for k in ['prices', 'price', 'salePrice', 'value']):
            nombre = nodo.get('displayName') or nodo.get('productName') or nodo.get('title') or nodo.get('name')
            if nombre and len(str(nombre).strip()) > 3: coleccion.append(nodo)
        for v in nodo.values(): coleccion.extend(extraer_productos_json_universal(v))
    elif isinstance(nodo, list):
        for item in nodo: coleccion.extend(extraer_productos_json_universal(item))
    return coleccion

def encontrar_foto_fala(nodo):
    if isinstance(nodo, str):
        if (nodo.startswith('http') or nodo.startswith('//')) and ('falabella' in nodo or 'media' in nodo or any(ext in nodo.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp'])) and '/product/' not in nodo: return nodo
    elif isinstance(nodo, dict):
        for k in ['imageUrl', 'src', 'url', 'thumbnail', 'image']:
            val = nodo.get(k)
            if isinstance(val, str) and (val.startswith('http') or val.startswith('//')) and len(val) > 10 and '/product/' not in val: return val
        for v in nodo.values():
            res = encontrar_foto_fala(v)
            if res: return res
    elif isinstance(nodo, list):
        for item in nodo:
            res = encontrar_foto_fala(item)
            if res: return res
    return ''

def extraer_numeros_dict(d, valores_aux):
    if isinstance(d, dict):
        d_keys_str = "".join(d.keys()).lower()
        if any(x in d_keys_str for x in ['size', 'talla', 'option', 'variant']):
            for sub_v in d.values(): extraer_numeros_dict(sub_v, valores_aux)
            return
        for k, v in d.items():
            if any(x in k.lower() for x in ['price', 'precio']):
                if isinstance(v, (int, float)): valores_aux.append(float(v))
                elif isinstance(v, str):
                    fv = limpiar_precio_pnp(v)
                    if fv > 0: valores_aux.append(fv)
            elif 'value' in k.lower():
                contexto_valido = any(x in str(d).lower() for x in ['price', 'precio', 'sale', 'list', 'oferta', 'regular', 'internet', 'cmr'])
                contexto_invalido = any(x in str(d).lower() for x in ['size', 'talla', 'option', 'variant', 'sku'])
                if contexto_valido and not contexto_invalido:
                    if isinstance(v, (int, float)): valores_aux.append(float(v))
                    elif isinstance(v, str):
                        fv = limpiar_precio_pnp(v)
                        if fv > 0: valores_aux.append(fv)
        for sub_v in d.values(): extraer_numeros_dict(sub_v, valores_aux)
    elif isinstance(d, list):
        for item in d: extraer_numeros_dict(item, valores_aux)

# =======================================================
# 🏥 SISTEMA DE AUTO-CURACIÓN Y SALUD (HEALTH CHECK)
# =======================================================
def notificar_desarrollador_caida(tienda: str, fallos: int, url_prueba: str):
    """Envía un reporte privado al desarrollador cuando un scraper falla repetidamente."""
    dev_chat = TELEGRAM_DEV_CHAT_ID or TELEGRAM_CHAT_ID
    if not TELEGRAM_TOKEN or not dev_chat:
        return
        
    mensaje_html = (
        f"🚨 <b>ALERTA DE INFRAESTRUCTURA (HEALTH CHECK)</b> 🚨\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🛠️ <b>Motor Afectado:</b> <code>{tienda}</code>\n"
        f"❌ <b>Fallos Consecutivos:</b> {fallos}\n"
        f"⚠️ <b>Diagnóstico:</b> El scraper devolvió 0 productos en {fallos} patrullajes seguidos.\n"
        f"🔍 <b>Causa probable:</b> Cambio en la estructura DOM/CSS o bloqueo anti-bot.\n\n"
        f"🔗 <a href='{url_prueba}'><b>Probar URL manualmente en navegador</b></a>"
    )
    
    url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": dev_chat,
        "text": mensaje_html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        requests.post(url_api, json=payload, timeout=10)
    except Exception as e:
        safe_log(f"Error enviando alerta dev: {e}", "warning")

def registrar_resultado_salud(supabase_client: Client, tienda: str, total_productos: int, url_origen: str):
    """
    Actualiza el estado de salud de la tienda.
    - Si total_productos > 0: Resetea fallos a 0 y marca GREEN.
    - Si total_productos == 0: Incrementa fallos acumulados (YELLOW con 1-2, RED con >= 3).
    """
    zona_peru = timezone(timedelta(hours=-5))
    ahora_iso = datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")
    
    fallos_actuales = 0
    try:
        res = supabase_client.table("health_checks").select("fallos_consecutivos").eq("tienda", tienda).execute()
        if res.data and len(res.data) > 0:
            fallos_actuales = res.data[0].get("fallos_consecutivos", 0)
    except Exception:
        pass
    
    if total_productos > 0:
        nuevos_fallos = 0
        nuevo_estado = "GREEN"
    else:
        nuevos_fallos = fallos_actuales + 1
        nuevo_estado = "RED" if nuevos_fallos >= 3 else "YELLOW"

    datos_actualizar = {
        "tienda": tienda,
        "estado": nuevo_estado,
        "fallos_consecutivos": nuevos_fallos,
        "ultimo_escaneo": ahora_iso,
        "ultimos_productos_count": total_productos,
        "ultimo_error": "0 productos extraídos" if total_productos == 0 else None
    }

    try:
        supabase_client.table("health_checks").upsert(datos_actualizar, on_conflict="tienda").execute()
    except Exception as e:
        safe_log(f"⚠️ No se pudo registrar salud de {tienda} en Supabase: {e}", "caption")

    if nuevos_fallos == 3:
        notificar_desarrollador_caida(tienda, nuevos_fallos, url_origen)

def renderizar_dashboard_salud(supabase_client: Client):
    """Renderiza el tablero de salud tipo semáforo en Streamlit."""
    st.markdown("## 🏥 Panel de Salud de Scrapers (Health Check)")
    st.caption("Monitoreo en tiempo real del estado operativo de los motores de extracción.")
    
    try:
        res = supabase_client.table("health_checks").select("*").order("tienda").execute()
        data = res.data if res.data else []
    except Exception as e:
        st.error(f"Error cargando registros de salud: {e}")
        return
    
    if not data:
        st.info("No hay registros de salud disponibles. Ejecuta un patrullaje primero.")
        return

    total_motores = len(data)
    verdes = sum(1 for d in data if d.get('estado') == 'GREEN')
    amarillos = sum(1 for d in data if d.get('estado') == 'YELLOW')
    rojos = sum(1 for d in data if d.get('estado') == 'RED')
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric("Total Scrapers", total_motores)
    kpi2.metric("🟢 Operativos", verdes)
    kpi3.metric("🟡 Advertencia", amarillos)
    kpi4.metric("🔴 Caídos", rojos)
    
    st.markdown("---")
    
    st.markdown("""
        <style>
        .health-card {
            background-color: #1e222d;
            border-radius: 8px;
            padding: 14px;
            margin-bottom: 10px;
            border-left: 6px solid #ccc;
        }
        .status-green { border-left-color: #2ed573; }
        .status-yellow { border-left-color: #ffa502; }
        .status-red { border-left-color: #ff4757; }
        .badge-green { background: #2ed57322; color: #2ed573; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
        .badge-yellow { background: #ffa50222; color: #ffa502; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
        .badge-red { background: #ff475722; color: #ff4757; padding: 2px 8px; border-radius: 4px; font-weight: bold; }
        </style>
    """, unsafe_allow_html=True)

    for item in data:
        estado = item.get('estado', 'GREEN')
        clase_card = "status-green" if estado == "GREEN" else "status-yellow" if estado == "YELLOW" else "status-red"
        badge_html = f"<span class='badge-{estado.lower()}'>{estado}</span>"
        icon = "🟢" if estado == "GREEN" else "🟡" if estado == "YELLOW" else "🔴"
        
        with st.container():
            col_info, col_action = st.columns([8, 2])
            with col_info:
                st.markdown(
                    f"""
                    <div class="health-card {clase_card}">
                        <h4>{icon} {item.get('tienda')} — Status: {badge_html}</h4>
                        <p style="margin: 0;"><b>Fallos Consecutivos:</b> {item.get('fallos_consecutivos', 0)} | <b>Último Hallazgo:</b> {item.get('ultimos_productos_count', 0)} prods</p>
                        <small style="color: #888;">Último Escaneo: {item.get('ultimo_escaneo')}</small>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
            with col_action:
                if estado == "RED":
                    st.warning("Revisión urgente")

# =======================================================
# 🚀 MOTORES DE EXTRACCIÓN (AISLADOS E INDEPENDIENTES)
# =======================================================

def motor_thn(url, limite):
    productos = []
    url = sanitizar_url(url)
    try:
        headers = {
            "User-Agent": random.choice(LISTA_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-PE,es;q=0.9"
        }
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        if resp.status_code != 200: return []
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        tarjetas = soup.find_all(['div', 'article', 'li'], class_=re.compile(r'(product-summary|product-card|item-card|vtex-product|grid-item)', re.I))
        
        for t in tarjetas:
            try:
                a_el = t.find('a', href=True)
                if not a_el: continue
                link_final = urljoin("https://www.thn.pe", a_el['href'])
                
                tit_el = t.find(['h2', 'h3', 'span', 'div'], class_=re.compile(r'(name|title|brand|description)', re.I))
                nombre = tit_el.text.strip().upper() if tit_el else ""
                if not nombre: nombre = a_el.text.strip().upper()
                if len(nombre) < 4: continue
                
                textos_precios = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', t.text)
                if not textos_precios: continue
                
                nums = sorted(list(set([limpiar_precio_pnp(p) for p in textos_precios if limpiar_precio_pnp(p) > 0])))
                if not nums: continue
                
                p_o = nums[0]
                p_r = nums[-1] if len(nums) > 1 else p_o
                
                if 0 < p_o <= limite:
                    img_tags = t.find_all('img')
                    img = ""
                    for img_el in img_tags:
                        src = img_el.get('data-src') or img_el.get('src') or ""
                        if src and 'data:image' not in str(src).lower() and 'pixel' not in str(src).lower():
                            img = src
                            break
                    if str(img).startswith('//'): img = 'https:' + str(img)
                    
                    productos.append({
                        "nombre": f"THN - {nombre}",
                        "precio": p_o,
                        "precio_regular": max(p_r, p_o),
                        "link": link_final,
                        "img": img
                    })
            except Exception: continue
                
    except Exception as e:
        safe_log(f"Aviso en motor THN: {e}", "caption")
        
    vistos = set()
    productos_unicos = []
    for p in productos:
        if p['link'] not in vistos:
            vistos.add(p['link'])
            productos_unicos.append(p)
            
    return productos_unicos

def motor_belcorp(url, limite, headers):
    productos = []
    url = sanitizar_url(url)
    dominio = urlparse(url).netloc.lower()
    marca = "cyzone" if "cyzone" in dominio else "lbel" if "lbel" in dominio else "esika"
    try:
        resp = requests.get(f"https://{marca}.tiendabelcorp.com.pe/api/catalog_system/pub/products/search", headers=headers, params={"ft": "perfume", "_from": 0, "_to": 20, "O": "OrderByPriceASC"}, timeout=15, verify=False)
        for item in resp.json():
            offer = item["items"][0]["sellers"][0]["commertialOffer"]
            if 0 < float(offer["Price"]) <= limite:
                productos.append({"nombre": f"{marca.upper()} - {item['productName'].upper()}", "precio": float(offer["Price"]), "precio_regular": float(offer.get("ListPrice", offer["Price"])), "link": item["link"], "img": item["items"][0]["images"][0]["imageUrl"]})
    except Exception: pass
    return productos

def motor_conecta_retail(url, limite, headers, tag):
    productos = []
    url = sanitizar_url(url)
    try:
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for t in (soup.select('.product-item') or soup.select('.product-item-info')):
                try:
                    tit_el = t.select_one('a.product-item-link') or t.select_one('.product-item-name a')
                    if not tit_el: continue
                    o_el = t.select_one('[data-price-type="finalPrice"] .price') or t.select_one('.special-price .price') or t.select_one('.price-box .price')
                    r_el = t.select_one('[data-price-type="oldPrice"] .price') or t.select_one('.old-price .price')
                    if not o_el: continue
                    p_o = limpiar_precio_pnp(o_el.text)
                    if 0 < p_o <= limite:
                        img_el = t.select_one('.product-image-photo') or t.find('img')
                        img = img_el.get('data-src') or img_el.get('src') or '' if img_el else ''
                        if img.startswith('//'): img = 'https:' + img
                        productos.append({"nombre": f"{tag} - {tit_el.text.strip().upper()}", "precio": p_o, "precio_regular": limpiar_precio_pnp(r_el.text) if r_el else p_o, "link": urljoin(url, tit_el['href']), "img": img})
                except Exception: continue
    except Exception: pass
    return productos

def motor_falabella(url, limite, headers):
    productos = []
    url = sanitizar_url(url)
    try:
        texto_html = ""
        status_code = 0
        for intento in range(1, 3):
            try:
                resp = requests.get(url, headers=headers, timeout=15, verify=False)
                texto_html = resp.text
                status_code = resp.status_code
            except Exception: pass
            if status_code == 200 and len(texto_html) > 5000: break
            else: time.sleep(random.uniform(1.5, 3.0))
        
        if status_code != 200 or len(texto_html) < 5000: return []
        soup = BeautifulSoup(texto_html, 'html.parser')
        
        fala_prods = []
        scripts_fala = soup.find_all('script')
        for script in scripts_fala:
            if script.text and 'displayName' in script.text and len(script.text) > 1000:
                try:
                    txt = script.text.strip()
                    start_idx = txt.find('{')
                    end_idx = txt.rfind('}')
                    if start_idx != -1 and end_idx != -1:
                        json_data = json.loads(txt[start_idx:end_idx+1])
                        encontrados = extraer_productos_json_universal(json_data)
                        if encontrados:
                            fala_prods = encontrados
                            break
                except Exception: continue

        if fala_prods:
            for prod in fala_prods:
                try:
                    nombre = str(prod.get('displayName') or prod.get('productName') or prod.get('title') or '').strip().upper()
                    if len(nombre) < 3: continue
                    
                    p_o, p_r = 0.0, 0.0
                    precios_list = prod.get('prices') or prod.get('price') or []
                    if isinstance(precios_list, dict): precios_list = [precios_list]
                    
                    if isinstance(precios_list, list):
                        for pr in precios_list:
                            if not isinstance(pr, dict): continue
                            tipo_p = str(pr.get('type', '')).lower()
                            val_p = pr.get('price') or pr.get('value')
                            if isinstance(val_p, list) and len(val_p) > 0: val_p = val_p[0]
                            float_p = safe_float(val_p)
                            if any(x in tipo_p for x in ['sale', 'event', 'oferta', 'internet', 'current', 'card', 'cmr', 'eventprice']): p_o = float_p
                            elif any(x in tipo_p for x in ['list', 'original', 'regular', 'normal', 'normalprice']): p_r = float_p
                        
                        if p_o == 0.0 or p_r <= p_o:
                            valores_aux = []
                            extraer_numeros_dict(prod, valores_aux)
                            valores_unicos = sorted(list(set(valores_aux)))
                            if len(valores_unicos) >= 2:
                                p_o = valores_unicos[0]
                                p_r = valores_unicos[-1]
                            elif len(valores_unicos) == 1:
                                p_o = valores_unicos[0]
                                if p_r == 0.0: p_r = p_o

                    if p_o == 0.0: p_o = safe_float(prod.get('salePrice') or prod.get('price'))
                    if p_r == 0.0: p_r = safe_float(prod.get('listPrice') or prod.get('originalPrice') or prod.get('regularPrice') or p_o)
                    
                    if 0 < p_o <= limite:
                        link_rel = prod.get('url') or prod.get('link') or prod.get('href') or ''
                        link_final = urljoin("https://www.falabella.com.pe", link_rel)
                        img = encontrar_foto_fala(prod)
                        
                        if not img or '/product/' in str(img) or len(str(img)) < 15 or str(img).strip() in ['0', 'None', 'false']:
                            url_limpia = link_final.split('?')[0].split('#')[0]
                            match_id = [t for t in url_limpia.split('/') if t.isdigit() and len(t) >= 7]
                            if match_id: img = f"https://media.falabella.com/falabellaPE/{match_id[-1]}_01/w=800,h=800,fit=pad"
                        
                        if str(img).startswith('//'): img = 'https:' + str(img)
                        img = str(img).split(' ')[0].strip().rstrip(',')
                        productos.append({"nombre": f"FALABELLA - {nombre}", "precio": p_o, "precio_regular": max(p_r, p_o), "link": link_final, "img": str(img)})
                except Exception: continue

        if not productos:
            items = soup.find_all(['div', 'li', 'article'], class_=re.compile(r'(pod|card|product-item|item)', re.I))
            for t in items:
                try:
                    tit_el = t.find(['b', 'span', 'p', 'h3', 'h4', 'a'], id=re.compile(r'name', re.I)) or t.find(['b', 'span', 'p', 'h3', 'h4', 'a'], class_=re.compile(r'(title|name|description|displayName)', re.I))
                    if not tit_el or len(tit_el.text.strip()) < 3: continue
                    
                    el_event = t.find(attrs={"data-event-price": True}) or t.select_one('[data-event-price]')
                    el_normal = t.find(attrs={"data-normal-price": True}) or t.select_one('[data-normal-price]')
                    
                    p_o = 0.0
                    if el_event: p_o = safe_float(el_event.get('data-event-price'))
                    else:
                        o_el = t.find(id=re.compile(r'(salePrice|offerPrice|currentPrice|precio|event)', re.I)) or t.find(class_=re.compile(r'(salePrice|price-value|oferta|current-price|price-item|eventPrice)', re.I))
                        if o_el: p_o = limpiar_precio_pnp(o_el.text)
                        
                    p_r = p_o
                    if el_normal: p_r = safe_float(el_normal.get('data-normal-price'))
                    else:
                        r_el = t.find(id=re.compile(r'(listPrice|regularPrice|oldPrice|normal)', re.I)) or t.find(class_=re.compile(r'(listPrice|regular-price|old-price|normal-price)', re.I))
                        if r_el: p_r = limpiar_precio_pnp(r_el.text)
                    
                    if 0 < p_o <= limite:
                        a_el = t.find('a', href=True) or (t if t.name == 'a' else None)
                        link_final = urljoin(url, a_el['href']) if a_el else url
                        img_el = t.select_one('img[id^="testId-pod-image-"]') or t.find('img', id=re.compile(r'image', re.I)) or t.find('img')
                        img = ''
                        if img_el:
                            for attr in ['data-srcset', 'srcset', 'data-src', 'src', 'data-lazy']:
                                val = img_el.get(attr)
                                if val and 'data:image' not in str(val) and len(str(val)) > 10:
                                    img = str(val).split(' ')[0].strip()
                                    break
                        
                        if not img or '/product/' in str(img) or len(str(img)) < 15 or str(img).strip() in ['0', 'None', 'false']:
                            url_limpia = link_final.split('?')[0].split('#')[0]
                            match_id = [t for t in url_limpia.split('/') if t.isdigit() and len(t) >= 7]
                            if match_id: img = f"https://media.falabella.com/falabellaPE/{match_id[-1]}_01/w=800,h=800,fit=pad"
                        
                        if str(img).startswith('//'): img = 'https:' + str(img)
                        img = str(img).split(' ')[0].strip().rstrip(',')
                        productos.append({"nombre": f"FALABELLA - {tit_el.text.strip().upper()}", "precio": p_o, "precio_regular": max(p_r, p_o), "link": link_final, "img": img})
                except Exception: continue

        vistos = set()
        productos_unicos = []
        for p in productos:
            if p['link'] not in vistos:
                vistos.add(p['link'])
                productos_unicos.append(p)
        return productos_unicos
    except Exception: pass
    return productos

def motor_adidas(url, limite):
    url = sanitizar_url(url)
    def limpiar_precio_adidas(texto):
        if not texto: return 0.0
        texto = str(texto)
        texto = re.sub(r'-?\s*\d+\s*%', '', texto)
        match = re.search(r'\d+(?:[.,]\d+)*', texto)
        if match:
            raw_num = match.group(0)
            if ',' in raw_num and '.' in raw_num:
                raw_num = raw_num.replace(',', '')
            elif ',' in raw_num and len(raw_num.split(',')[-1]) == 2:
                raw_num = raw_num.replace(',', '.')
            else:
                raw_num = raw_num.replace(',', '')
            try: return float(raw_num)
            except ValueError: return 0.0
        return 0.0

    def extraer_url_imagen(nodo):
        if isinstance(nodo, str) and nodo.startswith('http'): return nodo
        elif isinstance(nodo, dict): return nodo.get('src') or nodo.get('url') or nodo.get('desktop') or ''
        elif isinstance(nodo, list) and len(nodo) > 0: return extraer_url_imagen(nodo[0])
        return ''

    FRECUENCIA_MINUTOS = 720  # 12 Horas
    
    try:
        res_check = supabase.table("radares")\
            .select("ultimo_escaneo")\
            .eq("url", url)\
            .limit(1)\
            .execute()

        if res_check.data and len(res_check.data) > 0:
            fecha_str = res_check.data[0].get('ultimo_escaneo')
            if fecha_str:
                ultima_fecha = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone(timedelta(hours=-5)))
                ahora = datetime.now(timezone(timedelta(hours=-5)))
                minutos_transcurridos = (ahora - ultima_fecha).total_seconds() / 60

                if minutos_transcurridos < FRECUENCIA_MINUTOS:
                    safe_log(f"⏳ [Adidas] Esta URL se escaneó hace {int(minutos_transcurridos)} min. Omitiendo para preservar crédito de ScraperAPI.", "caption")
                    return []
    except Exception as e:
        safe_log(f"⚠️ No se pudo verificar el temporizador de Adidas en radares: {e}", "caption")

    productos_map = {}
    texto_html = ""

    lista_keys = []
    try:
        if hasattr(st, "secrets"):
            if "SCRAPERAPI_KEY" in st.secrets: lista_keys.append(st.secrets["SCRAPERAPI_KEY"])
            if "SCRAPERAPI_KEY_2" in st.secrets: lista_keys.append(st.secrets["SCRAPERAPI_KEY_2"])
    except Exception: pass
    
    if "SCRAPERAPI_KEY" in os.environ:
        lista_keys.append(os.environ["SCRAPERAPI_KEY"])

    if not lista_keys:
        lista_keys.append("4cd72a5cadb77297cd9f41f11dc632c0")

    safe_log("🚀 [Adidas] Consultando catálogo vía ScraperAPI...", "info")

    for api_key in lista_keys:
        payload = {'api_key': api_key, 'url': url}
        try:
            resp = requests.get('https://api.scraperapi.com/', params=payload, timeout=40)
            status_code = resp.status_code
            
            if status_code == 200 and len(resp.text) > 5000:
                texto_html = resp.text
                break
            elif status_code == 403:
                safe_log(f"🚨 [Adidas] Error 403 en clave {api_key[:5]}... Probando clave de respaldo.", "warning")
                continue
            else:
                safe_log(f"⚠️ [Adidas] ScraperAPI devolvió código HTTP {status_code}.", "warning")
        except Exception as e:
            safe_log(f"🚨 [Adidas] Error de conexión con ScraperAPI: {e}", "warning")
            continue

    if not texto_html or len(texto_html) <= 5000:
        safe_log("🛑 [Adidas] Imposible obtener respuesta HTML válida de Adidas.", "error")
        return []

    texto_html = texto_html.replace('\xa0', ' ').replace('&nbsp;', ' ')
    soup = BeautifulSoup(texto_html, 'html.parser')

    next_script = soup.find('script', id='__NEXT_DATA__')
    if next_script:
        try:
            json_data = json.loads(next_script.text)

            def buscar_productos_next(nodo):
                if isinstance(nodo, dict):
                    for k in ['products', 'results', 'items', 'itemListElement']:
                        if k in nodo and isinstance(nodo[k], list) and len(nodo[k]) > 0:
                            if isinstance(nodo[k][0], dict) and any(key in nodo[k][0] for key in ['title', 'name', 'displayName']):
                                return nodo[k]
                    for v in nodo.values():
                        res = buscar_productos_next(v)
                        if res: return res
                elif isinstance(nodo, list):
                    for x in nodo:
                        res = buscar_productos_next(x)
                        if res: return res
                return []

            items_json = buscar_productos_next(json_data)
            if items_json:
                for prod_j in items_json:
                    try:
                        nombre = str(prod_j.get('name') or prod_j.get('title') or prod_j.get('displayName') or "").strip().upper()
                        if len(nombre) < 3: continue

                        p_o = limpiar_precio_adidas(prod_j.get('salePrice') or prod_j.get('price'))
                        p_r = limpiar_precio_adidas(prod_j.get('originalPrice') or prod_j.get('price'))
                        if p_r == 0: p_r = p_o

                        if 0 < p_o <= limite:
                            link_rel = prod_j.get('url') or prod_j.get('link') or prod_j.get('href') or ""
                            link_final = urljoin("https://www.adidas.pe", link_rel) if link_rel else url
                            img_url = extraer_url_imagen(prod_j.get('image'))

                            productos_map[link_final] = {
                                "nombre": f"ADIDAS - {nombre}",
                                "precio": p_o,
                                "precio_regular": max(p_r, p_o),
                                "link": link_final,
                                "img": img_url
                            }
                    except Exception: continue
        except Exception: pass

    if not productos_map:
        titulos_testid = soup.find_all(attrs={"data-testid": "product-card-title"})
        for tit_el in titulos_testid:
            try:
                nombre_prod = tit_el.text.strip().upper()
                ancestor = tit_el

                oferta_el, regular_el, enlace_el, img_el = None, None, None, None
                for _ in range(5):
                    ancestor = ancestor.parent
                    if not ancestor: break
                    if not oferta_el: oferta_el = ancestor.find(attrs={"data-testid": "main-price"})
                    if not regular_el: regular_el = ancestor.find(attrs={"data-testid": "original-price"})
                    if not enlace_el: enlace_el = ancestor.find('a', href=True)
                    if not img_el: img_el = ancestor.find('img')

                if oferta_el:
                    precio_oferta = limpiar_precio_adidas(oferta_el.text)
                    precio_regular = limpiar_precio_adidas(regular_el.text) if regular_el else precio_oferta

                    if 0 < precio_oferta <= limite:
                        link_final = urljoin("https://www.adidas.pe", enlace_el['href']) if enlace_el else url
                        img_url = img_el.get('src', '') if img_el else ''

                        productos_map[link_final] = {
                            "nombre": f"ADIDAS - {nombre_prod}",
                            "precio": precio_oferta,
                            "precio_regular": max(precio_regular, precio_oferta),
                            "link": link_final,
                            "img": img_url
                        }
            except Exception: continue

    productos_list = list(productos_map.values())
    if productos_list:
        safe_log(f"✅ [Adidas] ¡Éxito! Se procesaron {len(productos_list)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [Adidas] No hay ofertas por debajo del presupuesto S/. {limite:.2f}", "warning")

    return productos_list

def motor_platanitos(url, limite):
    productos = []
    url = sanitizar_url(url)
    try:
        texto_html = ""
        try:
            headers = {"User-Agent": random.choice(LISTA_USER_AGENTS), "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8", "Accept-Language": "es-ES,es;q=0.9"}
            resp = requests.get(url, headers=headers, timeout=15, verify=False)
            texto_html = resp.text
        except Exception: pass

        if not texto_html or len(texto_html) < 2000: return []
        soup = BeautifulSoup(texto_html, 'html.parser')
        tarjetas = soup.find_all(['div', 'article', 'a'], class_=re.compile(r'(product|card|item|col|grid)', re.I))
                    
        for t in tarjetas:
            try:
                a_el = t.find('a', href=re.compile(r'/producto/', re.I)) or (t if t.name == 'a' and '/producto/' in t.get('href', '').lower() else None)
                if not a_el: continue
                link_final = urljoin("https://platanitos.com", a_el['href'])
                tit_el = t.find(['h3', 'h2', 'span', 'p', 'div'], class_=re.compile(r'(title|name|nombre|description)', re.I))
                nombre = tit_el.text.strip() if tit_el else ""
                if not nombre and a_el.has_attr('title'): nombre = a_el['title'].strip()
                if len(nombre) < 3 or "PLATANITOS" in nombre.upper(): continue
                
                textos_precios = []
                for el in t.find_all(['span', 'p', 'b', 'strong', 'del', 'small']):
                    if el.find(['span', 'p', 'b', 'strong', 'del', 'small']): continue
                    txt_el = el.text.strip() if el.text else ""
                    if 'S/' in txt_el and '%' not in txt_el and len(txt_el) < 20:
                        textos_precios.extend(re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', txt_el))
                        
                if not textos_precios: continue
                nums = sorted(list(set([limpiar_precio_pnp(p) for p in textos_precios if limpiar_precio_pnp(p) > 0])))
                if not nums: continue
                p_o = nums[0]
                p_r = nums[-1] if len(nums) > 1 else p_o
                
                if 0 < p_o <= limite:
                    img = ""
                    img_tags = t.find_all('img')
                    for img_el in img_tags:
                        src_candidato = img_el.get('data-src') or img_el.get('src') or img_el.get('data-lazy') or ""
                        if src_candidato and 'data:image' not in str(src_candidato).lower():
                            img = src_candidato
                            break
                    if str(img).startswith('//'): img = 'https:' + str(img)
                    productos.append({"nombre": f"PLATANITOS - {nombre.upper()}", "precio": p_o, "precio_regular": p_r, "link": link_final, "img": img})
            except Exception: continue
    except Exception: pass
    return productos

def motor_hiraoka(url, limite):
    productos = []
    url = sanitizar_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9"
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        if resp.status_code != 200: return []
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        tarjetas = soup.select('.product-item') or soup.select('.product-item-info') or soup.select('.item.product')
        
        for t in tarjetas:
            try:
                tit_el = t.select_one('.product-item-link') or t.select_one('.product-item-name a') or t.select_one('.product-name a')
                if not tit_el: continue
                nombre = tit_el.text.strip().upper()
                link_final = urljoin("https://hiraoka.com.pe", tit_el['href'])
                
                o_el = t.select_one('[data-price-type="finalPrice"] .price') or t.select_one('.special-price .price') or t.select_one('.price-box .price')
                r_el = t.select_one('[data-price-type="oldPrice"] .price') or t.select_one('.old-price .price')
                
                if not o_el:
                    textos_precios = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', t.text)
                    if textos_precios:
                        nums = sorted(list(set([limpiar_precio_pnp(p) for p in textos_precios if limpiar_precio_pnp(p) > 0])))
                        p_o = nums[0] if nums else 0.0
                        p_r = nums[-1] if len(nums) > 1 else p_o
                    else:
                        continue
                else:
                    p_o = limpiar_precio_pnp(o_el.text)
                    p_r = limpiar_precio_pnp(r_el.text) if r_el else p_o
                
                if 0 < p_o <= limite:
                    img_el = t.select_one('.product-image-photo') or t.find('img')
                    img_url = ""
                    if img_el:
                        img_url = img_el.get('data-src') or img_el.get('src') or ""
                    if img_url.startswith('//'): img_url = 'https:' + img_url
                    
                    productos.append({
                        "nombre": f"HIRAOKA - {nombre}",
                        "precio": p_o,
                        "precio_regular": max(p_r, p_o),
                        "link": link_final,
                        "img": img_url
                    })
            except Exception: continue
                
    except Exception as e:
        print(f"Error en motor Hiraoka: {e}")
        
    return productos

def motor_carsa(url, limite):
    """Motor CARSA optimizado con extracción de URL de imágenes."""
    productos = []
    url = sanitizar_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Referer": "https://www.google.com/",
        "Connection": "keep-alive"
    }
    
    try:
        safe_log(f"🚀 [Diag CARSA] Lanzando motor de alta fidelidad a: {url}", "info")
        session = requests.Session()
        resp = session.get(url, headers=headers, timeout=20, allow_redirects=True, verify=False)
        
        safe_log(f"📡 [Diag CARSA] Código de respuesta: {resp.status_code} | Tamaño: {len(resp.text)}", "info")
        
        if resp.status_code != 200:
            safe_log(f"🛑 [Diag CARSA] Bloqueo total por Firewall/Anti-Bot. Código {resp.status_code}", "error")
            return []

        matches = re.findall(
            r'"productName":"([^"]+)".*?"Price":(\d+\.?\d*).*?(?:'
            r'"imageUrl":"([^"]+)"|"image":"([^"]+)"|)', 
            resp.text
        )
        
        if not matches:
            safe_log("🛑 [Diag CARSA] Descarga exitosa, pero no encontramos productos con el buscador de texto.", "error")
        else:
            for match in matches:
                nombre = match[0]
                p = float(match[1])
                img_url = match[2] or match[3] if len(match) > 2 else ""
                
                if img_url and img_url.startswith('//'):
                    img_url = 'https:' + img_url

                if 0 < p <= limite:
                    productos.append({
                        "nombre": f"CARSA - {nombre}",
                        "precio": p,
                        "precio_regular": p,
                        "link": url,
                        "img": img_url
                    })
            safe_log(f"✅ [Diag CARSA] Se encontraron {len(matches)} productos. {len(productos)} cumplen el límite.", "success")
            
    except Exception as e:
        safe_log(f"🛑 [Diag CARSA] Error crítico: {str(e)}", "error")
        
    return productos

def motor_oechsle(url, limite):
    productos = []
    url = sanitizar_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    try:
        safe_log("📡 [Oechsle] Analizando estructura del radar...", "info")
        
        parsed_url = urlparse(url)
        raw_query = parsed_url.query
        
        if 'query=' in raw_query:
            raw_query = raw_query.replace('query=', 'ft=')
        
        has_category_filter = 'fq=C:' in raw_query or 'fq=C%3A' in raw_query
        base_api = "https://www.oechsle.pe/api/catalog_system/pub/products/search"
        
        if has_category_filter:
            api_url = f"{base_api}?{raw_query}"
        else:
            category_path = parsed_url.path.rstrip('/')
            if category_path and not category_path.startswith('/'):
                category_path = '/' + category_path
            api_url = f"{base_api}{category_path}?{raw_query}"
            
        if '_from=' not in api_url:
            api_url += "&_from=0&_to=49"
            
        api_url = sanitizar_url(api_url)
        
        safe_log(f"📡 [Oechsle] Conectando con la base de datos oficial...", "info")
        resp = requests.get(api_url, headers=headers, timeout=15, verify=False)
        
        if resp.status_code in [200, 206]:
            data = resp.json()
            safe_log(f"🔍 [Oechsle] Base de datos leída con éxito. Se procesaron {len(data)} productos.", "info")
            
            for item in data:
                try:
                    nombre = item.get('productName', '').upper()
                    link_final = item.get('link', url)
                    
                    items_list = item.get('items', [])
                    if not items_list: continue
                    first_item = items_list[0]
                    
                    sellers = first_item.get('sellers', [])
                    if not sellers: continue
                    offer = sellers[0].get('commertialOffer', {})
                    
                    p_o = float(offer.get('Price', 0.0))
                    p_r = float(offer.get('ListPrice', p_o))
                    
                    images = first_item.get('images', [])
                    img_url = images[0].get('imageUrl', '') if images else ""
                    if img_url.startswith('//'): img_url = 'https:' + img_url
                    
                    if 0 < p_o <= limite:
                        productos.append({
                            "nombre": f"OECHSLE - {nombre}",
                            "precio": p_o,
                            "precio_regular": max(p_r, p_o),
                            "link": link_final,
                            "img": img_url
                        })
                except Exception: continue
        else:
            safe_log(f"⚠️ [Oechsle API] Código {resp.status_code} recibido. Activando contingencia de rescate...", "warning")
            
    except Exception as e:
        safe_log(f"⚠️ [Oechsle API] Error durante la consulta directa: {e}. Activando contingencia...", "warning")
        
    if not productos:
        safe_log("🛡️ [Oechsle] Activando plan de contingencia HTML...", "info")
        try:
            html_headers = headers.copy()
            html_headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
            
            clean_html_url = sanitizar_url(url)
            resp = requests.get(clean_html_url, headers=html_headers, timeout=15, verify=False)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                json_ld_prods = []
                scripts = soup.find_all('script', type='application/ld+json')
                for script in scripts:
                    try:
                        if not script.string: continue
                        data = json.loads(script.string)
                        if isinstance(data, dict) and data.get('@type') == 'ItemList':
                            items = data.get('itemListElement', [])
                            for item in items:
                                prod = item.get('item', {})
                                if isinstance(prod, dict) and prod.get('@type') == 'Product':
                                    json_ld_prods.append(prod)
                        elif isinstance(data, dict) and data.get('@type') == 'Product':
                            json_ld_prods.append(data)
                    except Exception: continue
                        
                if json_ld_prods:
                    vistos_links = set()
                    for prod in json_ld_prods:
                        try:
                            nombre = prod.get('name', '').upper()
                            link_final = prod.get('url', '')
                            if not link_final: continue
                            link_final = urljoin("https://www.oechsle.pe", link_final)
                            
                            if link_final in vistos_links: continue
                            
                            offers = prod.get('offers', {})
                            p_o = 0.0
                            if isinstance(offers, dict):
                                p_o = float(offers.get('price', 0.0))
                            elif isinstance(offers, list) and offers:
                                p_o = float(offers[0].get('price', 0.0))
                                
                            img_url = prod.get('image', '')
                            if isinstance(img_url, list) and img_url:
                                img_url = img_url[0]
                                
                            if 0 < p_o <= limite:
                                vistos_links.add(link_final)
                                productos.append({
                                    "nombre": f"OECHSLE - {nombre}",
                                    "precio": p_o,
                                    "precio_regular": p_o,
                                    "link": link_final,
                                    "img": img_url
                                })
                        except Exception: continue
        except Exception as he:
            safe_log(f"🛑 [Oechsle HTML] Error en contingencia: {he}", "error")
            
    if productos:
        safe_log(f"✅ [Oechsle] ¡Éxito! Se encontraron {len(productos)} ofertas que cumplen el presupuesto.", "success")
    else:
        safe_log(f"⚠️ [Oechsle] Búsqueda finalizada, pero ningún equipo baja de S/. {limite:.2f}", "warning")
        
    return productos

def motor_plazavea(url, limite, headers=None):
    productos = []
    url = sanitizar_url(url)
    if not headers:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.plazavea.com.pe/"
        }

    try:
        parsed_url = urlparse(url)
        category_path = parsed_url.path.rstrip('/')
        if category_path and not category_path.startswith('/'):
            category_path = '/' + category_path

        if "busca" in category_path:
            api_url = "https://www.plazavea.com.pe/api/catalog_system/pub/products/search"
        else:
            api_url = f"https://www.plazavea.com.pe/api/catalog_system/pub/products/search{category_path}"

        query_params = parse_qs(parsed_url.query)
        params = {
            "O": "OrderByPriceASC",
            "_from": "0",
            "_to": "49"
        }
        
        for k, v in query_params.items():
            params[k] = v if len(v) > 1 else v[0]

        api_url = sanitizar_url(api_url)
        safe_log(f"📡 [Plaza Vea API] Consultando VTEX con filtros avanzados...", "info")
        resp = requests.get(api_url, headers=headers, params=params, timeout=15, verify=False)

        if resp.status_code in [200, 206]:
            data = resp.json()
            safe_log(f"🔍 [Plaza Vea API] Catálogo recibido. Procesando {len(data)} productos...", "info")
            vistos_links = set()

            for p in data:
                try:
                    nombre_prod = p.get("productName", "").strip().upper()
                    link_final = p.get("link", "")
                    
                    items = p.get("items", [])
                    if not items: continue
                    
                    first_item = items[0]
                    images = first_item.get("images", [])
                    img_final = images[0].get("imageUrl", "") if images else ""
                    
                    sellers = first_item.get("sellers", [])
                    if not sellers: continue
                        
                    offer = sellers[0].get("commertialOffer", {})
                    stock = offer.get("AvailableQuantity", 0)
                    if stock <= 0: continue  
                        
                    precio_oferta = float(offer.get("Price", 0))
                    precio_regular = float(offer.get("ListPrice", precio_oferta))
                    
                    if precio_oferta <= 0: continue

                    if precio_oferta <= limite:
                        if link_final in vistos_links: continue
                        vistos_links.add(link_final)

                        productos.append({
                            "nombre": f"Plaza Vea - {nombre_prod}",
                            "precio": precio_oferta,
                            "precio_regular": precio_regular,
                            "link": link_final,
                            "img": img_final
                        })
                except Exception: continue
        else:
            safe_log(f"🛑 [Plaza Vea API] Error de conexión con VTEX. Código HTTP: {resp.status_code}", "error")

    except Exception as e:
        safe_log(f"🛑 [Plaza Vea API] Error crítico inesperado: {e}", "error")

    if productos:
        safe_log(f"✅ [Plaza Vea API] ¡Éxito! Se indexaron {len(productos)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [Plaza Vea API] No se encontraron productos bajo el límite de S/. {limite:.2f}", "warning")

    return productos

def motor_juntoz(url, limite, headers=None):
    productos_map = {}
    url = sanitizar_url(url)
    if not headers:
        headers = {
            "User-Agent": random.choice(LISTA_USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
            "Referer": "https://www.juntoz.com/"
        }

    try:
        safe_log(f"📡 [Juntoz] Descargando catálogo por HTML...", "info")
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        
        if resp.status_code != 200:
            safe_log(f"🛑 [Juntoz] Error de servidor. Código: {resp.status_code}", "error")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        enlaces_productos = []
        for a in soup.find_all('a', href=True):
            href = a['href'].lower()
            if ('/p/' in href or '/producto/' in href) and not any(x in href for x in ['/politica', '/ayuda', '/terminos', '/catalogo', '/tienda']):
                enlaces_productos.append(a)

        for a_el in enlaces_productos:
            try:
                href_rel = a_el['href']
                link_final = urljoin("https://juntoz.com", href_rel)
                
                contenedor_tarjeta = None
                ancestro_actual = a_el.parent
                
                for _ in range(6):
                    if not ancestro_actual or ancestro_actual.name in ['body', 'html']: break
                    texto_ancestro = ancestro_actual.get_text()
                    if 'S/.' in texto_ancestro or 'S/' in texto_ancestro:
                        contenedor_tarjeta = ancestro_actual
                        break
                    ancestro_actual = ancestro_actual.parent

                if not contenedor_tarjeta: continue

                nombre = a_el.get_text(separator=" ").strip().upper()
                if not nombre or len(nombre) < 5:
                    for otro_a in contenedor_tarjeta.find_all('a', href=True):
                        if otro_a['href'] == href_rel:
                            nombre_otro = otro_a.get_text(separator=" ").strip().upper()
                            if nombre_otro and len(nombre_otro) >= 5:
                                nombre = nombre_otro
                                break

                if not nombre or len(nombre) < 5:
                    img_el = contenedor_tarjeta.find('img')
                    if img_el and img_el.get('alt'):
                        nombre = img_el['alt'].strip().upper()

                if not nombre or len(nombre) < 5: continue
                nombre = nombre.replace("AGREGAR A CARRITO", "").replace("AGREGAR", "").strip()
                nombre = re.sub(r'\s+', ' ', nombre)

                texto_tarjeta = contenedor_tarjeta.get_text()
                textos_precios = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', texto_tarjeta)
                if not textos_precios: continue

                precios_numeros = [limpiar_precio_pnp(p) for p in textos_precios if limpiar_precio_pnp(p) > 0]
                if not precios_numeros: continue

                precios_unicos = sorted(list(set(precios_numeros)))
                p_o = precios_unicos[0]
                p_r = precios_unicos[-1] if len(precios_unicos) > 1 else p_o

                img_el = contenedor_tarjeta.find('img')
                img_url = ""
                if img_el:
                    img_url = img_el.get('data-src') or img_el.get('src') or img_el.get('data-lazy') or img_el.get('data-original') or ""
                
                if img_url.startswith('//'): img_url = 'https:' + img_url
                elif img_url and not img_url.startswith('http'): img_url = urljoin("https://juntoz.com", img_url)

                if 'data:image' in img_url.lower() or 'pixel' in img_url.lower(): img_url = ""

                if 0 < p_o <= limite:
                    if link_final in productos_map:
                        prod_existente = productos_map[link_final]
                        if len(nombre) > len(prod_existente['nombre']) or (img_url and not prod_existente['img']):
                            productos_map[link_final] = {
                                "nombre": f"Juntoz - {nombre}",
                                "precio": p_o,
                                "precio_regular": max(p_r, p_o),
                                "link": link_final,
                                "img": img_url or prod_existente['img']
                            }
                    else:
                        productos_map[link_final] = {
                            "nombre": f"Juntoz - {nombre}",
                            "precio": p_o,
                            "precio_regular": max(p_r, p_o),
                            "link": link_final,
                            "img": img_url
                        }
            except Exception: continue

    except Exception as e:
        safe_log(f"🛑 [Juntoz] Error crítico inesperado: {e}", "error")

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [Juntoz] ¡Éxito! Se indexaron {len(productos_finales)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [Juntoz] No se encontraron productos bajo el límite de S/. {limite:.2f}", "warning")

    return productos_finales

def motor_triathlon(url, limite, headers=None):
    productos_map = {}
    vistos_links = set()
    url = sanitizar_url(url)
    
    if not headers:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9;image/webp,*/*;q=0.8",
            "Accept-Language": "es-PE,es;q=0.9",
            "Referer": "https://www.triathlon.com.pe/"
        }

    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)

        for page_num in range(1, 4):
            query_params['page'] = [str(page_num)]
            new_query = urlencode(query_params, doseq=True)
            page_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, new_query, parsed_url.fragment))

            resp = requests.get(page_url, headers=headers, timeout=15, verify=False)
            if resp.status_code != 200: break

            soup = BeautifulSoup(resp.text, 'html.parser')
            tarjetas = soup.select('[class*="product-summary-"]') or soup.select('[class*="vtex-product-summary-"]') or soup.select('[class*="summaryContainer"]')

            if not tarjetas: break
                
            for t in tarjetas:
                try:
                    link_final = ""
                    for a in t.find_all('a', href=True):
                        href = a['href'].lower()
                        if '/p' in href and not any(x in href for x in ['/account', '/checkout', '/cart', '/busca', '/login']):
                            link_final = urljoin("https://www.triathlon.com.pe", a['href'])
                            break
                    
                    if not link_final: continue

                    nombre_el = t.select_one('[class*="productName"]') or t.select_one('[class*="brandName"]') or t.select_one('[class*="productBrand"]')
                    raw_nombre = nombre_el.text.strip() if nombre_el else ""
                    
                    if not raw_nombre or len(raw_nombre) < 5 or raw_nombre.upper() in ['ADIDAS', 'PUMA', 'NIKE', 'UNDER ARMOUR']:
                        textos_internos = [a.get_text().strip() for a in t.find_all('a') if len(a.get_text().strip()) > 5]
                        raw_nombre = max(textos_internos, key=len) if textos_internos else "ZAPATILLA SPORT"

                    nombre_limpio = re.sub(r'-\d+%', '', raw_nombre)
                    nombre_limpio = re.sub(r'(?:S/\.?\s*)(\d[\d\.,]*)', '', nombre_limpio)
                    nombre_limpio = nombre_limpio.replace("Antes:", "").replace("Ahora:", "").strip().upper()
                    nombre_limpio = re.sub(r'\s+', ' ', nombre_limpio)

                    if len(nombre_limpio) < 4: continue

                    texto_tarjeta = t.get_text()
                    textos_precios = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', texto_tarjeta)
                    if not textos_precios: continue
                        
                    precios_num = sorted(list(set([limpiar_precio_pnp(p) for p in textos_precios if limpiar_precio_pnp(p) > 0])))
                    if not precios_num: continue
                        
                    p_o = precios_num[0]
                    p_r = precios_num[-1] if len(precios_num) > 1 else p_o

                    img_el = t.find('img')
                    img_url = ""
                    if img_el:
                        srcset = img_el.get('srcset') or img_el.get('data-srcset')
                        if srcset:
                            urls_set = re.findall(r'(https?://\S+)', srcset)
                            if urls_set: img_url = urls_set[0].split('?')[0]
                        if not img_url: img_url = img_el.get('data-src') or img_el.get('src') or ""

                    if img_url.startswith('//'): img_url = 'https:' + img_url
                    if 'data:image' in img_url.lower() or 'pixel' in img_url.lower(): img_url = ""

                    if 0 < p_o <= limite:
                        if link_final in vistos_links: continue
                        vistos_links.add(link_final)
                        
                        productos_map[link_final] = {
                            "nombre": f"Triathlon - {nombre_limpio}",
                            "precio": p_o,
                            "precio_regular": max(p_r, p_o),
                            "link": link_final,
                            "img": img_url
                        }
                except Exception: continue
            time.sleep(0.5)

    except Exception as e:
        safe_log(f"🛑 [Triathlon] Error crítico en paginación: {e}", "error")

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [Triathlon] ¡Éxito! Se consolidaron {len(productos_finales)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [Triathlon] No se encontraron ofertas bajo el límite de S/. {limite:.2f}", "warning")

    return productos_finales

def motor_ripley(url, limite, headers=None):
    safe_log("⏸️ [Ripley] Motor pausado temporalmente.", "caption")
    return []

def motor_footloose(url, limite):
    productos_map = {}
    url = sanitizar_url(url)
    headers = {
        "User-Agent": random.choice(LISTA_USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9",
        "Referer": "https://www.footloose.pe/"
    }

    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        
        raw_path = parsed_url.path.rstrip('/')
        if 'query' in query_params:
            q_val = query_params['query'][0]
            if q_val.startswith('/'):
                raw_path = q_val.rstrip('/')

        segmentos = [s for s in raw_path.split('/') if s and not re.match(r'^\d+[\-_.]\d+$', s)]
        path_limpio = '/' + '/'.join(segmentos) if segmentos else "/calzados"
        path_base = '/' + '/'.join(segmentos[:2]) if len(segmentos) >= 2 else path_limpio

        urls_a_probar = []

        if "map" in query_params:
            maps = query_params["map"][0].split(',')
            maps_validos = [m for m in maps if m in ['c', 'category-1', 'category-2', 'category-3', 'brand', 'b']]
            if maps_validos and len(maps_validos) == len(segmentos):
                urls_a_probar.append((f"https://www.footloose.pe/api/catalog_system/pub/products/search{path_limpio}", {"O": "OrderByPriceASC", "_from": "0", "_to": "49", "map": ",".join(maps_validos)}))

        urls_a_probar.append((f"https://www.footloose.pe/api/catalog_system/pub/products/search{path_limpio}", {"O": "OrderByPriceASC", "_from": "0", "_to": "49"}))
        
        if path_base != path_limpio:
            urls_a_probar.append((f"https://www.footloose.pe/api/catalog_system/pub/products/search{path_base}", {"O": "OrderByPriceASC", "_from": "0", "_to": "49"}))

        safe_log(f"📡 [Footloose API] Iniciando escaneo multinivel sobre `{path_limpio}`...", "info")

        for api_endpoint, params in urls_a_probar:
            try:
                api_endpoint = sanitizar_url(api_endpoint)
                resp = requests.get(api_endpoint, headers=headers, params=params, timeout=12, verify=False)
                if resp.status_code in [200, 206]:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        safe_log(f"🔍 [Footloose API] ¡Respuesta recibida! {len(data)} ítems evaluados.", "info")
                        for p in data:
                            try:
                                nombre_prod = p.get("productName", "").strip().upper()
                                link_rel = p.get("link", "")
                                link_final = urljoin("https://www.footloose.pe", link_rel) if link_rel else url
                                
                                items = p.get("items", [])
                                if not items: continue
                                
                                first_item = items[0]
                                images = first_item.get("images", [])
                                img_final = images[0].get("imageUrl", "") if images else ""
                                if img_final.startswith('//'): img_final = 'https:' + img_final
                                
                                sellers = first_item.get("sellers", [])
                                if not sellers: continue
                                    
                                offer = sellers[0].get("commertialOffer", {})
                                p_o = float(offer.get("Price", 0.0))
                                p_r = float(offer.get("ListPrice", p_o))
                                
                                if 0 < p_o <= limite:
                                    productos_map[link_final] = {
                                        "nombre": f"FOOTLOOSE - {nombre_prod}",
                                        "precio": p_o,
                                        "precio_regular": max(p_r, p_o),
                                        "link": link_final,
                                        "img": img_final
                                    }
                            except Exception: continue
                        
                        if len(productos_map) > 0: break
            except Exception: continue

    except Exception as e:
        safe_log(f"🛑 [Footloose API] Error de ejecución: {e}", "error")

    productos_list = list(productos_map.values())
    if productos_list:
        safe_log(f"✅ [Footloose] ¡Éxito! Se indexaron {len(productos_list)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [Footloose] No se encontraron ofertas por debajo de S/. {limite:.2f}", "warning")

    return productos_list

def motor_estilos(url, limite):
    productos_map = {}
    url = sanitizar_url(url)
    headers = {
        "User-Agent": random.choice(LISTA_USER_AGENTS),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-PE,es;q=0.9",
        "Referer": "https://www.estilos.com.pe/"
    }

    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        raw_path = unquote(parsed_url.path.rstrip('/'))
        
        segmentos = [s for s in raw_path.split('/') if s and not re.match(r'^\d+[\-_.]\d+$', s)]
        path_limpio = '/' + '/'.join(segmentos) if segmentos else "/poleras-hombre"
        path_base = '/' + '/'.join(segmentos[-2:]) if len(segmentos) >= 2 else path_limpio

        urls_a_probar = []

        q_term = query_params.get('_q', query_params.get('ft', [None]))[0]
        if q_term:
            urls_a_probar.append((
                "https://www.estilos.com.pe/api/catalog_system/pub/products/search",
                {"ft": q_term, "O": "OrderByPriceASC", "_from": "0", "_to": "49"}
            ))

        urls_a_probar.append((
            f"https://www.estilos.com.pe/api/catalog_system/pub/products/search{path_limpio}",
            {"O": "OrderByPriceASC", "_from": "0", "_to": "49"}
        ))
        
        if path_base != path_limpio:
            urls_a_probar.append((
                f"https://www.estilos.com.pe/api/catalog_system/pub/products/search{path_base}",
                {"O": "OrderByPriceASC", "_from": "0", "_to": "49"}
            ))

        safe_log(f"📡 [Estilos API] Consultando catálogo VTEX de Estilos...", "info")

        for api_endpoint, params in urls_a_probar:
            try:
                api_endpoint = sanitizar_url(api_endpoint)
                resp = requests.get(api_endpoint, headers=headers, params=params, timeout=12, verify=False)
                if resp.status_code in [200, 206]:
                    data = resp.json()
                    if isinstance(data, list) and len(data) > 0:
                        safe_log(f"🔍 [Estilos API] ¡Éxito! Se procesaron {len(data)} modelos desde VTEX.", "info")
                        for p in data:
                            try:
                                nombre_prod = p.get("productName", "").strip().upper()
                                link_rel = p.get("link", "")
                                link_final = urljoin("https://www.estilos.com.pe", link_rel) if link_rel else url
                                
                                items = p.get("items", [])
                                if not items: continue
                                
                                first_item = items[0]
                                images = first_item.get("images", [])
                                img_final = images[0].get("imageUrl", "") if images else ""
                                if img_final.startswith('//'): img_final = 'https:' + img_final
                                
                                sellers = first_item.get("sellers", [])
                                if not sellers: continue
                                    
                                offer = sellers[0].get("commertialOffer", {})
                                p_o = float(offer.get("Price", 0.0))
                                p_r = float(offer.get("ListPrice", p_o))
                                
                                if 0 < p_o <= limite:
                                    productos_map[link_final] = {
                                        "nombre": f"ESTILOS - {nombre_prod}",
                                        "precio": p_o,
                                        "precio_regular": max(p_r, p_o),
                                        "link": link_final,
                                        "img": img_final
                                    }
                            except Exception: continue
                        
                        if len(productos_map) > 0: break
            except Exception: continue

    except Exception as e:
        safe_log(f"⚠️ [Estilos API] Error de consulta: {e}", "warning")

    if not productos_map:
        try:
            safe_log("🛡️ [Estilos HTML] Escaneando estructura de respaldo...", "info")
            html_headers = headers.copy()
            html_headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
            resp = requests.get(url, headers=html_headers, timeout=15, verify=False)
            
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                for script in soup.find_all('script', type='application/ld+json'):
                    try:
                        if not script.string: continue
                        json_data = json.loads(script.string)
                        items = []
                        if isinstance(json_data, dict) and json_data.get('@type') == 'ItemList':
                            items = [x.get('item', {}) for x in json_data.get('itemListElement', [])]
                        elif isinstance(json_data, list):
                            items = json_data
                            
                        for item in items:
                            if not isinstance(item, dict): continue
                            nombre = str(item.get('name', '')).strip().upper()
                            link_f = urljoin("https://www.estilos.com.pe", item.get('url', ''))
                            offers = item.get('offers', {})
                            p_o = 0.0
                            if isinstance(offers, dict): p_o = float(offers.get('price', 0.0))
                            elif isinstance(offers, list) and offers: p_o = float(offers[0].get('price', 0.0))
                            img_f = item.get('image', '')
                            if isinstance(img_f, list) and img_f: img_f = img_f[0]
                            if str(img_f).startswith('//'): img_f = 'https:' + str(img_f)
                            
                            if 0 < p_o <= limite and nombre and link_f:
                                productos_map[link_f] = {
                                    "nombre": f"ESTILOS - {nombre}",
                                    "precio": p_o,
                                    "precio_regular": p_o,
                                    "link": link_f,
                                    "img": img_f
                                }
                    except Exception: continue
        except Exception as he:
            safe_log(f"🛑 [Estilos HTML] Error en contingencia HTML: {he}", "error")

    productos_list = list(productos_map.values())
    if productos_list:
        safe_log(f"✅ [Estilos] ¡Éxito! Se indexaron {len(productos_list)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [Estilos] No se encontraron ofertas por debajo de S/. {limite:.2f}", "warning")

    return productos_list

def motor_promart(url, limite, headers=None):
    productos_map = {}
    url = sanitizar_url(url)
    if not headers:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.promart.pe/"
        }

    try:
        parsed_url = urlparse(url)
        path = parsed_url.path.rstrip('/')
        api_base_url = f"https://www.promart.pe/api/catalog_system/pub/products/search{path}"

        query_parts = []
        if parsed_url.query:
            for pair in parsed_url.query.split('&'):
                if pair.startswith('fq=C:') or pair.startswith('fq=C%3A'): continue
                if pair.startswith('_from=') or pair.startswith('_to='): continue
                query_parts.append(pair)
        
        if not any(p.startswith('O=') for p in query_parts):
            query_parts.append("O=OrderByPriceASC")
        query_parts.append("_from=0")
        query_parts.append("_to=49")

        final_query_string = "&".join(query_parts)
        final_api_url = sanitizar_url(f"{api_base_url}?{final_query_string}")

        safe_log("📡 [Promart API] Consultando catálogo VTEX...", "info")
        resp = requests.get(final_api_url, headers=headers, timeout=15, verify=False)

        if resp.status_code in [200, 206]:
            data = resp.json()
            safe_log(f"🔍 [Promart API] Catálogo recibido ({len(data)} ítems). Procesando...", "info")

            url_decodificada = unquote(url).lower()
            exigir_50_59_tv = "50-59" in url_decodificada and ("televisor" in path or "tv" in path)

            for p in data:
                try:
                    nombre_prod = p.get("productName", "").strip().upper()
                    
                    if exigir_50_59_tv:
                        match_pulgadas = re.search(r'(\d{2})\s*(?:"|”|’|PULGADAS|PULGADA|P\b)', nombre_prod)
                        if match_pulgadas:
                            pulgadas = int(match_pulgadas.group(1))
                            if not (50 <= pulgadas <= 59): continue
                        elif not any(k in nombre_prod for k in ["50-59", "50", "55", "58"]): continue

                    link_rel = p.get("link", "")
                    link_final = urljoin("https://www.promart.pe", link_rel) if link_rel else url

                    items = p.get("items", [])
                    if not items: continue

                    first_item = items[0]
                    images = first_item.get("images", [])
                    img_final = images[0].get("imageUrl", "") if images else ""
                    if img_final.startswith('//'): img_final = 'https:' + img_final

                    sellers = first_item.get("sellers", [])
                    if not sellers: continue

                    offer = sellers[0].get("commertialOffer", {})
                    if offer.get("AvailableQuantity", 0) <= 0: continue

                    p_o = float(offer.get("Price", 0.0))
                    p_r = float(offer.get("ListPrice", p_o))
                    
                    p_tarjeta = None
                    installment_options = offer.get("PaymentOptions", {}).get("installmentOptions", [])
                    
                    for option in installment_options:
                        p_name = f"{option.get('paymentSystemName', '')} {option.get('paymentName', '')}".lower()
                        if "oh" in p_name:
                            installments = option.get("installments", [])
                            if installments:
                                total_val = float(installments[0].get("total", 0))
                                val = total_val / 100.0 if total_val > 10000 else float(installments[0].get("value", 0))
                                if 0 < val < p_o:
                                    p_tarjeta = val
                                    break

                    precio_minimo = p_tarjeta if p_tarjeta else p_o

                    if 0 < precio_minimo <= limite:
                        productos_map[link_final] = {
                            "nombre": f"PROMART - {nombre_prod}",
                            "precio": p_o,
                            "precio_tarjeta": p_tarjeta,
                            "precio_regular": max(p_r, p_o),
                            "link": link_final,
                            "img": img_final
                        }
                except Exception: continue
        else:
            safe_log(f"🛑 [Promart API] Código HTTP: {resp.status_code}", "error")

    except Exception as e:
        safe_log(f"🛑 [Promart API] Error crítico: {e}", "error")

    productos_list = list(productos_map.values())
    if productos_list:
        safe_log(f"✅ [Promart] ¡Éxito! Se indexaron {len(productos_list)} ofertas válidas.", "success")
    else:
        safe_log(f"⚠️ [Promart] No hay productos que cumplan el filtro por debajo de S/. {limite:.2f}", "warning")

    return productos_list

def motor_coolbox(url, limite, headers=None):
    productos_map = {}
    url = sanitizar_url(url)
    if not headers:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Referer": "https://www.coolbox.pe/"
        }

    try:
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        path = parsed_url.path.rstrip('/')

        initial_map = query_params.get("initialMap", [""])[0]
        initial_query = query_params.get("initialQuery", [""])[0]

        query_parts = []

        if initial_map == "productClusterIds" and initial_query:
            api_base_url = "https://www.coolbox.pe/api/catalog_system/pub/products/search"
            query_parts.append(f"fq=productClusterIds:{initial_query}")
        else:
            api_base_url = f"https://www.coolbox.pe/api/catalog_system/pub/products/search{path}"

        params_ignorar = ['initialmap', 'initialquery', 'map', 'query', 'searchstate', '_from', '_to']
        
        if parsed_url.query:
            for pair in parsed_url.query.split('&'):
                if not pair or '=' not in pair: continue
                key, val = pair.split('=', 1)
                key_lower = key.lower()
                if key_lower in params_ignorar: continue
                if key_lower in ['order', 'orderby']: query_parts.append(f"O={val}")
                else: query_parts.append(pair)
        
        if not any(p.startswith('O=') for p in query_parts):
            query_parts.append("O=OrderByPriceASC")
        query_parts.append("_from=0")
        query_parts.append("_to=49")

        final_query_string = "&".join(query_parts)
        final_api_url = sanitizar_url(f"{api_base_url}?{final_query_string}")

        safe_log("📡 [Coolbox API] Consultando catálogo VTEX...", "info")
        resp = requests.get(final_api_url, headers=headers, timeout=15, verify=False)

        if resp.status_code in [200, 206]:
            data = resp.json()
            safe_log(f"🔍 [Coolbox API] Catálogo recibido ({len(data)} ítems). Procesando...", "info")

            url_decodificada = unquote(url).lower()
            exigir_50_59_tv = "50-59" in url_decodificada and ("tv" in path or "televisor" in path or "todo-tv" in path)

            for p in data:
                try:
                    nombre_prod = p.get("productName", "").strip().upper()
                    
                    if exigir_50_59_tv:
                        match_pulgadas = re.search(r'(\d{2})\s*(?:"|”|’|PULGADAS|PULGADA|P\b)', nombre_prod)
                        if match_pulgadas:
                            pulgadas = int(match_pulgadas.group(1))
                            if not (50 <= pulgadas <= 59): continue
                        elif not any(k in nombre_prod for k in ["50-59", "50", "55", "58"]): continue

                    link_rel = p.get("link", "")
                    link_final = urljoin("https://www.coolbox.pe", link_rel) if link_rel else url

                    items = p.get("items", [])
                    if not items: continue

                    first_item = items[0]
                    images = first_item.get("images", [])
                    img_final = images[0].get("imageUrl", "") if images else ""
                    if img_final.startswith('//'): img_final = 'https:' + img_final

                    sellers = first_item.get("sellers", [])
                    if not sellers: continue

                    offer = sellers[0].get("commertialOffer", {})
                    if offer.get("AvailableQuantity", 0) <= 0: continue

                    p_o = float(offer.get("Price", 0.0))
                    p_r = float(offer.get("ListPrice", p_o))
                    
                    p_tarjeta = None
                    installment_options = offer.get("PaymentOptions", {}).get("installmentOptions", [])
                    
                    for option in installment_options:
                        p_name = f"{option.get('paymentSystemName', '')} {option.get('paymentName', '')}".lower()
                        if any(t in p_name for t in ["oh", "bcp", "cmr", "diners", "tarjeta", "bbva"]):
                            installments = option.get("installments", [])
                            if installments:
                                total_val = float(installments[0].get("total", 0))
                                val = total_val / 100.0 if total_val > 10000 else float(installments[0].get("value", 0))
                                if 0 < val < p_o:
                                    p_tarjeta = val
                                    break

                    precio_minimo = p_tarjeta if p_tarjeta else p_o

                    if 0 < precio_minimo <= limite:
                        productos_map[link_final] = {
                            "nombre": f"COOLBOX - {nombre_prod}",
                            "precio": p_o,
                            "precio_tarjeta": p_tarjeta,
                            "precio_regular": max(p_r, p_o),
                            "link": link_final,
                            "img": img_final
                        }
                except Exception: continue
        else:
            safe_log(f"🛑 [Coolbox API] Código HTTP: {resp.status_code}", "error")

    except Exception as e:
        safe_log(f"🛑 [Coolbox API] Error crítico: {e}", "error")

    productos_list = list(productos_map.values())
    if productos_list:
        safe_log(f"✅ [Coolbox] ¡Éxito! Se indexaron {len(productos_list)} ofertas válidas.", "success")
    else:
        safe_log(f"⚠️ [Coolbox] No hay productos que cumplan el filtro por debajo de S/. {limite:.2f}", "warning")

    return productos_list

def motor_tradicional_general(url, limite, headers):
    productos = []
    url = sanitizar_url(url)
    try:
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        if resp.status_code in [200, 206]:
            soup = BeautifulSoup(resp.text, 'html.parser')
            items = soup.find_all(['div', 'article', 'li', 'a'], class_=lambda x: x and any(k in x.lower() for k in ['product', 'card', 'item', 'grid']))
            for t in items:
                try:
                    tit = t.find(['h3', 'h2', 'span', 'p', 'div', 'a'], class_=re.compile(r'(title|name|nombre|description)', re.I))
                    if not tit or len(tit.text.strip()) < 3: continue
                    precios = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', t.text)
                    if precios:
                        p_o = limpiar_precio_pnp(precios[0])
                        if p_o <= limite:
                            del_el = t.find(['del', 'span'], class_=re.compile(r'(regular|original|old)', re.I))
                            p_r_matches = re.findall(r'(?:S/\.?\s*)(\d[\d\.,]*)', del_el.text) if del_el else []
                            p_r = limpiar_precio_pnp(p_r_matches[0]) if p_r_matches else p_o
                            a_el = t.find('a', href=True) or (t if t.name == 'a' and t.has_attr('href') else None)
                            if a_el and 'productos?' not in a_el['href'].lower():
                                img_el = t.find('img', src=True)
                                productos.append({"nombre": tit.text.strip().upper(), "precio": p_o, "precio_regular": p_r, "link": urljoin(url, a_el['href']), "img": img_el['src'] if img_el else ""})
                except Exception: continue
    except Exception: pass
    return productos 

def motor_nike(url, limite=9999, max_pages=10, use_playwright_fallback=False, session=None, step=12, sz=None, max_items=500):
    logs_ejecucion = []
    url = sanitizar_url(url)

    def _safe_log(msg, level="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level.upper()}] {msg}"
        logs_ejecucion.append(log_entry)
        try:
            if 'safe_log' in globals(): safe_log(msg, level)
            else: print(log_entry)
        except Exception: print(log_entry)

    def _save_debug(name, content, mode="w"):
        try:
            os.makedirs("ml_debug", exist_ok=True)
            path = os.path.join("ml_debug", name)
            with open(path, mode, encoding="utf-8") as fh: fh.write(content)
            return path
        except Exception as e:
            _safe_log(f"No se pudo guardar debug {name}: {e}", "warning")
            return None

    def _safe_parse_price(val):
        if 'limpiar_precio_pnp' in globals():
            try: return float(limpiar_precio_pnp(val))
            except Exception: pass
        try:
            s = re.sub(r'[^\d\.,]', '', str(val))
            if s.count('.') > 1: s = s.replace('.', '')
            s = s.replace(',', '.')
            return float(s) if s else 0.0
        except Exception: return 0.0

    def _normalize_identifier(link):
        try:
            m = re.search(r'([A-Z0-9\-]{4,})', link.split('?')[0].rstrip('/').split('/')[-1])
            if m: return f"NIKE-{m.group(1).upper()}"
            hash_md5 = hashlib.md5(link.encode('utf-8')).hexdigest()[:10].upper()
            return f"NIKE-{hash_md5}"
        except Exception:
            hash_md5 = hashlib.md5(link.encode('utf-8')).hexdigest()[:10].upper()
            return f"NIKE-{hash_md5}"

    start_ts = datetime.now(timezone.utc).isoformat()
    productos = []
    session = session or requests.Session()
    sz = sz or step
    STEP_SIZE = int(step)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Referer": "https://www.nike.com.pe/"
    }
    session.headers.update(headers)

    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    vistos = set()
    total_checked = 0

    _safe_log(f"🚀 Iniciando motor_nike para URL: {url}")

    try:
        for page in range(1, max_pages + 1):
            offset = (page - 1) * STEP_SIZE
            query_params["start"] = [str(offset)]
            query_params["sz"] = [str(sz)]
            new_query = urlencode(query_params, doseq=True)
            page_url = urlunparse((parsed_url.scheme, parsed_url.netloc, parsed_url.path, parsed_url.params, new_query, parsed_url.fragment))

            _safe_log(f"⚡ Escaneando Página {page} (start={offset})...")

            resp = None
            attempts, backoff = 0, 1
            while attempts < 3:
                try:
                    session.headers.update({"User-Agent": headers["User-Agent"]})
                    resp = session.get(page_url, timeout=15)
                    break
                except requests.RequestException as e:
                    attempts += 1
                    _safe_log(f"⚠️ Intento {attempts} falló: {e}", "warning")
                    time.sleep(backoff)
                    backoff *= 2

            if not resp:
                _safe_log("❌ Error fatal: No se obtuvo respuesta HTTP de Nike.", "error")
                break

            _safe_log(f"📡 [DIAGNÓSTICO NIKE] Status Code recibido: {resp.status_code}")
            _safe_log(f"📡 [DIAGNÓSTICO NIKE] Tamaño del contenido: {len(resp.text)} caracteres")
            
            preview_texto = resp.text[:300].replace('\n', ' ').strip()
            _safe_log(f"🔍 [DIAGNÓSTICO NIKE] Preview HTML: {preview_texto}...")

            _save_debug("raw_html_nike.html", resp.text)
            _save_debug("raw_html_last.html", resp.text)

            if resp.status_code != 200:
                _safe_log(f"🛑 HTTP {resp.status_code} devuelto por Nike en {page_url}", "error")
                break

            text = resp.text
            soup = BeautifulSoup(text, "html.parser")

            page_title = soup.title.text.lower() if soup and soup.title else ""
            if resp.status_code in [403, 429] or any(term in page_title for term in ["access denied", "attention required", "cloudflare", "security check"]):
                _safe_log("🚨 [ALERTA] El servidor devolvió una página de seguridad/bloqueo anti-bot de Nike.", "error")

            page_products = []

            # Capa 1: JSON
            if '"results"' in text or '"products"' in text or '"searchResults"' in text:
                try:
                    for script in soup.find_all("script"):
                        script_content = script.string or script.text or ""
                        if any(k in script_content for k in ['"results"', '"products"', '"searchResults"']):
                            try:
                                script_clean = script_content.strip()
                                if script_clean.startswith('{') and script_clean.endswith('}'):
                                    parsed = json.loads(script_clean)
                                    results = parsed.get("results") or parsed.get("products") or parsed.get("searchResults") or []
                                    for it in results:
                                        if len(productos) + len(page_products) >= max_items: break
                                        if not isinstance(it, dict): continue
                                        nombre = (it.get("title") or it.get("name") or "").strip()
                                        precio = float(it.get("price") or 0) if it.get("price") else 0.0
                                        link = it.get("permalink") or it.get("url") or ""
                                        img = it.get("thumbnail") or it.get("image") or ""
                                        if nombre and 0 < precio <= limite:
                                            ident = _normalize_identifier(link or page_url)
                                            if ident in vistos: continue
                                            vistos.add(ident)
                                            page_products.append({
                                                "identificador": ident, "nombre": f"NIKE - {nombre.upper()}",
                                                "precio": precio, "precio_regular": float(it.get("original_price") or precio),
                                                "link": link, "img": img, "fecha": datetime.now(timezone.utc).isoformat()
                                            })
                            except Exception: continue
                    if page_products:
                        _safe_log(f"✅ Se hallaron {len(page_products)} productos vía JSON embebido.")
                except Exception as e_json:
                    _safe_log(f"Error procesando JSON: {e_json}", "warning")

            # Capa 2: DOM HTML
            if not page_products:
                cards = soup.select(".product-tile, .product-card, .product-grid li, .product-grid div.product, a[href*='/product/'], a[href*='/productos/']")
                _safe_log(f"🔍 Tarjetas detectadas en HTML mediante selectores: {len(cards)}")

                for t in cards:
                    if len(productos) + len(page_products) >= max_items: break
                    try:
                        total_checked += 1
                        a_el = t if t.name == "a" else t.select_one("a[href]") or t
                        href = a_el.get("href") if a_el else None
                        if not href: continue
                        link_final = urljoin(f"{parsed_url.scheme}://{parsed_url.netloc}", href) if href.startswith("/") else href

                        tit_el = t.select_one(".product-name, .product-tile-title, .product-title, .pdp-link, h2, h3")
                        nombre = (tit_el.text.strip() if tit_el else (a_el.get("aria-label") or a_el.text or "")).strip()
                        if not nombre or len(nombre) < 3 or "TODAS" in nombre.upper(): continue

                        price_container = t.select_one(".price, .product-price, .product-tile-price") or t
                        price_texts = []
                        for sel in ["span.price", "span.amount", ".sales .value", ".value", "span"]:
                            el = price_container.select_one(sel)
                            if el and el.text: price_texts.append(el.text)

                        p_o = 0.0
                        if price_texts:
                            for txt in price_texts:
                                p = _safe_parse_price(txt)
                                if p > 0:
                                    p_o = p
                                    break
                        if p_o == 0.0:
                            m = re.search(r"(?:S/\.?\s*)(\d[\d\.,]*)", t.text)
                            if m: p_o = _safe_parse_price(m.group(1))

                        if p_o == 0.0: continue

                        p_r = p_o
                        del_el = t.select_one("del, .strike-through, .original-price")
                        if del_el and del_el.text:
                            p_r_val = _safe_parse_price(del_el.text)
                            if p_r_val > 0: p_r = p_r_val

                        if p_o < 30.0: continue

                        if not (0 < p_o <= limite): continue

                        identificador = _normalize_identifier(link_final)
                        if identificador in vistos: continue

                        img_el = t.select_one("img")
                        img_url = ""
                        if img_el:
                            img_url = img_el.get("data-src") or img_el.get("src") or ""
                            if img_url.startswith("//"): img_url = "https:" + img_url

                        vistos.add(identificador)
                        page_products.append({
                            "identificador": identificador, "nombre": f"NIKE - {nombre.upper()}",
                            "precio": p_o, "precio_regular": max(p_r, p_o), "link": link_final,
                            "img": img_url, "fecha": datetime.now(timezone.utc).isoformat()
                        })
                    except Exception: continue

            if not page_products:
                _safe_log(f"🛑 No se encontraron productos válidos en la página start={offset}. Finalizando ciclo.")
                break

            existing_links = {p["link"] for p in productos}
            for p in page_products:
                if p.get("link") not in existing_links:
                    productos.append(p)
                    existing_links.add(p.get("link"))

            _safe_log(f"📈 Total acumulado de productos válidos: {len(productos)}")
            time.sleep(random.uniform(0.6, 1.4))

            if len(productos) >= max_items: break

    except Exception as e:
        _safe_log(f"💥 Error crítico general en motor_nike: {e}", "error")

    combined = {
        "metadata": {"url_tested": url, "limit": limite, "max_pages": max_pages, "step": STEP_SIZE, "sz": sz, "timestamp": start_ts, "checked": total_checked},
        "logs": logs_ejecucion,
        "productos": productos
    }
    try:
        _save_debug("combined_debug.json", json.dumps(combined, ensure_ascii=False, indent=2))
    except Exception: pass

    return productos

# =======================================================
# ENRUTADOR AISLADO
# =======================================================
def escanear_tienda(url, limite, headers=None):
    url = sanitizar_url(url)
    dominio = urlparse(url).netloc.lower()
    
    if headers is None:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
    
    safe_log(f"🔎 [Enrutador] Analizando URL: {url} | Dominio detectado: {dominio}", "info")
    
    if "carsa.pe" in dominio:
        return motor_carsa(url, limite)
    elif "thn.pe" in dominio:
        return motor_thn(url, limite)
    elif any(k in dominio for k in ["tiendabelcorp", "cyzone", "lbel", "esika"]):
        return motor_belcorp(url, limite, headers)
    elif "efe.com.pe" in dominio or "lacuracao.pe" in dominio:
        return motor_conecta_retail(url, limite, headers, "EFE" if "efe.com.pe" in dominio else "CURACAO")
    elif "falabella.com" in dominio:
        return motor_falabella(url, limite, headers)
    elif "adidas.pe" in dominio:
        return motor_adidas(url, limite)
    elif "platanitos.com" in dominio:
        return motor_platanitos(url, limite)
    elif "hiraoka.com.pe" in dominio:
        return motor_hiraoka(url, limite)
    elif "oechsle.pe" in dominio:
        return motor_oechsle(url, limite)
    elif "plazavea.com.pe" in dominio:
        return motor_plazavea(url, limite, headers=headers)
    elif "juntoz.com" in dominio:
        return motor_juntoz(url, limite, headers=headers)
    elif "triathlon.com.pe" in dominio:
        return motor_triathlon(url, limite, headers=headers)
    elif "ripley.com.pe" in dominio:
        return motor_ripley(url, limite, headers=headers)
    elif "footloose.pe" in dominio:
        return motor_footloose(url, limite)
    elif "estilos.com.pe" in dominio:
        return motor_estilos(url, limite)
    elif "promart.pe" in dominio:
        return motor_promart(url, limite, headers=headers)
    elif "coolbox.pe" in dominio:
        return motor_coolbox(url, limite, headers=headers)
    elif "nike.com.pe" in dominio:
        return motor_nike(url, limite)
    else:
        safe_log(f"💤 [Enrutador] Tienda sin motor específico. Aplicando motor tradicional general.", "info")
        return motor_tradicional_general(url, limite, headers)

# =======================================================
# SISTEMA DE PATRULLAJE CENTRAL
# =======================================================
def revisar_ofertas(filtro_objetivo="TODOS"):
    try: 
        res = supabase.table("radares").select("*").execute()
    except Exception as e: 
        safe_log(f"🛑 Error de conexión con Supabase (Tabla radares): {e}", "error")
        return f"Fallo Supabase: {e}"
        
    if not res or not res.data: return "Sin radares activos."
    
    total, alertas = 0, 0
    enviados = set()
    lista_html_streamlit = []
    zona_peru = timezone(timedelta(hours=-5))
    fecha_hoy = datetime.now(zona_peru).strftime("%Y-%m-%d %H:%M:%S")
    target = str(filtro_objetivo).strip().upper()
    
    mapa_emojis = {
        "PERFUMES": "🧪", "ZAPATILLAS": "👟", "MEDIAS": "🧦", "POLOS": "👕", 
        "CASACAS": "🧥", "SHORTS": "🩳", "BUZOS": "👖", "AUDIFONOS": "🎧", 
        "TV": "📺", "PARLANTE": "🔊", "BARRA DE SONIDO": "🎵", "CELULAR": "📱", 
        "PC": "💻", "REFRIGERADORA": "❄️", "LAVADORA": "🧺", "ELECTRODOMESTICOS": "🔌", 
        "CAMA": "🛏️", "OTROS": "📦"
    }
    
    safe_log("🔍 **Iniciando Patrullaje y Diagnóstico en Vivo...**", "info")
    
    for item in res.data:
        ident = item['identificador'].upper()
        url_low = sanitizar_url(item['url']).lower()
        
        # Identificar si es un accesorio/insumo para no clasificarlo como electrodoméstico principal
        es_accesorio = any(acc in ident or acc.lower() in url_low for acc in [
            "FILTRO", "DETERGENTE", "LIMPIADOR", "PROTECTOR", "FUNDA", "CABLE", 
            "SOPORTE", "AMORTIGUADOR", "REPUESTO", "ADAPTADOR", "PASTILLA", "JABON"
        ])

        # Categorización precisa
        if es_accesorio: grupo = "OTROS"
        elif "SHORT" in ident or "short" in url_low: grupo = "SHORTS"
        elif "PERFUME" in ident or "perfume" in url_low: grupo = "PERFUMES"
        elif "ZAPATILLA" in ident or "zapatilla" in url_low or "calzado" in url_low or "nike.com.pe" in url_low: grupo = "ZAPATILLAS"
        elif "MEDIAS" in ident or "medias" in url_low: grupo = "MEDIAS"
        elif "POLO" in ident or "polo" in url_low: grupo = "POLOS"
        elif "CASACA" in ident or "casaca" in url_low or "polera" in url_low: grupo = "CASACAS"
        elif "BUZO" in ident or "buzo" in url_low or "pantalon" in url_low: grupo = "BUZOS"
        elif "AUDIFONO" in ident or "audifono" in url_low: grupo = "AUDIFONOS"
        elif "TV" in ident or "smart-tv" in url_low: grupo = "TV"
        elif "PARLANTE" in ident or "speaker" in url_low: grupo = "PARLANTE"
        elif "BARRA" in ident or "soundbar" in url_low: grupo = "BARRA DE SONIDO"
        elif "CELULAR" in ident or "phone" in url_low or "celular" in url_low: grupo = "CELULAR"
        elif "PC" in ident or "laptop" in url_low: grupo = "PC"
        elif "REFRIGERADORA" in ident or "refrig" in url_low: grupo = "REFRIGERADORA"
        elif "LAVADORA" in ident: grupo = "LAVADORA"
        elif "ELECTRO" in ident: grupo = "ELECTRODOMESTICOS"
        elif "CAMA" in ident or "colchon" in url_low: grupo = "CAMA"
        else: grupo = "OTROS"

        if target != "TODOS" and target != grupo: continue
            
        tienda_actual = ident.replace('_', '-').split('-')[0]
        safe_log(f"🔄 Patrullando Tienda: {tienda_actual} | Categoría: {grupo}...", "info")
        
        prods = escanear_tienda(item['url'], item['precio_max'])
        
        # 🛡️ REGISTRO AUTOMÁTICO DE SALUD DE SCRAPERS
        registrar_resultado_salud(
            supabase_client=supabase,
            tienda=tienda_actual,
            total_productos=len(prods),
            url_origen=item['url']
        )

        # Consultar cupones activos para la tienda actual en Supabase
        bloque_cupones = obtener_bloque_cupones_telegram(tienda_actual)
        bloque_cupones_str = f"\n{bloque_cupones}" if bloque_cupones else ""

        # Actualizar la fecha del último escaneo en la tabla radares
        try:
            supabase.table("radares").update({"ultimo_escaneo": fecha_hoy}).eq("identificador", item['identificador']).execute()
        except Exception:
            pass

        for p in prods:
            try:
                n_u = re.sub(r'\s+', ' ', p['nombre']).strip().upper()
                
                if grupo in ["BARRA DE SONIDO", "PARLANTE", "AUDIFONOS"]:
                    palabras_prohibidas = ["SABANA", "SÁBANA", "ALMOHADA", "COLCHON", "COLCHÓN", "EDREDON", "EDREDÓN", "CAMA", "FRAZADA", "MANTA"]
                    if any(bad in n_u for bad in palabras_prohibidas): continue
                
                if n_u in enviados: continue
                enviados.add(n_u)
                total += 1
                p_v = float(p['precio'])
                
                # Respetar intacto el precio regular de la web
                p_r = max(float(p.get('precio_regular', p_v)), p_v)
                
                p['tienda_origen'] = tienda_actual
                lista_html_streamlit.append(p)
                
                id_limpio = re.sub(r'[^A-Z0-9_]', '', n_u.replace(' ', '_'))
                id_registro = f"{item['identificador']}-{id_limpio}"[:200]
                
                precio_anterior = None
                try:
                    res_ant = supabase.table("historial_precios").select("precio").eq("identificador", id_registro).execute()
                    if res_ant.data and len(res_ant.data) > 0:
                        precio_anterior = float(res_ant.data[0]['precio'])
                except Exception: pass

                # Saneamiento de imágenes para Supabase/Telegram
                img_limpia = sanitizar_url(p.get('img', ''))
                if not img_limpia or img_limpia.lower() in ['empty', 'none', 'null']:
                    img_limpia = None

                datos_guardar = {
                    "identificador": id_registro, 
                    "precio": p_v, 
                    "precio_regular": p_r, 
                    "link_producto": sanitizar_url(p['link']), 
                    "imagen_producto": img_limpia, 
                    "fecha": fecha_hoy
                }
                
                emoji = mapa_emojis.get(grupo, "🔥")

                # =======================================================
                # 🚨 EVALUACIÓN DE DETECCIÓN DE BUG / ERROR DE PRECIO
                # =======================================================
                es_bug, pct_descuento = es_error_de_precio(
                    precio_actual=p_v, 
                    precio_regular=p_r, 
                    precio_anterior=precio_anterior, 
                    categoria=grupo
                )

                if es_bug:
                    if precio_anterior is None:
                        try: supabase.table("historial_precios").insert(datos_guardar).execute()
                        except Exception: pass
                    else:
                        try: supabase.table("historial_precios").update(datos_guardar).eq("identificador", id_registro).execute()
                        except Exception: pass

                    msg_bug = (
                        f"🚨🚨 <b>¡POSIBLE ERROR DE PRECIO / BUG!</b> 🚨🚨\n"
                        f"‼️ <b>¡COMPRA RÁPIDO ANTES QUE LO CORRIJAN!</b> ‼️\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📦 <b>Producto:</b> <code>{p['nombre']}</code>\n"
                        f"🏪 <b>Tienda:</b> <code>{tienda_actual}</code>\n"
                        f"💥 <b>Precio BUG:</b> <b>S/. {p_v:.2f}</b>\n"
                        f"❌ <b>Precio Normal:</b> S/. {p_r:.2f}\n"
                        f"🔥 <b>Descuento Brutal:</b> {pct_descuento:.0f}%\n\n"
                        f"⏰ <i>Nota: Los errores de sistema suelen durar pocos minutos.</i>"
                        f"{bloque_cupones_str}"
                    )
                    if enviar_telegram_real(msg_bug, p['link'], img_limpia or ""): 
                        alertas += 1
                        safe_log(f"🔥 ¡BUG DE PRECIO DETECTADO Y ENVIADO! -> {p['nombre']}", "success")
                        time.sleep(0.3)
                    continue

                if precio_anterior is None:
                    # 1. PRODUCTO NUEVO EN BASE DE DATOS -> Guarda y Envía Alerta
                    try: supabase.table("historial_precios").insert(datos_guardar).execute()
                    except Exception: pass

                    msg_t = (
                        f"✨ <b>¡NUEVO PRODUCTO ENCONTRADO!</b> ✨\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📦 <b>Producto:</b> <code>{p['nombre']}</code>\n"
                        f"🏪 <b>Tienda:</b> <code>{tienda_actual}</code>\n"
                        f"💰 <b>Precio Encontrado:</b> S/. {p_v:.2f}"
                        f"{bloque_cupones_str}"
                    )
                    if enviar_telegram_real(msg_t, p['link'], img_limpia or ""): 
                        alertas += 1
                        time.sleep(0.3)

                elif p_v < precio_anterior:
                    # 2. PRODUCTO REGISTRADO QUE BAJÓ DE PRECIO -> Actualiza BD y Envía Alerta
                    try: supabase.table("historial_precios").update(datos_guardar).eq("identificador", id_registro).execute()
                    except Exception: pass

                    ahorro = precio_anterior - p_v
                    msg_t = (
                        f"{emoji} <b>¡OFERTA: BAJÓ DE PRECIO!</b> {emoji}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📦 <b>Producto:</b> <code>{p['nombre']}</code>\n"
                        f"🏪 <b>Tienda:</b> <code>{tienda_actual}</code>\n"
                        f"❌ <b>Precio Anterior:</b> S/. {precio_anterior:.2f}\n"
                        f"💰 <b>Nuevo Precio Oferta:</b> S/. {p_v:.2f}\n"
                        f"📉 <b>Te Ahorras:</b> S/. {ahorro:.2f}"
                        f"{bloque_cupones_str}"
                    )
                    if enviar_telegram_real(msg_t, p['link'], img_limpia or ""): 
                        alertas += 1
                        time.sleep(0.3)

                else:
                    # 3. PRODUCTO REGISTRADO SIN BAJADA DE PRECIO Y SIN BUG -> Actualiza BD en silencio
                    try: supabase.table("historial_precios").update(datos_guardar).eq("identificador", id_registro).execute()
                    except Exception: pass

            except Exception: continue

    safe_log("✅ **¡Patrullaje y Diagnóstico Finalizados con Éxito!**", "success")

    if len(lista_html_streamlit) > 0:
        try:
            st.markdown("---")
            st.markdown(f"### 🎯 Modelos encontrados e indexados en vivo ({len(lista_html_streamlit)}):")
            for prod in lista_html_streamlit:
                with st.container(border=True):
                    col1, col2 = st.columns([2, 8])
                    with col1:
                        if prod.get('img') and len(prod['img']) > 5: st.image(prod['img'], width=120)
                        else: st.write("📷 _Sin Foto_")
                    with col2:
                        st.markdown(f"#### `{prod['nombre']}`")
                        st.markdown(f"🏪 **Tienda de Origen:** `{prod['tienda_origen']}`")
                        p_oferta = prod['precio']
                        p_regular = prod.get('precio_regular', p_oferta)
                        if p_regular > p_oferta:
                            ahorro_soles = p_regular - p_oferta
                            porcentaje = (ahorro_soles / p_regular) * 100
                            st.markdown(f"❌ ~~Precio Regular: S/. {p_regular:.2f}~~")
                            st.markdown(f"💰 **Precio Oferta: S/. {prod['precio']:.2f}**")
                            st.markdown(f"🔥 **¡Ahorraste S/. {ahorro_soles:.2f}! ({porcentaje:.0f}% de Descuento)**")
                        else:
                            st.markdown(f"💰 **Precio Actual: S/. {prod['precio']:.2f}**")
                        st.markdown(f"🔗 [🌐 IR A COMPRAR DIRECTO]({prod['link']})")
        except Exception: pass

    return f"Éxito. Modelos procesados: {total}. Alertas Telegram: {alertas}."
