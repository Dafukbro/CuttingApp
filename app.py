import importlib
import streamlit as st
import database as db
import ai_helper as ai
from config_nutricion import fecha_hoy
from vistas_auth import mostrar_pantalla_auth, mostrar_onboarding_perfil
from vistas_tabs import (
    render_tab_resumen,
    render_tab_registro,
    render_tab_ayuno,
    render_tab_chat,
    render_tab_perfil,
)

if not hasattr(db, "_sesion_db"):
    importlib.reload(db)
if not hasattr(ai, "CONFIG_CHAT_HYDROGEN"):
    importlib.reload(ai)

st.set_page_config(page_title="Tracker Fitness & Cutting", page_icon="🔥", layout="centered")
db.init_db(8)

API_KEY = st.secrets["API_KEY"]

# --- INICIALIZACIÓN DE ESTADO DE SESIÓN ---
if "usuario" not in st.session_state:
    st.session_state.usuario = None
if "intentos_fallidos" not in st.session_state:
    st.session_state.intentos_fallidos = 0
if "bloqueo_hasta" not in st.session_state:
    st.session_state.bloqueo_hasta = 0.0
if "reset_id" not in st.session_state:
    st.session_state.reset_id = 0

# --- 1. PANTALLA DE LOGIN / REGISTRO / RECUPERACIÓN ---
if not st.session_state.usuario:
    mostrar_pantalla_auth()
    st.stop()

usuario = st.session_state.usuario
datos_perfil = db.obtener_perfil(usuario)

# --- 2. CONFIGURACIÓN INICIAL DE PERFIL (ONBOARDING) ---
if not datos_perfil:
    mostrar_onboarding_perfil(usuario, API_KEY)
    st.stop()

# --- 3. ENCABEZADO Y NAVEGACIÓN PRINCIPAL ---
peso = datos_perfil[0]

col_titulo, col_salir = st.columns([4, 1])
with col_titulo:
    st.title("🔥 Fitness & Macro Tracker")
    st.caption(f"👤 Sesión activa: **{usuario}**")
with col_salir:
    if st.button("Salir 🚪", use_container_width=True):
        st.session_state.clear()
        st.rerun()

PESTANAS = ["🏠 Resumen", "➕ Registro", "⏳ Ayuno", "🤖 Chat IA", "⚙️ Perfil"]
nav_key = f"nav_principal_{usuario}"

if nav_key not in st.session_state:
    st.session_state[nav_key] = "🏠 Resumen"
if "pestana_anterior" not in st.session_state:
    st.session_state.pestana_anterior = "🏠 Resumen"

if st.session_state.get("ir_a_resumen", False):
    st.session_state[nav_key] = "🏠 Resumen"
    st.session_state.pestana_anterior = "🏠 Resumen"
    st.session_state.ir_a_resumen = False

pestana_activa = st.radio(
    "Menú principal",
    PESTANAS,
    horizontal=True,
    label_visibility="collapsed",
    key=nav_key
)

if pestana_activa != st.session_state.pestana_anterior:
    st.session_state.pestana_anterior = pestana_activa
    st.session_state.reset_id += 1

rid = st.session_state.reset_id
st.divider()

if f"fecha_sel_{usuario}" not in st.session_state:
    st.session_state[f"fecha_sel_{usuario}"] = fecha_hoy()
fecha_activa = st.session_state[f"fecha_sel_{usuario}"]

# --- 4. RENDERIZADO DE LA PESTAÑA ACTIVA ---
if pestana_activa == "🏠 Resumen":
    render_tab_resumen(usuario, datos_perfil, fecha_activa, rid)
elif pestana_activa == "➕ Registro":
    render_tab_registro(usuario, peso, fecha_activa, rid, API_KEY)
elif pestana_activa == "⏳ Ayuno":
    render_tab_ayuno(usuario)
elif pestana_activa == "🤖 Chat IA":
    render_tab_chat(usuario, datos_perfil, fecha_activa, rid, API_KEY)
elif pestana_activa == "⚙️ Perfil":
    render_tab_perfil(usuario, datos_perfil, rid)
