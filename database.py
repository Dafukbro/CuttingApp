import hashlib
import hmac
import secrets
import sqlite3
import streamlit as st

try:
    import psycopg2
except ImportError:
    psycopg2 = None

PBKDF2_ITERATIONS = 200_000


def _hash_password(password, salt=None):
    """Genera un hash seguro PBKDF2-HMAC-SHA256 con salt aleatorio por usuario."""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${salt}${dk}"


def _verificar_hash(password, pwd_guardada):
    """
    Verifica la contraseña en tiempo constante (hmac.compare_digest).
    Retorna (es_valida, requiere_migracion).
    """
    if not pwd_guardada:
        return False, False

    if pwd_guardada.startswith("pbkdf2_sha256$"):
        partes = pwd_guardada.split("$")
        if len(partes) == 3:
            _, salt, _ = partes
            esperado = _hash_password(password, salt)
            return hmac.compare_digest(esperado, pwd_guardada), False
        return False, False

    # Compatibilidad con SHA-256 anterior (sin salt) -> migrar a PBKDF2
    sha256_simple = hashlib.sha256(password.encode("utf-8")).hexdigest()
    if hmac.compare_digest(pwd_guardada, sha256_simple):
        return True, True

    # Compatibilidad con texto plano antiguo -> migrar a PBKDF2
    if hmac.compare_digest(pwd_guardada, password):
        return True, True

    return False, False


def _usar_postgres():
    """Retorna True si DATABASE_URL está configurada en st.secrets y psycopg2 está disponible."""
    try:
        return bool(psycopg2 and "DATABASE_URL" in st.secrets and st.secrets["DATABASE_URL"])
    except Exception:
        return False


def _conectar():
    """Abre conexión a Supabase (PostgreSQL) si está configurado, o a SQLite local como respaldo."""
    if _usar_postgres():
        url = st.secrets["DATABASE_URL"].replace("[", "").replace("]", "")
        return psycopg2.connect(url, connect_timeout=10), True
    return sqlite3.connect("cutting.db", timeout=10), False


def _ph(es_pg, cantidad=1):
    """Genera los placeholders correctos (%s para Postgres, ? para SQLite)."""
    simbolo = "%s" if es_pg else "?"
    return ", ".join([simbolo] * cantidad)


