import re
import requests
import urllib3
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from utils import sanitizar_url, safe_log

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def limpiar_num_platanitos(texto):
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
    Motor extractor de productos para Platanitos Perú (platanitos.com)
    """
    productos_map = {}
    url_base = sanitizar_url(url)

    headers_base = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-PE,es;q=0.9,en;q=0.8",
        "Referer": "https://platanitos.com/"
    }
    if headers:
        headers_base.update(headers)

    try:
        safe_log(f"📡 [PLATANITOS] Consultando catálogo...", "info")
        session = requests.Session()
        resp = session.get(url_base, headers=headers_base, timeout=15, verify=False)

        if resp.status_code != 200:
            safe_log(f"🛑 [PLATANITOS] El servidor devolvió HTTP {resp.status_code}", "error")
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Buscar enlaces a /pe/producto/
        enlaces_prod = soup.find_all('a', href=lambda h: h and '/pe/producto/' in str(h).lower())

        for a_tag in enlaces_prod:
            try:
                href = a_tag['href'].strip()
                link_final = urljoin("https://platanitos.com", href).split('?')[0].split('#')[0]

                card = a_tag.find_parent(['div', 'article', 'li']) or a_tag
                texto_card = card.get_text(separator=' ', strip=True)

                # Extraer nombre
                nombre = ""
                nombre_el = card.find(['h2', 'h3', 'h4', 'p', 'span'], class_=lambda c: c and any(k in str(c).lower() for k in ['title', 'nombre', 'product', 'item']))
                if nombre_el:
                    nombre = nombre_el.get_text(strip=True).upper()
                
                if not nombre or len(nombre) < 3:
                    img_in_a = card.find('img', alt=True)
                    if img_in_a and len(img_in_a['alt'].strip()) > 3:
                        nombre = img_in_a['alt'].strip().upper()
                    else:
                        nombre = a_tag.get_text(strip=True).upper()

                nombre = re.sub(r'S/\.?\s*\d+[\d\.,]*', '', nombre)
                nombre = re.sub(r'\s+', ' ', nombre).strip()

                if not nombre or len(nombre) < 3 or nombre in ['VER MÁS', 'COMPRAR', 'NUEVO']: continue

                # Precios
                precios_encontrados = re.findall(r'(?:S/\.?\s*|PEN\s*)(\d[\d\.,]*)', texto_card)
                precios_numeros = [limpiar_num_platanitos(p) for p in precios_encontrados if limpiar_num_platanitos(p) > 0]

                if not precios_numeros: continue

                precios_unicos = sorted(list(set(precios_numeros)))
                p_o = precios_unicos[0]
                p_r = precios_unicos[-1] if len(precios_unicos) > 1 else p_o

                # Imagen
                img_el = card.find('img')
                img_url = ""
                if img_el:
                    img_url = img_el.get('src') or img_el.get('data-src') or img_el.get('data-lazy') or ""

                if img_url:
                    if img_url.startswith('//'): img_url = 'https:' + img_url
                    elif not img_url.startswith('http'): img_url = urljoin("https://platanitos.com", img_url)

                if 0 < p_o <= limite:
                    productos_map[link_final] = {
                        "nombre": f"PLATANITOS - {nombre}",
                        "precio": p_o,
                        "precio_regular": max(p_r, p_o),
                        "link": link_final,
                        "img": img_url
                    }
            except Exception:
                continue

    except Exception as e:
        safe_log(f"🚨 [PLATANITOS] Error en petición: {e}", "error")

    productos_finales = list(productos_map.values())
    if productos_finales:
        safe_log(f"✅ [PLATANITOS] ¡Éxito! Se indexaron {len(productos_finales)} ofertas.", "success")
    else:
        safe_log(f"⚠️ [PLATANITOS] No se encontraron productos bajo S/. {limite:.2f}", "warning")

    return productos_finales
