import re
import requests
from urllib.parse import urlparse, unquote, urljoin
from utils import sanitizar_url, safe_log

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
