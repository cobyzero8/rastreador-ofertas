import re
import streamlit as st
from urllib.parse import urlparse, urlunparse

def safe_log(mensaje, tipo="info"):
    """Imprime mensajes en consola y en Streamlit si la interfaz está activa."""
    prefijos = {
        "info": "ℹ️",
        "success": "✅",
        "warning": "⚠️",
        "error": "🚨",
        "caption": "💬"
    }
    icono = prefijos.get(tipo, "📌")
    print(f"[{tipo.upper()}] {mensaje}")
    try:
        if tipo == "caption":
            st.caption(mensaje)
        elif tipo == "error":
            st.error(mensaje)
        elif tipo == "warning":
            st.warning(mensaje)
        elif tipo == "success":
            st.success(mensaje)
        else:
            st.info(mensaje)
    except Exception:
        pass

def sanitizar_url(url):
    """Limpia y normaliza URLs para evitar errores de formato."""
    if not url:
        return ""
    url = str(url).strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    return urlunparse(parsed)

def safe_float(val):
    """Convierte de forma segura cualquier valor a float."""
    if val is None:
        return 0.0
    try:
        return float(val)
    except (ValueError, TypeError):
        try:
            s = str(val).replace('S/', '').replace('S/.', '').replace(',', '').strip()
            return float(s)
        except Exception:
            return 0.0

def limpiar_precio_pnp(texto):
    """Extrae y convierte precios en formato de soles peruanos a número float."""
    if not texto:
        return 0.0
    texto_str = str(texto)
    match = re.search(r'\d+(?:[.,]\d+)*', texto_str)
    if match:
        raw_num = match.group(0)
        if ',' in raw_num and '.' in raw_num:
            raw_num = raw_num.replace(',', '')
        elif ',' in raw_num and len(raw_num.split(',')[-1]) == 2:
            raw_num = raw_num.replace(',', '.')
        else:
            raw_num = raw_num.replace(',', '')
        try:
            return float(raw_num)
        except ValueError:
            return 0.0
    return 0.0

def es_error_de_precio(precio, precio_regular=0.0, precio_anterior=0.0):
    """
    Valida si un precio es un error evidente (ej. S/. 1.00) 
    o si representa un descuento sospechoso e irreal (> 95% de caída).
    """
    try:
        p_oferta = safe_float(precio)
        p_reg = safe_float(precio_regular)
        
        # 1. Precios ridículamente bajos
        if p_oferta <= 0 or p_oferta < 5.0:
            return True
            
        # 2. Descuentos extremos sospechosos (> 95% de descuento)
        if p_reg > 0 and (p_oferta / p_reg) < 0.05:
            return True
            
        return False
    except Exception:
        return False

def extraer_productos_json_universal(data):
    """Recorre recursivamente un objeto JSON buscando estructuras de productos."""
    productos = []
    if isinstance(data, dict):
        if any(k in data for k in ['displayName', 'productName', 'title']) and any(k in data for k in ['prices', 'price', 'salePrice', 'url', 'link']):
            productos.append(data)
        
        for clave in ['products', 'results', 'items', 'elements', 'itemListElement', 'mainEntity']:
            if clave in data and isinstance(data[clave], list):
                for item in data[clave]:
                    productos.extend(extraer_productos_json_universal(item))
                    
        for k, v in data.items():
            if k not in ['products', 'results', 'items', 'elements', 'itemListElement']:
                productos.extend(extraer_productos_json_universal(v))
                
    elif isinstance(data, list):
        for item in data:
            productos.extend(extraer_productos_json_universal(item))

    unicos = []
    vistos = set()
    for p in productos:
        if isinstance(p, dict):
            ident = p.get('id') or p.get('productId') or p.get('displayName') or p.get('productName')
            if ident and ident not in vistos:
                vistos.add(ident)
                unicos.append(p)
            elif not ident:
                unicos.append(p)
    return unicos

def extraer_numeros_dict(d, lista_salida):
    """Extrae de forma recursiva valores numéricos de un diccionario."""
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, (int, float)) and v > 0:
                lista_salida.append(float(v))
            elif isinstance(v, (dict, list)):
                extraer_numeros_dict(v, lista_salida)
    elif isinstance(d, list):
        for item in d:
            extraer_numeros_dict(item, lista_salida)

def encontrar_foto_fala(prod_dict):
    """Extrae la URL de imagen desde la estructura JSON de Falabella."""
    if not isinstance(prod_dict, dict):
        return ""
    
    for key in ['mediaUrls', 'images', 'image', 'primaryImageUrl', 'iconUrl']:
        val = prod_dict.get(key)
        if isinstance(val, list) and len(val) > 0:
            img = val[0]
            if isinstance(img, dict):
                return img.get('url') or img.get('src') or ""
            return str(img)
        elif isinstance(val, str) and len(val) > 10:
            return val
        elif isinstance(val, dict):
            return val.get('url') or val.get('src') or ""
            
    return ""
