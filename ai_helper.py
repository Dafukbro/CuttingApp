import json
from google import genai
from PIL import Image

MODELO_IA = "gemini-4-hydrogen"


def _limpiar_json(texto):
    """Limpia bloques markdown y extrae el objeto JSON válido."""
    limpio = texto.strip().replace("```json", "").replace("```", "").strip()
    inicio = limpio.find("{")
    fin = limpio.rfind("}")
    if inicio != -1 and fin != -1 and fin > inicio:
        limpio = limpio[inicio:fin + 1]
    return json.loads(limpio)


def calcular_macros_texto(texto_comida, api_key):
    """Analiza una comida descrita en texto y estima sus calorías y macronutrientes con precisión."""
    client = genai.Client(api_key=api_key)
    prompt_calculo = f"""
    Eres un nutricionista deportivo y dietista clínico experto en cuantificación de macronutrientes.
    Analiza detalladamente la siguiente comida y todos sus ingredientes (incluyendo métodos de cocción, aceites, aderezos, salsas, bebidas o acompañamientos): "{texto_comida}".

    Reglas de estimación:
    1. Si el usuario especifica gramos, unidades, latas o cucharadas, calcula los valores exactos según tablas nutricionales estándar (USDA).
    2. Si alguna porción no especifica peso exacto, asume una porción estándar realista.
    3. Asegúrate de que las calorías totales sean coherentes con los macronutrientes (aprox. 4 kcal por gramo de proteína, 4 kcal por gramo de carbohidrato y 9 kcal por gramo de grasa).
    4. En "nombre", escribe el nombre claro del plato seguido de un desglose breve entre paréntesis de los ingredientes principales y sus cantidades.

    Devuelve ÚNICAMENTE un objeto JSON válido, sin texto adicional ni bloques markdown, con este formato exacto:
    {{"nombre": "Nombre del plato (ingredientes clave)", "kcal": 0, "proteina": 0, "carbs": 0, "grasas": 0}}
    Usa solo números enteros.
    """
    resp = client.models.generate_content(
        model=MODELO_IA, contents=prompt_calculo
    )
    return _limpiar_json(resp.text)


def consultar_asistente_stream(pregunta, contexto_macros, api_key, historial_chat=None):
    """Envía la consulta junto con el contexto completo y el historial de la sesión actual."""
    client = genai.Client(api_key=api_key)

    texto_historial = "Sin mensajes previos en esta sesión."
    if historial_chat:
        lineas = []
        for msg in historial_chat:
            rol = "Usuario" if msg["rol"] == "user" else "Asistente"
            lineas.append(f"{rol}: {msg['texto']}")
        texto_historial = "\n".join(lineas)

    prompt_completo = f"""
    Eres un entrenador y nutricionista deportivo experto en composición corporal, hipertrofia, pérdida de grasa (cutting), mantenimiento/recomposición corporal, volumen limpio (bulking) y ayuno intermitente.

    Directrices de respuesta:
    - Adapta tus consejos al objetivo específico del usuario según sus metas calóricas y de macronutrientes actuales (ya sea que esté en déficit calórico/definición, mantenimiento o superávit/volumen).
    - Toma en cuenta las comidas que ya registró hoy, las calorías que quemó con su ejercicio, los macros que le restan en el día y si se encuentra en ayuno intermitente.
    - Responde de forma directa, práctica, motivadora y bien estructurada (usa viñetas cuando sugieras opciones de comidas o alimentos con sus gramos y macros aproximados).
    - Mantén una conversación natural y continua recordando lo hablado en esta sesión (evita volver a saludar si ya hay mensajes previos en el historial).

    DATOS ACTUALES DEL USUARIO HOY:
    {contexto_macros}

    HISTORIAL DE LA CONVERSACIÓN EN ESTA SESIÓN:
    {texto_historial}

    Nueva intervención del usuario: {pregunta}
    """
    respuesta = client.models.generate_content_stream(
        model=MODELO_IA, contents=prompt_completo
    )
    for fragmento in respuesta:
        if fragmento.text:
            yield fragmento.text


