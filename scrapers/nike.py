import os
import re
import time
import json
import random
import hashlib
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, urljoin
from utils import sanitizar_url, safe_log, limpiar_precio_pnp

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
