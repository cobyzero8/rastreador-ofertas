import re
import requests
from utils import sanitizar_url, safe_log

def motor_carsa(url, limite):
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