def calcular_macros_imagen(imagen_archivo, api_key):
    """Analiza visualmente la foto de un plato o etiqueta nutricional con Gemini Hydrogen."""
    client = genai.Client(api_key=api_key)
    img = Image.open(imagen_archivo)
    prompt = """
    Eres un nutricionista deportivo experto en estimación visual de porciones y lectura de etiquetas nutricionales.
    Analiza detalladamente la comida o producto que aparece en esta imagen:
    - Identifica todos los alimentos visibles, estimando su peso aproximado en gramos según el tamaño del plato, grosor y volumen, incluyendo salsas, aderezos o aceites de cocción.
    - Si la imagen muestra una tabla o etiqueta nutricional, extrae los valores exactos de la porción mostrada.
    - Verifica que las calorías totales sean coherentes con la suma de proteínas (4 kcal/g), carbohidratos (4 kcal/g) y grasas (9 kcal/g).
    - En "nombre", escribe el nombre del plato seguido de un resumen breve entre paréntesis de los ingredientes y porciones detectadas.

    Devuelve ÚNICAMENTE un objeto JSON válido, sin texto adicional ni bloques markdown, con este formato exacto:
    {"nombre": "Nombre del plato (ingredientes detectados)", "kcal": 0, "proteina": 0, "carbs": 0, "grasas": 0}
    Usa solo números enteros.
    """
    resp = client.models.generate_content(
        model=MODELO_IA, contents=[prompt, img]
    )
    return _limpiar_json(resp.text)


def extraer_datos_perfil(texto_usuario, api_key):
    """Extrae peso (kg), altura (cm) y edad (años) a partir de la descripción en lenguaje natural del usuario."""
    client = genai.Client(api_key=api_key)
    prompt = f"""
    Extrae el peso (en kg), la altura (convertida siempre a centímetros, ej. 1.75m -> 175) y la edad (en años) del siguiente texto del usuario: "{texto_usuario}".
    Si el usuario menciona su peso en libras (lb), conviértelo a kilogramos (dividiendo entre 2.2046).
    Devuelve ÚNICAMENTE un objeto JSON válido, sin texto adicional ni bloques markdown, con este formato exacto:
    {{"peso": 0.0, "altura": 0.0, "edad": 0}}
    """
    resp = client.models.generate_content(
        model=MODELO_IA, contents=prompt
    )
    return _limpiar_json(resp.text)


def calcular_gasto_ejercicio(texto_ejercicio, peso_kg, api_key):
    """Estima las calorías activas quemadas y la duración en minutos según el entrenamiento y el peso del usuario."""
    client = genai.Client(api_key=api_key)
    prompt = f"""
    Eres un fisiólogo del ejercicio experto. El usuario pesa {peso_kg} kg y realizó la siguiente actividad física, deporte o sesión de entrenamiento: "{texto_ejercicio}".
    - Calcula de forma realista el gasto calórico activo (kcal quemadas) utilizando valores MET (Equivalentes Metabólicos) reales según la intensidad de cada ejercicio, la duración y el peso corporal del usuario ({peso_kg} kg).
    - Si el usuario combinó pesas y cardio (ej. "45 min de pesas y 20 min de caminadora"), suma la duración total y el gasto calórico de ambas actividades.
    - Si no especificó la duración exacta, asume una sesión estándar de 45 minutos.

    Devuelve ÚNICAMENTE un objeto JSON válido, sin texto adicional ni bloques markdown, con este formato exacto:
    {{"nombre": "Resumen claro del entrenamiento", "duracion_min": 0, "kcal_quemadas": 0}}
    Usa solo números enteros.
    """
    resp = client.models.generate_content(
        model=MODELO_IA, contents=prompt
    )
    return _limpiar_json(resp.text)
