import json
from google import genai
from google.genai import types
from PIL import Image

MODELO_IA = "gemini-4-hydrogen"

CONFIG_BAJO_RAZONAMIENTO = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(thinking_level="LOW"),
    temperature=0.2,
)


def _limpiar_json(texto):
    """Limpia bloques markdown y extrae el objeto JSON válido."""
    limpio = texto.strip().replace("```json", "").replace("```", "").strip()
    inicio = limpio.find("{")
    fin = limpio.rfind("}")
    if inicio != -1 and fin != -1 and fin > inicio:
        limpio = limpio[inicio:fin + 1]
    return json.loads(limpio)


def calcular_macros_texto(texto_comida, api_key):
    """Analiza una comida descrita en texto con Gemini Hydrogen en modo de razonamiento bajo."""
    client = genai.Client(api_key=api_key)
    prompt_calculo = f"""
    Analiza esta comida y todos sus ingredientes (incluyendo cocción, aceites, salsas o aderezos): "{texto_comida}".
    Calcula calorías, proteínas, carbohidratos y grasas totales coherentes entre sí (4 kcal/g P, 4 kcal/g C, 9 kcal/g G).
    En "nombre", escribe el nombre del plato seguido de un resumen breve entre paréntesis de los ingredientes clave.
    Devuelve ÚNICAMENTE un objeto JSON válido con números enteros, sin texto adicional:
    {{"nombre": "Nombre del plato (ingredientes clave)", "kcal": 0, "proteina": 0, "carbs": 0, "grasas": 0}}
    """
    resp = client.models.generate_content(
        model=MODELO_IA,
        contents=prompt_calculo,
        config=CONFIG_BAJO_RAZONAMIENTO
    )
    return _limpiar_json(resp.text)


def consultar_asistente_stream(pregunta, contexto_macros, api_key, historial_chat=None):
    """Envía la consulta junto con el contexto completo y el historial de la sesión actual."""
    client = genai.Client(api_key=api_key)

    texto_historial = "Sin mensajes previos en esta sesión."
    if historial_chat:
        lineas = []
        for msg in historial_chat[-8:]:
            rol = "Usuario" if msg["rol"] == "user" else "Asistente"
            lineas.append(f"{rol}: {msg['texto']}")
        texto_historial = "\n".join(lineas)

    prompt_completo = f"""
    Eres un entrenador y nutricionista deportivo experto en composición corporal: definición (cutting), mantenimiento/recomposición, volumen limpio (bulking) y ayuno intermitente.
    - Adapta tus recomendaciones a la etapa actual del usuario, sus comidas registradas, ejercicio del día, macros restantes y estado de ayuno.
    - Sé directo, conciso, práctico y amigable (usa viñetas breves si sugieres alimentos con gramos y macros).
    - Mantén el hilo de la conversación sin volver a saludar si ya hay mensajes previos.

    DATOS ACTUALES DEL USUARIO HOY:
    {contexto_macros}

    HISTORIAL DE ESTA SESIÓN:
    {texto_historial}

    Usuario: {pregunta}
    """
    respuesta = client.models.generate_content_stream(
        model=MODELO_IA,
        contents=prompt_completo,
        config=CONFIG_BAJO_RAZONAMIENTO
    )
    for fragmento in respuesta:
        if fragmento.text:
            yield fragmento.text


def calcular_macros_imagen(imagen_archivo, api_key):
    """Analiza visualmente la foto de un plato o etiqueta nutricional con Gemini Hydrogen (razonamiento bajo)."""
    client = genai.Client(api_key=api_key)
    img = Image.open(imagen_archivo)
    img.thumbnail((1024, 1024))
    prompt = """
    Analiza la comida o etiqueta nutricional en esta imagen:
    - Identifica todos los alimentos visibles y estima sus gramos (incluyendo salsas, aceites o aderezos), o lee los datos si es una tabla nutricional.
    - Verifica coherencia calórica (4 kcal/g P, 4 kcal/g C, 9 kcal/g G).
    - En "nombre", coloca el nombre del plato seguido de los ingredientes detectados entre paréntesis.
    Devuelve ÚNICAMENTE un objeto JSON válido con números enteros, sin texto adicional:
    {"nombre": "Nombre del plato (ingredientes detectados)", "kcal": 0, "proteina": 0, "carbs": 0, "grasas": 0}
    """
    resp = client.models.generate_content(
        model=MODELO_IA,
        contents=[prompt, img],
        config=CONFIG_BAJO_RAZONAMIENTO
    )
    return _limpiar_json(resp.text)


def extraer_datos_perfil(texto_usuario, api_key):
    """Extrae peso (kg), altura (cm) y edad (años) del texto del usuario."""
    client = genai.Client(api_key=api_key)
    prompt = f"""
    Extrae el peso (en kg; si está en lb divídelo entre 2.2046), la altura (en cm; ej. 1.75m -> 175) y la edad (en años) de: "{texto_usuario}".
    Devuelve ÚNICAMENTE un objeto JSON válido, sin texto adicional:
    {{"peso": 0.0, "altura": 0.0, "edad": 0}}
    """
    resp = client.models.generate_content(
        model=MODELO_IA,
        contents=prompt,
        config=CONFIG_BAJO_RAZONAMIENTO
    )
    return _limpiar_json(resp.text)


def calcular_gasto_ejercicio(texto_ejercicio, peso_kg, api_key):
    """Estima las calorías activas quemadas y la duración en minutos según el entrenamiento y el peso del usuario."""
    client = genai.Client(api_key=api_key)
    prompt = f"""
    El usuario pesa {peso_kg} kg y realizó: "{texto_ejercicio}".
    Calcula la duración total en minutos y las calorías activas quemadas (kcal) usando valores MET reales para {peso_kg} kg.
    Devuelve ÚNICAMENTE un objeto JSON válido con números enteros, sin texto adicional:
    {{"nombre": "Resumen corto del entrenamiento", "duracion_min": 0, "kcal_quemadas": 0}}
    """
    resp = client.models.generate_content(
        model=MODELO_IA,
        contents=prompt,
        config=CONFIG_BAJO_RAZONAMIENTO
    )
    return _limpiar_json(resp.text)
