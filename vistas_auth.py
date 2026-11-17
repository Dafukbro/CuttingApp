import re
import time
import streamlit as st
import database as db
import ai_helper as ai
from config_nutricion import (
    MAX_INTENTOS_LOGIN,
    SEGUNDOS_BLOQUEO,
    PREGUNTAS_SEGURIDAD,
    OBJETIVOS_CONFIG,
    NIVELES_ACTIVIDAD,
    calcular_macros_objetivo,
    fecha_hoy,
)


def mostrar_pantalla_auth():
    """Renderiza el acceso (Iniciar Sesión, Registrarse y Recuperar Contraseña)."""
    st.title("🔐 Acceso a tu Tracker")
    opciones_auth = ["Iniciar Sesión", "Registrarse", "🔑 Recuperar Contraseña"]
    if "auth_tab_ant" not in st.session_state:
        st.session_state.auth_tab_ant = opciones_auth[0]

    auth_sel = st.radio(
        "Navegación de acceso",
        opciones_auth,
        horizontal=True,
        label_visibility="collapsed",
        key="auth_nav_radio"
    )
    if auth_sel != st.session_state.auth_tab_ant:
        st.session_state.auth_tab_ant = auth_sel
        st.session_state.reset_id += 1

    rid_auth = st.session_state.reset_id
    st.divider()

    if auth_sel == "Iniciar Sesión":
        tiempo_restante_bloqueo = int(st.session_state.bloqueo_hasta - time.time())
        if tiempo_restante_bloqueo > 0:
            st.error(f"⏳ Demasiados intentos fallidos. Por seguridad, espera **{tiempo_restante_bloqueo} segundos** antes de volver a intentar.")
        else:
            user_login = st.text_input("Usuario", max_chars=30, key=f"login_user_{rid_auth}").strip()
            pass_login = st.text_input("Contraseña", type="password", max_chars=128, key=f"login_pass_{rid_auth}")
            if st.button("Entrar", type="primary", use_container_width=True):
                if user_login and pass_login:
                    if db.verificar_usuario(user_login, pass_login):
                        st.session_state.clear()
                        st.session_state.usuario = user_login
                        st.session_state.mensajes = []
                        st.session_state.reset_id = 0
                        st.rerun()
                    else:
                        st.session_state.intentos_fallidos += 1
                        restantes = MAX_INTENTOS_LOGIN - st.session_state.intentos_fallidos
                        if restantes <= 0:
                            st.session_state.bloqueo_hasta = time.time() + SEGUNDOS_BLOQUEO
                            st.session_state.intentos_fallidos = 0
                            st.rerun()
                        else:
                            st.error(f"Usuario o contraseña incorrectos. Intentos restantes: {restantes}")
                else:
                    st.warning("Completa todos los campos.")

    elif auth_sel == "Registrarse":
        user_reg = st.text_input("Nuevo Usuario (letras, números o guion bajo)", max_chars=30, key=f"reg_user_{rid_auth}").strip()
        pass_reg = st.text_input("Nueva Contraseña (mínimo 6 caracteres)", type="password", max_chars=128, key=f"reg_pass_{rid_auth}")
        pass_reg_conf = st.text_input("Confirmar Contraseña", type="password", max_chars=128, key=f"reg_pass_conf_{rid_auth}")
        st.divider()
        st.caption("🛡️ **Pregunta de Seguridad** (te permitirá recuperar tu cuenta si olvidas la contraseña):")
        preg_sel_reg = st.selectbox("Elige una pregunta de seguridad", PREGUNTAS_SEGURIDAD, key=f"reg_preg_{rid_auth}")
        if preg_sel_reg == "✍️ Escribir mi propia pregunta personalizada...":
            preg_reg = st.text_input("Escribe tu pregunta personalizada", max_chars=120, placeholder="Ej. ¿Cuál fue mi primer gimnasio?", key=f"reg_preg_custom_{rid_auth}").strip()
        else:
            preg_reg = preg_sel_reg
        resp_reg = st.text_input("Tu respuesta secreta", max_chars=100, key=f"reg_resp_{rid_auth}").strip()

        if st.button("Crear Cuenta", type="primary", use_container_width=True):
            if not user_reg or not pass_reg or not pass_reg_conf or not preg_reg or not resp_reg:
                st.warning("Completa todos los campos (incluyendo la pregunta y respuesta de seguridad).")
            elif not re.match(r"^[a-zA-Z0-9_.-]{3,30}$", user_reg):
                st.error("El usuario debe tener entre 3 y 30 caracteres (solo letras, números, puntos, guiones o guion bajo, sin espacios).")
            elif len(pass_reg) < 6:
                st.error("La contraseña debe tener al menos 6 caracteres.")
            elif pass_reg != pass_reg_conf:
                st.error("Las contraseñas no coinciden.")
            else:
                if db.crear_usuario(user_reg, pass_reg, preg_reg, resp_reg):
                    st.session_state.reset_id += 1
                    st.success("¡Cuenta creada con éxito! Ahora puedes iniciar sesión.")
                else:
                    st.error("Ese nombre de usuario ya existe.")

    elif auth_sel == "🔑 Recuperar Contraseña":
        tiempo_restante_bloqueo = int(st.session_state.bloqueo_hasta - time.time())
        if tiempo_restante_bloqueo > 0:
            st.error(f"⏳ Demasiados intentos fallidos. Espera **{tiempo_restante_bloqueo} segundos** antes de volver a intentar.")
        else:
            st.caption("Ingresa tu nombre de usuario para ver tu pregunta de seguridad y restablecer tu contraseña.")
            user_rec = st.text_input("Tu nombre de usuario", max_chars=30, key=f"rec_user_q_{rid_auth}").strip()
            if user_rec:
                existe_u, pregunta_u = db.obtener_pregunta_seguridad(user_rec)
                if not existe_u:
                    st.error("No existe ninguna cuenta con ese nombre de usuario.")
                elif not pregunta_u:
                    st.warning("Esta cuenta aún no tiene una pregunta de seguridad configurada. Inicia sesión y configúrala en la pestaña **⚙️ Perfil**.")
                else:
                    with st.container(border=True):
                        st.info(f"🛡️ **Pregunta de seguridad:** {pregunta_u}")
                        resp_rec = st.text_input("Escribe tu respuesta secreta", type="password", max_chars=100, key=f"rec_resp_q_{rid_auth}").strip()
                        nueva_pwd_rec = st.text_input("Nueva Contraseña (mínimo 6 caracteres)", type="password", max_chars=128, key=f"rec_new_pwd_q_{rid_auth}")
                        conf_pwd_rec = st.text_input("Confirmar Nueva Contraseña", type="password", max_chars=128, key=f"rec_conf_pwd_q_{rid_auth}")

                        if st.button("✅ Restablecer Contraseña", type="primary", use_container_width=True, key=f"btn_rec_q_{rid_auth}"):
                            if not resp_rec or not nueva_pwd_rec or not conf_pwd_rec:
                                st.warning("Completa tu respuesta y la nueva contraseña.")
                            elif len(nueva_pwd_rec) < 6:
                                st.error("La nueva contraseña debe tener al menos 6 caracteres.")
                            elif nueva_pwd_rec != conf_pwd_rec:
                                st.error("Las contraseñas no coinciden.")
                            elif db.recuperar_password_pregunta(user_rec, resp_rec, nueva_pwd_rec):
                                st.session_state.intentos_fallidos = 0
                                st.session_state.reset_id += 1
                                st.success("🎉 ¡Contraseña restablecida con éxito! Ya puedes entrar en 'Iniciar Sesión'.")
                            else:
                                st.session_state.intentos_fallidos += 1
                                restantes = MAX_INTENTOS_LOGIN - st.session_state.intentos_fallidos
                                if restantes <= 0:
                                    st.session_state.bloqueo_hasta = time.time() + SEGUNDOS_BLOQUEO
                                    st.session_state.intentos_fallidos = 0
                                    st.rerun()
                                else:
                                    st.error(f"Respuesta incorrecta. Intentos restantes: {restantes}")


