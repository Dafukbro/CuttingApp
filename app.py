from datetime import datetime, timezone, timedelta
import importlib
import streamlit as st
import database as db
import ai_helper as ai

if not hasattr(db, "_hash_password"):
    importlib.reload(db)

ZONA_HORARIA = timezone(timedelta(hours=-5))

def fecha_hoy():
    return datetime.now(ZONA_HORARIA).date()

def ahora_local():
    return datetime.now(ZONA_HORARIA)

st.set_page_config(page_title="Tracker Cutting", page_icon="🔥", layout="centered")
db.init_db(2)

API_KEY = st.secrets["API_KEY"]

# --- GESTIÓN DE SESIÓN Y PANTALLA DE LOGIN ---
if "usuario" not in st.session_state:
    st.session_state.usuario = None

if not st.session_state.usuario:
    st.title("🔐 Acceso a Cutting Tracker")
    tab_login, tab_registro = st.tabs(["Iniciar Sesión", "Registrarse"])

    with tab_login:
        user_login = st.text_input("Usuario", key="login_user").strip()
        pass_login = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Entrar", use_container_width=True):
            if user_login and pass_login:
                if db.verificar_usuario(user_login, pass_login):
                    st.session_state.clear()
                    st.session_state.usuario = user_login
                    st.session_state.mensajes = []
                    st.success(f"¡Bienvenido, {user_login}!")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")
            else:
                st.warning("Completa todos los campos.")

    with tab_registro:
        user_reg = st.text_input("Nuevo Usuario", key="reg_user").strip()
        pass_reg = st.text_input("Nueva Contraseña", type="password", key="reg_pass")
        if st.button("Crear Cuenta", use_container_width=True):
            if user_reg and pass_reg:
                if db.crear_usuario(user_reg, pass_reg):
                    st.success("¡Cuenta creada con éxito! Ahora puedes iniciar sesión.")
                else:
                    st.error("Ese nombre de usuario ya existe.")
            else:
                st.warning("Completa todos los campos.")
    st.stop()

usuario = st.session_state.usuario
datos_perfil = db.obtener_perfil(usuario)

