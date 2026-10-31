import json
from google import genai
from PIL import Image

def calcular_macros_texto(texto_comida, api_key):
    client = genai.Client(api_key=api_key)
    prompt_calculo = f"""
    Analiza detalladamente esta comida y todos sus ingredientes (incluyendo aderezos, aceites, salsas o mayonesa): "{texto_comida}".
    Calcula y suma con precisión las calorías, proteínas, carbohidratos y grasas de cada ingrediente mencionado.
    En "nombre", coloca el nombre del plato seguido de un resumen breve entre paréntesis de sus ingredientes clave.
    Devuelve ÚNICAMENTE un objeto JSON válido con las estimaciones nutricionales totales, sin texto adicional ni bloques markdown, con este formato exacto:
    {{"nombre": "Nombre del plato (ingredientes clave)", "kcal": 0, "proteina": 0, "carbs": 0, "grasas": 0}}
    Usa solo números enteros.
    """
    resp = client.models.generate_content(
        model="gemini-3.5-flash-lite", contents=prompt_calculo
    )
    texto_limpio = resp.text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(texto_limpio)

def consultar_asistente_stream(pregunta, contexto_macros, api_key, historial_chat=None):
    """Envía la pregunta junto con el historial de la sesión y devuelve un generador en vivo."""
    client = genai.Client(api_key=api_key)

    texto_historial = "Sin mensajes previos en esta sesión."
    if historial_chat:
        lineas = []
        for msg in historial_chat:
            rol = "Usuario" if msg["rol"] == "user" else "Asistente"
            lineas.append(f"{rol}: {msg['texto']}")
        texto_historial = "\n".join(lineas)

    prompt_completo = f"""
    Eres un asistente experto en nutrición deportiva e hipertrofia enfocado en una etapa de 'cutting'.
    Responde de forma directa, práctica y amigable.
    Mantén una conversación fluida y sostenida con el usuario recordando los detalles que te haya mencionado en el historial de esta sesión (evita volver a saludar si ya están conversando).
    
    DATOS ACTUALES DEL USUARIO:
    {contexto_macros}
    
    HISTORIAL DE LA CONVERSACIÓN EN ESTA SESIÓN:
    {texto_historial}
    
    Nueva intervención del usuario: {pregunta}
    """
    respuesta = client.models.generate_content_stream(
        model="gemini-3.5-flash-lite", contents=prompt_completo
    )
    for fragmento in respuesta:
        if fragmento.text:
            yield fragmento.text

def calcular_macros_imagen(imagen_archivo, api_key):
    """Analiza la foto del plato."""
    client = genai.Client(api_key=api_key)
    img = Image.open(imagen_archivo)
    prompt = """
    Analiza detalladamente la comida en esta imagen, incluyendo todos sus componentes, aderezos o salsas visibles.
    En "nombre", coloca el nombre del plato seguido de un resumen breve entre paréntesis de los ingredientes detectados.
    Devuelve ÚNICAMENTE un objeto JSON válido con las estimaciones nutricionales totales, sin texto adicional ni bloques markdown, con este formato exacto:
    {"nombre": "Nombre del plato (ingredientes clave)", "kcal": 0, "proteina": 0, "carbs": 0, "grasas": 0}
    Usa solo números enteros.
    """
    resp = client.models.generate_content(
        model="gemini-3.8-flash", contents=[prompt, img]
    )
    texto_limpio = resp.text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(texto_limpio)

def extraer_datos_perfil(texto_usuario, api_key):
    client = genai.Client(api_key=api_key)
    prompt = f"""
    Extrae el peso (en kg), altura (en cm) y edad (en años) del siguiente texto: "{texto_usuario}".
    Devuelve ÚNICAMENTE un objeto JSON válido, sin texto adicional, con este formato exacto:
    {{"peso": 0.0, "altura": 0.0, "edad": 0}}
    """
    resp = client.models.generate_content(
        model="gemini-3.5-flash-lite", contents=prompt
    )
    texto_limpio = resp.text.strip().replace("```json", "").replace("```", "").strip()
    return json.loads(texto_limpio)
