import os
import json
import requests
import streamlit as st
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from config import supabase
from utils import sanitizar_url, safe_log, limpiar_precio_pnp

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

    FRECUENCIA_MINUTOS = 240  # 4 Horas
    
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
                    safe_log(f"⏳ [Adidas] Esta URL se escaneó hace {int(minutos_transcurridos)} min. Omitiendo...", "caption")
                    return []
    except Exception as e:
        safe_log(f"⚠️ No se pudo verificar el temporizador de Adidas en radares: {e}", "caption")

    productos_map = {}
    texto_html = ""

    lista_keys = []
    try:
        if hasattr(st, "secrets"):
            for key_name in ["SCRAPERAPI_KEY", "SCRAPERAPI_KEY_2", "SCRAPERAPI_KEY_3"]:
                if key_name in st.secrets and st.secrets[key_name]:
                    val = str(st.secrets[key_name]).strip()
                    if val and val not in lista_keys: lista_keys.append(val)
    except Exception: pass
    
    for key_name in ["SCRAPERAPI_KEY", "SCRAPERAPI_KEY_2", "SCRAPERAPI_KEY_3"]:
        if key_name in os.environ and os.environ[key_name]:
            val = str(os.environ[key_name]).strip()
            if val and val not in lista_keys: lista_keys.append(val)

    if not lista_keys:
        lista_keys.append("4cd72a5cadb77297cd9f41f11dc632c0")

    safe_log(f"🚀 [Adidas] Consultando catálogo vía ScraperAPI ({len(lista_keys)} claves disponibles)...", "info")

    for idx, api_key in enumerate(lista_keys, 1):
        payload = {'api_key': api_key, 'url': url}
        try:
            resp = requests.get('https://api.scraperapi.com/', params=payload, timeout=40)
            status_code = resp.status_code
            
            if status_code == 200 and len(resp.text) > 5000:
                texto_html = resp.text
                break
            elif status_code in [401, 403, 429]:
                safe_log(f"🚨 [Adidas] Error HTTP {status_code} con clave #{idx}. Cambiando a clave de respaldo...", "warning")
                continue
            else:
                safe_log(f"⚠️ [Adidas] ScraperAPI respuesta inusual (HTTP {status_code}) con clave #{idx}.", "warning")
        except Exception as e:
            safe_log(f"🚨 [Adidas] Error de conexión con ScraperAPI (Clave #{idx}): {e}", "warning")
            continue

    if not texto_html or len(texto_html) <= 5000:
        safe_log("🛑 [Adidas] Imposible obtener respuesta HTML válida de Adidas tras probar todas las claves.", "error")
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
