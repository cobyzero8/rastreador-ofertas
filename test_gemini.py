import os
from google import genai

# 1. Coloca tu API Key directamente para probar
API_KEY = "AQ.Ab8RN6KuutkYUM6CJ65rQQx6qvscNR_f66P_kzS911ordtLPfQ"

# 2. Inicializar cliente
client = genai.Client(api_key=API_KEY)

# 3. Datos de prueba
texto_oferta_prueba = """
Producto: TELEVISOR LG 65" NANO 4K UHD AI SMART TV
Tienda: ESTILOS
Precio Encontrado: S/. 1399.00
Precio Regular: S/. 2299.00
"""

prompt = f"""
Actúa como un cazador de ofertas e-commerce en Perú.
Analiza el siguiente producto extraído de una tienda:

{texto_oferta_prueba}

Responde en MÁXIMO 2 ORACIONES:
1. Evalúa si el "Precio Regular" parece inflado artificialmente o si el descuento es real.
2. Di claramente si CONVIENE COMPRAR O NO por ese valor en soles.
Sé directo, crítico y no saludes.
"""

print("🔍 Conectando con Gemini fuera de Telegram...")

# Probar modelos disponibles en el nuevo SDK
modelos_a_probar = ['gemini-2.5-flash', 'gemini-1.5-flash', 'gemini-2.5-pro']

for modelo in modelos_a_probar:
    try:
        print(f"⏳ Intentando con: {modelo}...")
        response = client.models.generate_content(
            model=modelo,
            contents=prompt
        )
        if response and response.text:
            print(f"\n✅ ¡ÉXITO CON {modelo}!")
            print("--------------------------------------------------")
            print(response.text.strip())
            print("--------------------------------------------------")
            break
    except Exception as e:
        print(f"❌ Error con {modelo}: {e}\n")
