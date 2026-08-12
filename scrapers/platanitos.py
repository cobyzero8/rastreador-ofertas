import re
import random
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from utils import sanitizar_url, safe_log, LISTA_USER_AGENTS

try:
    from curl_cffi import requests as curl_requests
    CURL_DISPONIBLE = True
except ImportError:
    import requests as curl_requests
    CURL_DISPONIBLE = False

def limpiar_precio_pnp(texto):
    if not texto: return 0.0
    texto = str(texto).replace('&nbsp;', ' ').replace('\xa0', ' ')
    texto = texto.replace('S/.', '').replace('S/', '').replace('PEN', '').replace('S', '').strip()
    match = re.search(r'\d+(?:[.,]\d+)*', texto)
    if match:
        raw = match.group(0)
        if ',' in raw and '.' in raw:
            raw = raw.replace(',', '')
        elif ',' in raw and len(raw.split(',')[-1]) == 2:
            raw = raw.replace(',', '.')
        else:
            raw = raw.replace(',', '')
        try: return float(raw)
        except ValueError: return 0.0
    return 0.0

def motor_platanitos(url, limite=999999.0, headers=None):
    """
    Motor Platanitos con tu lógica flexible de tarjetas/precios 
    + Conexión protegida contra HTTP 403.
    """
    productos = []
    url_base = sanitizar_url(url)

    headers_base = {
        "User-Agent": random.choice(LISTA_USER_AGENTS) if 'LISTA_USER_AGENTS' in globals() else "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Referer": "https://platanitos.com/pe"
    }

    try:
        texto_html = ""
        # 🟢 Paso 1: Intentar con curl_cffi para imitar Chrome y pasar Cloudflare
        if CURL_DISPONIBLE:
            try:
                session = curl_requests.Session(impersonate="chrome120")
                resp = session.get(url_base, headers=headers_base, timeout=15)
                if resp.status_code == 200:
                    texto_html = resp.text
            except Exception: pass

        # 🟡 Paso 2: Fallback a requests normal si falla lo anterior
        if not texto_html:
            import requests
            resp = requests.get(url_base, headers=headers_base, timeout=15, verify=False)
            if resp.status_code == 200:
                texto_html = resp.text

        if not texto_html or len(texto_html) < 2000:
            safe_log("⚠️ [PLATANITOS] Respuesta vacía o rebotada por servidor.", "warning")
            return []

        # 🎯 Tu Lógica de Parseo Original (Rápida y Efectiva)
        soup = BeautifulSoup(texto_html, 'html.parser')
        tarjetas = soup.find_all(['div', 'article', 'a'], class_=re.compile(r'(product|card|item|col|grid)', re.I))

        for t in tarjetas:
            try:
                a_el = t.find('a', href=re.compile(r'/producto/', re.I)) or (t if t.name == 'a' and '/producto/' in t.get('href', '').lower() else None)
                if not a_el: continue
                
                link_final = urljoin("https://platanitos.com", a_el['href']).split('?')[0].split('#')[0]

                tit_el = t.find(['h3', 'h2', 'span', 'p', 'div'], class_=re.compile(r'(title|name|nombre|description)', re.I))
                nombre = tit_el.text.strip() if tit_el else ""
                if not nombre and a_el.has_attr('title'): 
                    nombre = a_el['title'].strip()

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

                    productos.append({
                        "nombre": f"PLATANITOS - {nombre.upper()}",
                        "precio": p_o,
                        "precio_regular": p_r,
                        "link": link_final,
                        "img": img
                    })
            except Exception: continue

        if productos:
            safe_log(f"✅ [PLATANITOS] ¡Éxito! Se indexaron {len(productos)} ofertas.", "success")

    except Exception as e:
        safe_log(f"🚨 [PLATANITOS] Error en extracción: {e}", "error")

    return productos
