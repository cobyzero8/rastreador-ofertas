import re
import streamlit as st

def sanitizar_url(url_raw):
    if not url_raw: return ""
    url = str(url_raw).strip()
    match = re.search(r'\((https?://[^\s)]+)\)', url)
    if match: url = match.group(1)
    return re.sub(r'^[\[\'"]+|[\]\'"]+$', '', url).strip()

def safe_log(texto, tipo="text"):
    try:
        if tipo in ["text", "write"]: st.write(texto)
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
        texto = re.sub(r'[^\d.,]', '', str(texto_precio)).strip()
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

def es_error_de_precio(precio_actual, precio_regular, precio_anterior=None, categoria="OTROS"):
    if precio_actual <= 0: return False, 0.0
    p_reg = max(precio_regular, precio_actual)
    ahorro_soles = p_reg - precio_actual
    descuento_pct = (ahorro_soles / p_reg) * 100.0 if p_reg > 0 else 0.0
    es_precio_reg_ficticio = (p_reg >= 9999.0 or p_reg > precio_actual * 4.0)

    if descuento_pct >= 75.0 and ahorro_soles >= 30.0 and not es_precio_reg_ficticio:
        return True, descuento_pct

    if precio_anterior and precio_anterior > 0:
        caida_historica = ((precio_anterior - precio_actual) / precio_anterior) * 100.0
        if caida_historica >= 70.0 and (precio_anterior - precio_actual) >= 30.0:
            return True, caida_historica

    categorias_alto_valor = ["TV", "PC", "CELULAR", "REFRIGERADORA", "LAVADORA", "BARRA DE SONIDO"]
    if categoria in categorias_alto_valor and precio_actual <= 50.0 and p_reg >= 300.0 and not es_precio_reg_ficticio:
        return True, descuento_pct

    return False, descuento_pct
