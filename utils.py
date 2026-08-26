import re
import json
import logging
import streamlit as st
import os
from urllib.parse import urlparse, urlunparse
from streamlit.runtime.scriptrunner import get_script_run_ctx

# Desactivar registros de contexto de Streamlit en ejecuciones CLI/Cron
logging.getLogger("streamlit.runtime.scriptrunner.script_runner").setLevel(logging.ERROR)
logging.getLogger("streamlit").setLevel(logging.ERROR)

def analizar_producto_con_gemini(texto_oferta):
    """
    Analiza el texto de una oferta enviada a Telegram usando Gemini
    y genera un veredicto crítico y directo con detección dinámica de modelos.
    """
    try:
        import google.generativeai as genai
    except ImportError:
        return "⚠️ <i>Librería 'google-generativeai' no instalada en el entorno.</i>"

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            pass

    if not api_key:
        return "⚠️ <i>Falta configurar GEMINI_API_KEY en variables de entorno o secrets.</i>"

    try:
        genai.configure(api_key=api_key)

        prompt = f"""
        Actúa como un cazador de ofertas e-commerce en Perú.
        Analiza el siguiente producto extraído de una tienda:

        {texto_oferta}

        Responde en MÁXIMO 2 ORACIONES:
        1. Evalúa si el "Precio Regular" parece inflado artificialmente o si el descuento es real.
        2. Di claramente si CONVIENE COMPRAR O NO por ese valor en soles.
        Sé directo, crítico y no saludes.
        """

        modelos_a_probar = ['gemini-1.5-flash', 'gemini-1.5-pro', 'models/gemini-1.5-flash', 'gemini-pro']

        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    nombre_m = m.name.replace('models/', '')
                    if nombre_m not in modelos_a_probar:
                        modelos_a_probar.insert(0, nombre_m)
        except Exception:
            pass

        response = None
        ultimo_error = ""

        for nombre_modelo in modelos_a_probar:
            try:
                model = genai.GenerativeModel(nombre_modelo)
                response = model.generate_content(prompt)
                if response and response.text:
                    break
            except Exception as e_mod:
                ultimo_error = str(e_mod)
                continue

        if not response or not response.text:
            return f"⚠️ <i>Error de conexión con Gemini: {ultimo_error}</i>"

        veredicto = response.text.strip()

        return (
            f"🧠 <b>VEREDICTO IA:</b>\n"
            f"<blockquote><i>{veredicto}</i></blockquote>"
        )
    except Exception as e:
        return f"⚠️ <i>Error al consultar a Gemini: {e}</i>"

def interpretar_busqueda_gemini(texto_busqueda):
    """
    Usa Gemini para convertir frases en lenguaje natural en un JSON con filtros de búsqueda.
    """
    try:
        import google.generativeai as genai
    except ImportError:
        return None

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get("GEMINI_API_KEY")
        except Exception:
            pass

    if not api_key:
        return None

    try:
        genai.configure(api_key=api_key)

        prompt = f"""
        Convierte la siguiente frase de búsqueda de un usuario en un JSON estricto para filtrar una base de datos e-commerce en Perú.

        Búsqueda del usuario: "{texto_busqueda}"

        Categorías válidas en la BD:
        [PERFUMES, ZAPATILLAS, POLOS, CASACAS, SHORTS, BUZOS, MEDIAS, AUDIFONOS, TV, PARLANTE, BARRA_DE_SONIDO, CELULAR, PC, REFRIGERADORA, LAVADORA, ELECTRODOMESTICOS, CAMPANA_EXTRACTORA, CAMA, OTROS]

        Responde ÚNICAMENTE en formato JSON estricto con esta estructura:
        {{
            "categoria": "NOMBRE_CATEGORIA_O_NULL",
            "precio_max": numero_o_null,
            "palabras_clave": ["palabra1", "palabra2"]
        }}
        """

        modelos_a_probar = ['gemini-1.5-flash', 'gemini-1.5-pro', 'models/gemini-1.5-flash', 'gemini-pro']
        try:
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    nombre_m = m.name.replace('models/', '')
                    if nombre_m not in modelos_a_probar:
                        modelos_a_probar.insert(0, nombre_m)
        except Exception:
            pass

        for nombre_modelo in modelos_a_probar:
            try:
                model = genai.GenerativeModel(nombre_modelo)
                res = model.generate_content(
                    prompt, 
                    generation_config={"response_mime_type": "application/json"}
                )
                if res and res.text:
                    return json.loads(res.text.strip())
            except Exception:
                continue
    except Exception:
        pass

    return None

def buscar_productos_por_ia(supabase_client, texto_busqueda):
    """
    Interpreta la frase del usuario con Gemini y consulta Supabase con los criterios obtenidos.
    """
    criterios = interpretar_busqueda_gemini(texto_busqueda)
    if not criterios or not supabase_client:
        return None, []

    try:
        query = supabase_client.table("historial_precios").select(
            "nombre_producto, precio, precio_regular, link_producto, imagen_producto, identificador"
        )

        cat = criterios.get("categoria")
        if cat and str(cat).upper() not in ["NULL", "NONE", "OTROS", ""]:
            query = query.ilike("identificador", f"%{cat}%")

        p_max = criterios.get("precio_max")
        if p_max and safe_float(p_max) > 0:
            query = query.lte("precio", safe_float(p_max))

        keywords = criterios.get("palabras_clave", [])
        for kw in keywords:
            if len(str(kw)) >= 3:
                query = query.ilike("nombre_producto", f"%{kw}%")

        res = query.order("precio", desc=False).limit(5).execute()
        productos = res.data if res and res.data else []

        return criterios, productos
    except Exception as e:
        safe_log(f"Error consultando Supabase para búsqueda IA: {e}", "error")
        return criterios, []

def safe_log(mensaje, tipo="info"):
    """Imprime mensajes en consola y los envía a Streamlit únicamente si la UI está activa."""
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
        if get_script_run_ctx() is not None:
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
        
        if p_oferta <= 0 or p_oferta < 5.0:
            return True
            
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