@st.cache_resource
def init_db(_version=3):
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        id_tipo = "SERIAL PRIMARY KEY" if es_pg else "INTEGER PRIMARY KEY AUTOINCREMENT"

        tablas = [
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                usuario TEXT PRIMARY KEY,
                password TEXT
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS perfil (
                usuario TEXT PRIMARY KEY, 
                peso REAL, altura REAL, edad INTEGER,
                meta_kcal INTEGER, meta_prot INTEGER, meta_carbs INTEGER, meta_grasas INTEGER
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS comidas (
                id {id_tipo}, 
                usuario TEXT,
                fecha TEXT, nombre TEXT,
                kcal INTEGER, proteina INTEGER, carbs INTEGER, grasas INTEGER
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS historial_peso (
                id {id_tipo}, 
                usuario TEXT,
                fecha TEXT, peso REAL
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS ayuno (
                usuario TEXT PRIMARY KEY,
                inicio_iso TEXT,
                horas_meta INTEGER,
                activo INTEGER
            )
            """,
            f"""
            CREATE TABLE IF NOT EXISTS historial_ayunos (
                id {id_tipo},
                usuario TEXT,
                fecha TEXT,
                protocolo TEXT,
                horas_completadas REAL,
                horas_meta INTEGER
            )
            """
        ]

        for sql in tablas:
            try:
                c.execute(sql)
                conn.commit()
            except Exception:
                conn.rollback()
    finally:
        conn.close()
    return True


# --- FUNCIONES DE AUTENTICACIÓN Y SEGURIDAD ---
def crear_usuario(usuario, password):
    """Crea un usuario con contraseña protegida con PBKDF2-HMAC-SHA256 + salt."""
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        p = _ph(es_pg, 2)
        pwd_hash = _hash_password(password)
        try:
            c.execute(f"INSERT INTO usuarios (usuario, password) VALUES ({p})", (usuario, pwd_hash))
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False
    finally:
        conn.close()


def verificar_usuario(usuario, password):
    """Verifica credenciales en tiempo constante y migra automáticamente hashes antiguos a PBKDF2."""
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        simbolo = "%s" if es_pg else "?"

        c.execute(f"SELECT password FROM usuarios WHERE usuario = {simbolo}", (usuario,))
        fila = c.fetchone()
        if not fila:
            return False

        es_valida, migrar = _verificar_hash(password, fila[0])
        if es_valida and migrar:
            nuevo_hash = _hash_password(password)
            c.execute(f"UPDATE usuarios SET password = {simbolo} WHERE usuario = {simbolo}", (nuevo_hash, usuario))
            conn.commit()

        return es_valida
    finally:
        conn.close()


def cambiar_password(usuario, password_actual, password_nueva):
    """Cambia la contraseña verificando primero la contraseña actual del usuario."""
    if not verificar_usuario(usuario, password_actual):
        return False
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        s = "%s" if es_pg else "?"
        nuevo_hash = _hash_password(password_nueva)
        c.execute(f"UPDATE usuarios SET password = {s} WHERE usuario = {s}", (nuevo_hash, usuario))
        conn.commit()
        return True
    finally:
        conn.close()


# --- FUNCIONES DEL TRACKER (CON AISLAMIENTO ESTRICTO POR USUARIO) ---
def obtener_perfil(usuario):
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        simbolo = "%s" if es_pg else "?"
        c.execute(
            f"SELECT peso, altura, edad, meta_kcal, meta_prot, meta_carbs, meta_grasas FROM perfil WHERE usuario = {simbolo}",
            (usuario,)
        )
        return c.fetchone()
    finally:
        conn.close()


def crear_perfil(usuario, peso, altura, edad, kcal, prot, carbs, grasas):
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        p = _ph(es_pg, 8)
        c.execute(
            f"INSERT INTO perfil (usuario, peso, altura, edad, meta_kcal, meta_prot, meta_carbs, meta_grasas) VALUES ({p})",
            (usuario, peso, altura, edad, kcal, prot, carbs, grasas)
        )
        conn.commit()
    finally:
        conn.close()


def actualizar_perfil(usuario, peso, altura, edad, kcal, prot, carbs, grasas):
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        s = "%s" if es_pg else "?"
        c.execute(
            f"""
            UPDATE perfil 
            SET peso={s}, altura={s}, edad={s}, meta_kcal={s}, meta_prot={s}, meta_carbs={s}, meta_grasas={s}
            WHERE usuario={s}
            """,
            (peso, altura, edad, kcal, prot, carbs, grasas, usuario)
        )
        conn.commit()
    finally:
        conn.close()


def agregar_comida(usuario, fecha_sel, nombre, kcal, prot, carbs, grasas):
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        p = _ph(es_pg, 7)
        c.execute(
            f"INSERT INTO comidas (usuario, fecha, nombre, kcal, proteina, carbs, grasas) VALUES ({p})",
            (usuario, str(fecha_sel), str(nombre)[:150], int(kcal), int(prot), int(carbs), int(grasas))
        )
        conn.commit()
    finally:
        conn.close()


def obtener_comidas_por_fecha(usuario, fecha_sel):
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        s = "%s" if es_pg else "?"
        c.execute(
            f"SELECT id, nombre, kcal, proteina, carbs, grasas FROM comidas WHERE usuario = {s} AND fecha = {s}",
            (usuario, str(fecha_sel))
        )
        return c.fetchall()
    finally:
        conn.close()


def eliminar_comida(id_comida, usuario=None):
    """Elimina una comida verificando que pertenezca al usuario autenticado."""
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        s = "%s" if es_pg else "?"
        if usuario:
            c.execute(f"DELETE FROM comidas WHERE id = {s} AND usuario = {s}", (id_comida, usuario))
        else:
            c.execute(f"DELETE FROM comidas WHERE id = {s}", (id_comida,))
        conn.commit()
    finally:
        conn.close()


def registrar_peso_diario(usuario, fecha_sel, peso_val):
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        p = _ph(es_pg, 3)
        s = "%s" if es_pg else "?"
        c.execute(f"INSERT INTO historial_peso (usuario, fecha, peso) VALUES ({p})", (usuario, str(fecha_sel), peso_val))
        c.execute(f"UPDATE perfil SET peso = {s} WHERE usuario = {s}", (peso_val, usuario))
        conn.commit()
    finally:
        conn.close()


def obtener_historial_peso(usuario):
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        s = "%s" if es_pg else "?"
        c.execute(f"SELECT fecha, peso FROM historial_peso WHERE usuario = {s} ORDER BY fecha ASC", (usuario,))
        return c.fetchall()
    finally:
        conn.close()


# --- FUNCIONES DE AYUNO INTERMITENTE ---
def obtener_ayuno(usuario):
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        s = "%s" if es_pg else "?"
        c.execute(f"SELECT inicio_iso, horas_meta, activo FROM ayuno WHERE usuario = {s}", (usuario,))
        return c.fetchone()
    finally:
        conn.close()


def iniciar_ayuno(usuario, inicio_iso, horas_meta):
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        s = "%s" if es_pg else "?"
        p = _ph(es_pg, 4)
        c.execute(f"SELECT usuario FROM ayuno WHERE usuario = {s}", (usuario,))
        if c.fetchone():
            c.execute(
                f"UPDATE ayuno SET inicio_iso = {s}, horas_meta = {s}, activo = 1 WHERE usuario = {s}",
                (inicio_iso, int(horas_meta), usuario)
            )
        else:
            c.execute(
                f"INSERT INTO ayuno (usuario, inicio_iso, horas_meta, activo) VALUES ({p})",
                (usuario, inicio_iso, int(horas_meta), 1)
            )
        conn.commit()
    finally:
        conn.close()


def detener_ayuno(usuario, fecha_sel, protocolo, horas_completadas, horas_meta):
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        s = "%s" if es_pg else "?"
        p = _ph(es_pg, 5)
        c.execute(f"UPDATE ayuno SET activo = 0 WHERE usuario = {s}", (usuario,))
        if horas_completadas >= 0.1:
            c.execute(
                f"INSERT INTO historial_ayunos (usuario, fecha, protocolo, horas_completadas, horas_meta) VALUES ({p})",
                (usuario, str(fecha_sel), protocolo, round(float(horas_completadas), 2), int(horas_meta))
            )
        conn.commit()
    finally:
        conn.close()


def obtener_historial_ayunos(usuario):
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        s = "%s" if es_pg else "?"
        c.execute(
            f"SELECT id, fecha, protocolo, horas_completadas, horas_meta FROM historial_ayunos WHERE usuario = {s} ORDER BY id DESC LIMIT 10",
            (usuario,)
        )
        return c.fetchall()
    finally:
        conn.close()


def cancelar_ayuno(usuario):
    """Descarta el ayuno en curso sin guardarlo en el historial."""
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        s = "%s" if es_pg else "?"
        c.execute(f"UPDATE ayuno SET activo = 0 WHERE usuario = {s}", (usuario,))
        conn.commit()
    finally:
        conn.close()


def eliminar_historial_ayuno(id_ayuno, usuario=None):
    """Elimina un registro del historial de ayunos verificando propiedad del usuario."""
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        s = "%s" if es_pg else "?"
        if usuario:
            c.execute(f"DELETE FROM historial_ayunos WHERE id = {s} AND usuario = {s}", (id_ayuno, usuario))
        else:
            c.execute(f"DELETE FROM historial_ayunos WHERE id = {s}", (id_ayuno,))
        conn.commit()
    finally:
        conn.close()


def obtener_resumen_dias(usuario, fechas_lista):
    """Obtiene calorías y proteínas totales por día para una lista de fechas (Resumen semanal)."""
    if not fechas_lista:
        return {}
    conn, es_pg = _conectar()
    try:
        c = conn.cursor()
        s = "%s" if es_pg else "?"
        placeholders = _ph(es_pg, len(fechas_lista))
        parametros = [usuario] + [str(f) for f in fechas_lista]
        c.execute(
            f"""
            SELECT fecha, SUM(kcal), SUM(proteina)
            FROM comidas
            WHERE usuario = {s} AND fecha IN ({placeholders})
            GROUP BY fecha
            ORDER BY fecha ASC
            """,
            tuple(parametros)
        )
        filas = c.fetchall()
        return {fila[0]: (int(fila[1] or 0), int(fila[2] or 0)) for fila in filas}
    finally:
        conn.close()