def mostrar_onboarding_perfil(usuario, api_key):
    """Renderiza la pantalla de configuración inicial cuando el usuario aún no tiene perfil."""
    st.title(f"👋 Bienvenido, {usuario}")
    st.write("Cuéntame sobre ti y elige tu objetivo para configurar tus metas automáticamente.")
    descripcion_usuario = st.text_area(
        "¿Cuál es tu peso, altura y edad?",
        placeholder="Ej. Tengo 21 años, mido 1.75m y peso 75 kilos.",
        key=f"desc_inicial_{usuario}"
    )
    obj_inicial = st.selectbox("🎯 ¿Cuál es tu objetivo actual?", list(OBJETIVOS_CONFIG.keys()), key=f"obj_ini_{usuario}")
    act_inicial = st.selectbox("🏃 Nivel de actividad semanal", list(NIVELES_ACTIVIDAD.keys()), index=2, key=f"act_ini_{usuario}")

    if st.button("✨ Generar mi plan", type="primary", use_container_width=True):
        if descripcion_usuario:
            datos = None
            with st.spinner("Calculando macros ideales..."):
                try:
                    datos = ai.extraer_datos_perfil(descripcion_usuario, api_key)
                except Exception as e:
                    st.error(f"Error: {e}")
            if datos:
                p_val, a_val, e_val = float(datos["peso"]), float(datos["altura"]), int(datos["edad"])
                meta_kcal, meta_prot, meta_carbs, meta_grasas, a_cm = calcular_macros_objetivo(
                    p_val, a_val, e_val, obj_inicial, act_inicial
                )
                db.crear_perfil(usuario, p_val, a_cm, e_val, meta_kcal, meta_prot, meta_carbs, meta_grasas)
                db.registrar_peso_diario(usuario, fecha_hoy(), p_val)
                st.success("¡Perfil creado!")
                st.rerun()
    if st.button("Cerrar Sesión", use_container_width=True):
        st.session_state.clear()
        st.rerun()