if not datos_perfil:
    st.title(f"👋 Bienvenido, {usuario}")
    st.write("Cuéntame sobre ti para configurar tus metas automáticamente.")
    descripcion_usuario = st.text_area(
        "¿Cuál es tu peso, altura y edad?",
        placeholder="Ej. Tengo 21 años, mido 1.75m y peso 75 kilos.",
        key=f"desc_inicial_{usuario}"
    )
    
    if st.button("✨ Generar mi plan", use_container_width=True):
        if descripcion_usuario:
            with st.spinner("Calculando macros ideales..."):
                try:
                    datos = ai.extraer_datos_perfil(descripcion_usuario, API_KEY)
                    p_val, a_val, e_val = float(datos["peso"]), float(datos["altura"]), int(datos["edad"])
                    
                    tmb = (10 * p_val) + (6.25 * a_val) - (5 * e_val) + 5
                    mantenimiento = int(tmb * 1.55)
                    meta_kcal = mantenimiento - 400
                    meta_prot = int(p_val * 2.2)
                    meta_grasas = int(p_val * 0.9)
                    meta_carbs = int((meta_kcal - (meta_prot * 4) - (meta_grasas * 9)) / 4)
                    
                    db.crear_perfil(usuario, p_val, a_val, e_val, meta_kcal, meta_prot, meta_carbs, meta_grasas)
                    db.registrar_peso_diario(usuario, fecha_hoy(), p_val)
                    st.success("¡Perfil creado!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()
    st.stop()

else:
    peso, altura, edad, meta_kcal, meta_prot, meta_carbs, meta_grasas = datos_perfil
    
    col_titulo, col_salir = st.columns([4, 1])
    with col_titulo:
        st.title("🔥 Cutting Tracker")
        st.caption(f"👤 Sesión activa: **{usuario}**")
    with col_salir:
        if st.button("Salir 🚪", use_container_width=True):
            st.session_state.clear()
            st.rerun()
    
    # Navegación principal estilo app móvil
    tab_dash, tab_reg, tab_ayuno, tab_ia, tab_perfil = st.tabs(["🏠 Resumen", "➕ Registro", "⏳ Ayuno", "🤖 Chat IA", "⚙️ Perfil"])

    # --- PESTAÑA 1: RESUMEN DEL DÍA (Visibilidad del estado del sistema) ---
    with tab_dash:
        fecha_activa = st.date_input("📅 Fecha", value=fecha_hoy(), key=f"fecha_{usuario}")
        comidas_hoy = db.obtener_comidas_por_fecha(usuario, fecha_activa)

        kcal_hoy = sum(x[2] for x in comidas_hoy)
        prot_hoy = sum(x[3] for x in comidas_hoy)
        carbs_hoy = sum(x[4] for x in comidas_hoy)
        grasas_hoy = sum(x[5] for x in comidas_hoy)
        kcal_restantes = meta_kcal - kcal_hoy
        prot_restante = meta_prot - prot_hoy
        carbs_restantes = meta_carbs - carbs_hoy
        grasas_restantes = meta_grasas - grasas_hoy

        with st.container(border=True):
            st.markdown(f"🔥 **Calorías del día:** {kcal_hoy} / {meta_kcal} kcal ({int(min(kcal_hoy / max(meta_kcal, 1), 1.0) * 100)}%)")
            st.progress(min(kcal_hoy / max(meta_kcal, 1), 1.0))

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Kcal Restantes", f"{kcal_restantes}", delta="En meta" if kcal_restantes >= 0 else f"Exceso ({abs(kcal_restantes)})", delta_color="normal" if kcal_restantes >= 0 else "inverse")
            with col2:
                st.metric("🥩 Proteína", f"{prot_hoy}g / {meta_prot}g", f"Faltan {max(prot_restante, 0)}g" if prot_restante > 0 else "¡Meta lograda!")
                st.progress(min(prot_hoy / max(meta_prot, 1), 1.0))
            with col3:
                st.metric("🍚 Carbs", f"{carbs_hoy}g / {meta_carbs}g", f"Restan {carbs_restantes}g" if carbs_restantes >= 0 else f"+{abs(carbs_restantes)}g")
                st.progress(min(carbs_hoy / max(meta_carbs, 1), 1.0))
            with col4:
                st.metric("🥑 Grasas", f"{grasas_hoy}g / {meta_grasas}g", f"Restan {grasas_restantes}g" if grasas_restantes >= 0 else f"+{abs(grasas_restantes)}g")
                st.progress(min(grasas_hoy / max(meta_grasas, 1), 1.0))
        
        st.divider()
        st.subheader("📋 Consumido hoy")
        if not comidas_hoy:
            st.info("No has registrado comidas aún.")
        else:
            for id_c, nom, k, p, c, g in comidas_hoy:
                with st.container(border=True):
                    col_t, col_b = st.columns([5, 1])
                    with col_t:
                        st.markdown(f"**{nom}**")
                        st.caption(f"🔥 **{k} kcal** ｜ 🥩 **{p}g** Prot ｜ 🍚 **{c}g** Carbs ｜ 🥑 **{g}g** Grasas")
                    with col_b:
                        if st.button("🗑️", key=f"del_{usuario}_{id_c}"):
                            db.eliminar_comida(id_c)
                            st.rerun()

        st.divider()
        st.subheader("⚖️ Evolución de Peso")
        col_p1, col_p2 = st.columns([2, 1])
        peso_hoy_input = col_p1.number_input("Peso (kg)", value=float(peso), step=0.1, key=f"peso_diario_{usuario}")
        if col_p2.button("Guardar", key=f"btn_peso_{usuario}"):
            db.registrar_peso_diario(usuario, fecha_activa, peso_hoy_input)
            st.rerun()
        historial = db.obtener_historial_peso(usuario)
        if historial:
            st.line_chart({fila[0]: fila[1] for fila in historial[-14:]}) # Últimos 14 días para no saturar

    # --- PESTAÑA 2: REGISTRO (Prevención de errores y flexibilidad) ---
    with tab_reg:
        st.subheader("📸 Escáner Visual")
        foto_plato = st.file_uploader("Toma o sube una foto", type=["jpg", "jpeg", "png"], key=f"foto_{usuario}")
        if foto_plato and st.button("Analizar foto", use_container_width=True, key=f"btn_foto_{usuario}"):
            with st.spinner("Analizando..."):
                try:
                    datos = ai.calcular_macros_imagen(foto_plato, API_KEY)
                    db.agregar_comida(usuario, fecha_activa, datos["nombre"], datos["kcal"], datos["proteina"], datos["carbs"], datos["grasas"])
                    st.success(f"Guardado: {datos['nombre']}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Fallo en servidor de IA, intenta más tarde. Detalle: {e}")

        st.divider()
        st.subheader("✍️ Registro por Texto")
        comida_ia = st.text_input("¿Qué comiste?", placeholder="Ej. 200g pollo y arroz", key=f"comida_txt_{usuario}")
        if st.button("Calcular macros", use_container_width=True, key=f"btn_txt_{usuario}") and comida_ia:
            with st.spinner("Calculando..."):
                try:
                    datos = ai.calcular_macros_texto(comida_ia, API_KEY)
                    db.agregar_comida(usuario, fecha_activa, datos["nombre"], datos["kcal"], datos["proteina"], datos["carbs"], datos["grasas"])
                    st.success("Guardado correctamente.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # --- PESTAÑA 3: AYUNO INTERMITENTE (Heurísticas: Visibilidad, Mundo Real, Control y Prevención de Errores) ---
    with tab_ayuno:
        st.subheader("⏳ Ayuno Intermitente")
        datos_ayuno = db.obtener_ayuno(usuario)
        ayuno_activo = bool(datos_ayuno and datos_ayuno[2] == 1)

        if not ayuno_activo:
            st.caption("🟢 **Estado actual:** En ventana de alimentación (sin ayuno activo)")

            with st.container(border=True):
                st.markdown("#### 1. Elige tu protocolo")
                protocolos = {
                    "⭐ 16:8 — Estándar (16h ayuno / 8h comida)": 16,
                    "🌱 14:10 — Principiante (14h ayuno / 10h comida)": 14,
                    "🔥 18:6 — Avanzado (18h ayuno / 6h comida)": 18,
                    "⚡ 20:4 — Guerrero (20h ayuno / 4h comida)": 20,
                    "⚙️ Personalizado": 0
                }
                seleccion = st.selectbox("Protocolo de ayuno", list(protocolos.keys()), key=f"prot_ayuno_{usuario}")
                if seleccion == "⚙️ Personalizado":
                    horas_obj = st.slider("Horas de ayuno objetivo", min_value=12, max_value=36, value=16, key=f"slider_ayuno_{usuario}")
                else:
                    horas_obj = protocolos[seleccion]

                st.markdown("#### 2. ¿Cuándo terminaste tu última comida?")
                modo_inicio = st.radio(
                    "Momento de inicio",
                    ["Empezar ahora mismo", "Elegir la hora de mi última comida"],
                    horizontal=True,
                    label_visibility="collapsed",
                    key=f"modo_inicio_ayuno_{usuario}"
                )

                ahora_dt = ahora_local()
                if modo_inicio == "Empezar ahora mismo":
                    inicio_previsto = ahora_dt
                else:
                    hora_elegida = st.time_input(
                        "Hora de tu última comida",
                        value=ahora_dt.replace(minute=0, second=0, microsecond=0).time(),
                        key=f"hora_comida_ayuno_{usuario}"
                    )
                    inicio_previsto = ahora_dt.replace(
                        hour=hora_elegida.hour, minute=hora_elegida.minute, second=0, microsecond=0
                    )
                    # Si la hora elegida es mayor a la hora actual, asumimos que fue anoche
                    if inicio_previsto > ahora_dt:
                        inicio_previsto -= timedelta(days=1)

                fin_previsto = inicio_previsto + timedelta(hours=horas_obj)
                etiqueta_dia = "hoy" if fin_previsto.date() == ahora_dt.date() else "mañana"

                st.info(
                    f"🎯 **Vista previa:** Tu ayuno de **{horas_obj}h** cuenta desde las **{inicio_previsto.strftime('%I:%M %p')}** "
                    f"y podrás volver a comer **{etiqueta_dia} a las {fin_previsto.strftime('%I:%M %p')}**."
                )

                if st.button("▶️ Iniciar Ayuno", type="primary", use_container_width=True, key=f"btn_iniciar_ayuno_{usuario}"):
                    db.iniciar_ayuno(usuario, inicio_previsto.isoformat(), horas_obj)
                    st.rerun()
        else:
            inicio_iso, horas_meta, _ = datos_ayuno
            inicio_dt = datetime.fromisoformat(inicio_iso)
            if inicio_dt.tzinfo is None:
                inicio_dt = inicio_dt.replace(tzinfo=ZONA_HORARIA)
            fin_dt = inicio_dt + timedelta(hours=horas_meta)
            ahora_dt = ahora_local()

            segundos_transcurridos = max((ahora_dt - inicio_dt).total_seconds(), 0)
            horas_transcurridas = segundos_transcurridos / 3600.0
            segundos_meta = horas_meta * 3600.0
            progreso = min(segundos_transcurridos / max(segundos_meta, 1), 1.0)
            porcentaje = int(progreso * 100)

            h_trans = int(segundos_transcurridos // 3600)
            m_trans = int((segundos_transcurridos % 3600) // 60)

            segundos_restantes = max(segundos_meta - segundos_transcurridos, 0)
            h_rest = int(segundos_restantes // 3600)
            m_rest = int((segundos_restantes % 3600) // 60)

            with st.container(border=True):
                st.markdown(f"🔥 **Ayuno {horas_meta}:{max(24 - horas_meta, 0)} en curso** — **{porcentaje}% completado**")
                st.progress(progreso)

                col_a1, col_a2, col_a3 = st.columns(3)
                col_a1.metric("Tiempo en Ayuno", f"{h_trans}h {m_trans}m", f"Meta: {horas_meta}h")
                col_a2.metric(
                    "Tiempo Restante",
                    f"{h_rest}h {m_rest}m" if segundos_restantes > 0 else "¡Meta lograda! 🎉",
                    delta="En curso" if segundos_restantes > 0 else "Completado"
                )
                col_a3.metric("Hora para comer", fin_dt.strftime("%I:%M %p"), f"Inicio: {inicio_dt.strftime('%I:%M %p')}")

                # Etapa metabólica actual
                if horas_transcurridas < 4:
                    etapa = "🍽️ **Fase 1 (0–4h): Digestión** — Procesando nutrientes de tu última comida."
                elif horas_transcurridas < 8:
                    etapa = "📉 **Fase 2 (4–8h): Caída de insulina** — Baja la glucosa y empiezas a usar reservas."
                elif horas_transcurridas < 12:
                    etapa = "🔥 **Fase 3 (8–12h): Quema de glucógeno** — Tu cuerpo empieza a recurrir a la grasa."
                elif horas_transcurridas < 16:
                    etapa = "⚡ **Fase 4 (12–16h): Lipólisis activa** — Quema de grasa acelerada ideal para definición."
                else:
                    etapa = "🧬 **Fase 5 (+16h): Autofagia** — Renovación celular y máxima oxidación de grasas."

                st.info(etapa)

                col_btn1, col_btn2 = st.columns(2)
                if col_btn1.button("🔄 Actualizar tiempo", use_container_width=True, key=f"btn_ref_ayuno_{usuario}"):
                    st.rerun()
                if col_btn2.button("✅ Terminar y Guardar", type="primary", use_container_width=True, key=f"btn_fin_ayuno_{usuario}"):
                    protocolo_str = f"{horas_meta}:{max(24 - horas_meta, 0)}"
                    db.detener_ayuno(usuario, fecha_hoy(), protocolo_str, horas_transcurridas, horas_meta)
                    st.success(f"¡Ayuno guardado! Completaste {h_trans}h {m_trans}m.")
                    st.rerun()

                with st.expander("⚙️ Opciones adicionales (Corregir o cancelar ayuno)"):
                    st.caption("Si iniciaste el ayuno por error, puedes descartarlo sin que afecte tu historial.")
                    if st.button("🗑️ Descartar ayuno actual sin guardar", use_container_width=True, key=f"btn_cancel_ayuno_{usuario}"):
                        db.cancelar_ayuno(usuario)
                        st.rerun()

        with st.expander("ℹ️ Guía rápida: ¿Qué puedo consumir durante el ayuno?"):
            st.markdown(
                "- ✅ **Permitido (0 kcal):** Agua natural o con gas, café negro sin azúcar, té o infusiones sin endulzar, sal/electrolitos.\n"
                "- ❌ **Rompe el ayuno:** Azúcar, leche, crema, aceite, caldos con grasa, proteína en polvo o snacks."
            )

        st.divider()
        st.subheader("📜 Historial de Ayunos")
        hist_ayunos = db.obtener_historial_ayunos(usuario)
        if not hist_ayunos:
            st.info("Aún no tienes ayunos completados registrados.")
        else:
            for id_ay, f_ay, prot_ay, h_comp, h_m in hist_ayunos:
                cumplido = "✅ Meta cumplida" if h_comp >= h_m else "⚠️ Parcial"
                with st.container(border=True):
                    col_h1, col_h2 = st.columns([5, 1])
                    with col_h1:
                        st.markdown(f"📅 **{f_ay}** — Protocolo **{prot_ay}** ({cumplido})")
                        st.caption(f"⏱️ Duración completada: **{h_comp:.1f} horas** de {h_m}h objetivo")
                    with col_h2:
                        if st.button("🗑️", key=f"del_ayuno_{usuario}_{id_ay}"):
                            db.eliminar_historial_ayuno(id_ay)
                            st.rerun()

    # --- PESTAÑA 4: CHAT IA ---
    with tab_ia:
        if "mensajes" not in st.session_state:
            st.session_state.mensajes = []

        # Botones de preguntas rápidas para usar con 1 toque desde el celular
        st.caption("⚡ **Consultas rápidas:**")
        col_q1, col_q2, col_q3, col_q4 = st.columns([2, 2, 2, 1])
        pregunta_rapida = None
        if col_q1.button("🍽️ ¿Qué como con mis macros restantes?", use_container_width=True, key=f"q1_{usuario}"):
            pregunta_rapida = "¿Qué opciones de comida me recomiendas para cuadrar exactamente las calorías y macros que me faltan hoy?"
        if col_q2.button("🥩 ¿Cómo llego a mi proteína hoy?", use_container_width=True, key=f"q2_{usuario}"):
            pregunta_rapida = "¿Qué alimentos bajos en calorías puedo agregar hoy para completar mi meta de proteína sin pasarme de grasas ni carbohidratos?"
        if col_q3.button("📊 Evalúa mi día de hoy", use_container_width=True, key=f"q3_{usuario}"):
            pregunta_rapida = "Evalúa cómo van mis calorías, macronutrientes y ayuno de hoy y dame un consejo práctico."
        if col_q4.button("🧹 Limpiar", use_container_width=True, key=f"q_clear_{usuario}"):
            st.session_state.mensajes = []
            st.rerun()

        contenedor_chat = st.container(height=420)

        with contenedor_chat:
            if not st.session_state.mensajes:
                st.info(f"👋 ¡Hola, {usuario}! Toca uno de los botones rápidos de arriba o escribe tu consulta abajo.")
            for msg in st.session_state.mensajes:
                with st.chat_message(msg["rol"]):
                    st.markdown(msg["texto"])

        pregunta_input = st.chat_input("Consulta sobre tu dieta...", key=f"chat_input_{usuario}")
        pregunta = pregunta_rapida or pregunta_input

        if pregunta:
            st.session_state.mensajes.append({"rol": "user", "texto": pregunta})
            with contenedor_chat:
                with st.chat_message("user"):
                    st.markdown(pregunta)
                
                lista_comidas_str = ", ".join([f"{nom} ({k} kcal, {p}g P, {c}g C, {g}g G)" for _, nom, k, p, c, g in comidas_hoy]) if comidas_hoy else "Ninguna hoy."
                estado_ayuno_str = "No está en ayuno actualmente."
                if ayuno_activo:
                    estado_ayuno_str = f"En ayuno activo ({h_trans}h {m_trans}m completadas de una meta de {horas_meta}h)."
                contexto = (
                    f"Usuario: {usuario}. Perfil: {peso}kg. "
                    f"Metas diarias: {meta_kcal}kcal, {meta_prot}g P, {meta_carbs}g C, {meta_grasas}g G. "
                    f"Lleva hoy: {kcal_hoy}kcal, {prot_hoy}g P, {carbs_hoy}g C, {grasas_hoy}g G. "
                    f"Ayuno intermitente: {estado_ayuno_str} "
                    f"Comió: {lista_comidas_str}."
                )
                
                with st.chat_message("assistant"):
                    try:
                        historial_previo = st.session_state.mensajes[:-1]
                        generador_ia = ai.consultar_asistente_stream(pregunta, contexto, API_KEY, historial_previo)
                        caja_texto = st.empty()
                        texto_ia = ""
                        for pedazo in generador_ia:
                            texto_ia += pedazo
                            caja_texto.markdown(texto_ia + "▌")  
                        caja_texto.markdown(texto_ia)
                        st.session_state.mensajes.append({"rol": "assistant", "texto": texto_ia})
                    except Exception as e:
                        st.error(f"Error: {e}")

    # --- PESTAÑA 4: PERFIL (Flexibilidad y eficiencia) ---
    with tab_perfil:
        st.subheader(f"Configuración Física de {usuario}")
        nuevo_peso = st.number_input("Peso actual (kg)", value=float(peso), key=f"perfil_peso_{usuario}")
        nueva_kcal = st.number_input("Kcal Objetivo", value=int(meta_kcal), step=50, key=f"perfil_kcal_{usuario}")
        nueva_prot = st.number_input("Proteína (g)", value=int(meta_prot), key=f"perfil_prot_{usuario}")
        nuevos_carbs = st.number_input("Carbohidratos (g)", value=int(meta_carbs), key=f"perfil_carbs_{usuario}")
        nuevas_grasas = st.number_input("Grasas (g)", value=int(meta_grasas), key=f"perfil_grasas_{usuario}")
        
        if st.button("Guardar Cambios", use_container_width=True, key=f"btn_perfil_{usuario}"):
            db.actualizar_perfil(usuario, nuevo_peso, altura, edad, nueva_kcal, nueva_prot, nuevos_carbs, nuevas_grasas)
            st.success("Perfil actualizado.")
            st.rerun()
