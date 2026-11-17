import json
from google import genai
from google.genai import types
from PIL import Image

MODELO_IA = "gemini-4-hydrogen"

# Cadena de modelos con cuotas diarias independientes en el Free Tier de Google AI Studio.
# Si el modelo principal presenta 503 (alta demanda) o 429 (límite diario de ese modelo),
# pasa automáticamente al siguiente modelo disponible sin interrumpir al usuario.
CADENA_MODELOS = [
    "gemini-4-hydrogen",
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash",
]

CONFIG_HYDROGEN = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(thinking_level="LOW"),
    temperature=0.2,
)

CONFIG_ESTANDAR = types.GenerateContentConfig(
    temperature=0.2,
)

CONFIG_CHAT_HYDROGEN = types.GenerateContentConfig(
    thinking_config=types.ThinkingConfig(thinking_level="LOW"),
    temperature=0.75,
)

CONFIG_CHAT_ESTANDAR = types.GenerateContentConfig(
    temperature=0.75,
)


def _cliente(api_key):
    """Crea cliente con 1 intento por modelo para saltar de inmediato al siguiente si hay error 429 o 503."""
    return genai.Client(api_key=api_key, http_options={"retry_options": {"attempts": 1}})


def _config_para_modelo(modelo, es_chat=False):
    if es_chat:
        return CONFIG_CHAT_HYDROGEN if "hydrogen" in modelo else CONFIG_CHAT_ESTANDAR
    return CONFIG_HYDROGEN if "hydrogen" in modelo else CONFIG_ESTANDAR


def _generar(api_key, contents):
    """Recorre la cadena de modelos hasta obtener respuesta, evitando bloqueos por cuota (429) o demanda (503)."""
    client = _cliente(api_key)
    ultimo_error = None
    for modelo in CADENA_MODELOS:
        try:
            resp = client.models.generate_content(
                model=modelo,
                contents=contents,
                config=_config_para_modelo(modelo)
            )
            if resp and resp.text:
                return resp.text
        except Exception as e:
            ultimo_error = e
            continue
    raise ultimo_error


def _limpiar_json(texto):
    """Limpia bloques markdown y extrae el objeto JSON válido."""
    limpio = texto.strip().replace("```json", "").replace("```", "").strip()
    inicio = limpio.find("{")
    fin = limpio.rfind("}")
    if inicio != -1 and fin != -1 and fin > inicio:
        limpio = limpio[inicio:fin + 1]
    return json.loads(limpio)


def calcular_macros_texto(texto_comida, api_key):
    """Analiza una comida descrita en texto con Gemini Hydrogen (y rotación automática de cuota)."""
    prompt_calculo = f"""
    Analiza esta comida y todos sus ingredientes (incluyendo cocción, aceites, salsas o aderezos): "{texto_comida}".
    Calcula calorías, proteínas, carbohidratos y grasas totales coherentes entre sí (4 kcal/g P, 4 kcal/g C, 9 kcal/g G).
    En "nombre", escribe el nombre del plato seguido de un resumen breve entre paréntesis de los ingredientes clave.
    Devuelve ÚNICAMENTE un objeto JSON válido con números enteros, sin texto adicional:
    {{"nombre": "Nombre del plato (ingredientes clave)", "kcal": 0, "proteina": 0, "carbs": 0, "grasas": 0}}
    """
    return _limpiar_json(_generar(api_key, prompt_calculo))


def consultar_asistente_stream(pregunta, contexto_macros, api_key, historial_chat=None):
    """Envía la consulta junto con el contexto completo y el historial de la sesión actual."""
    client = _cliente(api_key)

    texto_historial = "Sin mensajes previos en esta sesión."
    if historial_chat:
        lineas = []
        for msg in historial_chat[-8:]:
            rol = "Usuario" if msg["rol"] == "user" else "Asistente"
            lineas.append(f"{rol}: {msg['texto']}")
        texto_historial = "\n".join(lineas)

    prompt_completo = f"""
    Eres el coach y compa de confianza del usuario en nutrición deportiva, gimnasio y estilo de vida fitness (definición/cutting, mantenimiento o volumen/hipertrofia, además de ayuno intermitente).

    Tu personalidad y estilo:
    - Tienes muchísimo carisma, buena vibra y hablas de forma cercana, natural y motivadora (como un entrenador personal joven y apasionado que celebra tus avances y te impulsa sin juzgarte).
    - Nada de sonar como un robot o una enciclopedia médica: usa un tono conversacional, fresco, con chispa y emojis bien puestos (🔥, 💪, 🥩, 🙌).
    - Ve al grano con consejos súper prácticos y realistas: si sugiere comidas, da ideas ricas y fáciles de preparar con sus gramos y macros aproximados para cuadrar lo que le falta hoy.
    - Toma muy en cuenta lo que ya comió hoy, si entrenó, sus macros restantes y si está en ayuno.
    - Mantén el hilo de la charla como una conversación real entre amigos (no vuelvas a decir "¡Hola!" en cada mensaje si ya venían hablando en el historial).

    DATOS ACTUALES DEL USUARIO HOY:
    {contexto_macros}

    HISTORIAL DE LA CONVERSACIÓN EN ESTA SESIÓN:
    {texto_historial}

    Usuario: {pregunta}
    """
    ultimo_error = None
    for modelo in CADENA_MODELOS:
        try:
            respuesta = client.models.generate_content_stream(
                model=modelo,
                contents=prompt_completo,
                config=_config_para_modelo(modelo, es_chat=True)
            )
            for fragmento in respuesta:
                if fragmento.text:
                    yield fragmento.text
            return
        except Exception as e:
            ultimo_error = e
            continue
    if ultimo_error:
        raise ultimo_error


def calcular_macros_imagen(imagen_archivo, api_key):
    """Analiza visualmente la foto de un plato o etiqueta nutricional con Gemini Hydrogen."""
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
    return _limpiar_json(_generar(api_key, [prompt, img]))


def extraer_datos_perfil(texto_usuario, api_key):
    """Extrae peso (kg), altura (cm) y edad (años) del texto del usuario."""
    prompt = f"""
    Extrae el peso (en kg; si está en lb divídelo entre 2.2046), la altura (en cm; ej. 1.75m -> 175) y la edad (en años) de: "{texto_usuario}".
    Devuelve ÚNICAMENTE un objeto JSON válido, sin texto adicional:
    {{"peso": 0.0, "altura": 0.0, "edad": 0}}
    """
    return _limpiar_json(_generar(api_key, prompt))


def calcular_gasto_ejercicio(texto_ejercicio, peso_kg, api_key):
    """Estima las calorías activas quemadas y la duración en minutos según el entrenamiento y el peso del usuario."""
    prompt = f"""
    El usuario pesa {peso_kg} kg y realizó: "{texto_ejercicio}".
    Calcula la duración total en minutos y las calorías activas quemadas (kcal) usando valores MET reales para {peso_kg} kg.
    Devuelve ÚNICAMENTE un objeto JSON válido con números enteros, sin texto adicional:
    {{"nombre": "Resumen corto del entrenamiento", "duracion_min": 0, "kcal_quemadas": 0}}
    """
    return _limpiar_json(_generar(api_key, prompt))
