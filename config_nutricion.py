from datetime import datetime, timezone, timedelta

ZONA_HORARIA = timezone(timedelta(hours=-5))
MAX_INTENTOS_LOGIN = 5
SEGUNDOS_BLOQUEO = 60

OBJETIVOS_CONFIG = {
    "🔥 Definición moderada (-400 kcal)": {"ajuste_kcal": -400, "prot_kg": 2.2, "grasas_kg": 0.9},
    "⚡ Definición agresiva (-600 kcal)": {"ajuste_kcal": -600, "prot_kg": 2.3, "grasas_kg": 0.85},
    "⚖️ Mantenimiento / Recomposición (0 kcal)": {"ajuste_kcal": 0, "prot_kg": 2.0, "grasas_kg": 1.0},
    "💪 Volumen limpio / Hipertrofia (+300 kcal)": {"ajuste_kcal": 300, "prot_kg": 1.9, "grasas_kg": 1.0},
    "🚀 Volumen clásico (+500 kcal)": {"ajuste_kcal": 500, "prot_kg": 1.8, "grasas_kg": 1.0},
}

NIVELES_ACTIVIDAD = {
    "🛋️ Sedentario (Poco o nada de ejercicio)": 1.2,
    "🚶 Ligero (1 a 3 días de entreno/semana)": 1.375,
    "🏋️ Moderado (3 a 5 días de entreno/semana)": 1.55,
    "🔥 Intenso (6 a 7 días de entreno/semana)": 1.725,
}

PREGUNTAS_SEGURIDAD = [
    "¿Cuál era el nombre de tu primera mascota?",
    "¿En qué ciudad o barrio creciste?",
    "¿Cuál era el apodo de tu infancia?",
    "¿Cuál fue el nombre de tu primera escuela o colegio?",
    "¿Cuál era el nombre de tu mejor amigo/a de la infancia?",
    "¿Cuál es el segundo nombre de tu madre?",
    "¿Cuál es el segundo nombre de tu padre?",
    "¿En qué ciudad se conocieron tus padres?",
    "¿Cuál fue tu primer videojuego favorito?",
    "¿Cuál es tu película o serie favorita de todos los tiempos?",
    "¿Cuál es tu personaje ficticio o de anime favorito?",
    "¿Cuál es tu comida trampa (cheat meal) favorita?",
    "¿Cuál es tu postre favorito?",
    "¿Cuál fue el primer concierto o evento al que asististe?",
    "¿Cuál es la marca o modelo de tu primer auto o moto?",
    "¿Cuál es el nombre de tu profesor/a favorito/a del colegio?",
    "¿A qué lugar o país hiciste tu viaje más memorable?",
    "¿Cuál es tu equipo deportivo o atleta favorito?",
    "¿Cuál es tu ejercicio favorito en el gimnasio?",
    "¿Cuál es tu canción o banda musical favorita?",
    "¿Cómo se llamaba la calle donde vivías de niño/a?",
    "¿Cuál fue tu primer trabajo?",
    "¿En qué hospital o clínica naciste?",
    "¿Cuál es el nombre de tu abuelo/a materno/a?",
    "✍️ Escribir mi propia pregunta personalizada..."
]


def fecha_hoy():
    return datetime.now(ZONA_HORARIA).date()


def ahora_local():
    return datetime.now(ZONA_HORARIA)


def normalizar_altura_cm(altura_val):
    return float(altura_val) * 100.0 if float(altura_val) < 3.0 else float(altura_val)


def calcular_mantenimiento_base(peso_kg, altura_val, edad_val, factor_act=1.55):
    altura_cm = normalizar_altura_cm(altura_val)
    tmb = (10.0 * float(peso_kg)) + (6.25 * altura_cm) - (5.0 * int(edad_val)) + 5.0
    return int(tmb * factor_act), round(altura_cm, 1)


def calcular_macros_objetivo(peso_kg, altura_val, edad_val, objetivo_key, actividad_key):
    """Calcula calorías y macronutrientes ideales según Mifflin-St Jeor, objetivo y actividad."""
    factor_act = NIVELES_ACTIVIDAD.get(actividad_key, 1.55)
    mantenimiento, altura_cm = calcular_mantenimiento_base(peso_kg, altura_val, edad_val, factor_act)
    peso_f = float(peso_kg)

    cfg = OBJETIVOS_CONFIG.get(objetivo_key, OBJETIVOS_CONFIG["🔥 Definición moderada (-400 kcal)"])
    meta_kcal = max(mantenimiento + cfg["ajuste_kcal"], 1200)
    meta_prot = int(peso_f * cfg["prot_kg"])
    meta_grasas = int(peso_f * cfg["grasas_kg"])
    meta_carbs = max(int((meta_kcal - (meta_prot * 4) - (meta_grasas * 9)) / 4), 50)
    return meta_kcal, meta_prot, meta_carbs, meta_grasas, altura_cm


def obtener_fase_ayuno(horas_transcurridas):
    if horas_transcurridas < 4:
        return "🍽️ **Fase 1 (0–4h): Digestión** — Procesando nutrientes de tu última comida."
    if horas_transcurridas < 8:
        return "📉 **Fase 2 (4–8h): Caída de insulina** — Baja la glucosa y empiezas a usar reservas."
    if horas_transcurridas < 12:
        return "🔥 **Fase 3 (8–12h): Quema de glucógeno** — Tu cuerpo empieza a recurrir a la grasa."
    if horas_transcurridas < 16:
        return "⚡ **Fase 4 (12–16h): Lipólisis activa** — Quema de grasa acelerada ideal para definición."
    return "🧬 **Fase 5 (+16h): Autofagia** — Renovación celular y máxima oxidación de grasas."
