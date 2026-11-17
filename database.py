from contextlib import contextmanager
import hashlib
import hmac
import secrets
import sqlite3
import streamlit as st

try:
    import psycopg2
    from psycopg2 import pool as pg_pool
except ImportError:
    psycopg2 = None
    pg_pool = None

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

    sha256_simple = hashlib.sha256(password.encode("utf-8")).hexdigest()
    if hmac.compare_digest(pwd_guardada, sha256_simple):
        return True, True

    if hmac.compare_digest(pwd_guardada, password):
        return True, True

    return False, False


def _usar_postgres():
    """Retorna True si DATABASE_URL está configurada en st.secrets y psycopg2 está disponible."""
    try:
        return bool(psycopg2 and "DATABASE_URL" in st.secrets and st.secrets["DATABASE_URL"])
    except Exception:
        return False


@st.cache_resource
def _obtener_pool_pg(url):
    """Mantiene un pool de conexiones reutilizables hacia Supabase para evitar reconexiones SSL lentas."""
    return pg_pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=url, connect_timeout=10)


def _conectar():
    """Obtiene una conexión rápida del pool de Supabase (PostgreSQL) o de SQLite local."""
    if _usar_postgres():
        url = st.secrets["DATABASE_URL"].replace("[", "").replace("]", "")
        try:
            pool_inst = _obtener_pool_pg(url)
            conn = pool_inst.getconn()
            if conn.closed:
                pool_inst.putconn(conn, close=True)
                conn = psycopg2.connect(url, connect_timeout=10)
                return conn, True, None
            return conn, True, pool_inst
        except Exception:
            return psycopg2.connect(url, connect_timeout=10), True, None
    return sqlite3.connect("cutting.db", timeout=10), False, None


@contextmanager
def _sesion_db(commit=False):
    """Context manager que gestiona cursores, commits y devuelve la conexión al pool de forma segura."""
    conn, es_pg, pool_inst = _conectar()
    try:
        c = conn.cursor()
        yield c, conn, es_pg
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        if pool_inst is not None:
            try:
                pool_inst.putconn(conn)
            except Exception:
                conn.close()
        else:
            conn.close()


def _ph(es_pg, cantidad=1):
    """Genera los placeholders correctos (%s para Postgres, ? para SQLite)."""
    simbolo = "%s" if es_pg else "?"
    return ", ".join([simbolo] * cantidad)


@st.cache_resource
def init_db(_version=8):
    with _sesion_db() as (c, conn, es_pg):
        id_tipo = "SERIAL PRIMARY KEY" if es_pg else "INTEGER PRIMARY KEY AUTOINCREMENT"

        tablas = [
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                usuario TEXT PRIMARY KEY,
                password TEXT,
                pregunta_seguridad TEXT,
                respuesta_hash TEXT
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
            """,
            f"""
            CREATE TABLE IF NOT EXISTS ejercicios (
                id {id_tipo},
                usuario TEXT,
                fecha TEXT,
                nombre TEXT,
                duracion_min INTEGER,
                kcal_quemadas INTEGER
            )
            """
        ]

        for sql in tablas:
            try:
                c.execute(sql)
                conn.commit()
            except Exception:
                conn.rollback()

        for col_sql in [
            "ALTER TABLE usuarios ADD COLUMN pregunta_seguridad TEXT;",
            "ALTER TABLE usuarios ADD COLUMN respuesta_hash TEXT;"
        ]:
            try:
                c.execute(col_sql)
                conn.commit()
            except Exception:
                conn.rollback()

        # Índices para acelerar las consultas por usuario y fecha
        indices = [
            "CREATE INDEX IF NOT EXISTS idx_comidas_usr_fecha ON comidas (usuario, fecha);",
            "CREATE INDEX IF NOT EXISTS idx_ejercicios_usr_fecha ON ejercicios (usuario, fecha);",
            "CREATE INDEX IF NOT EXISTS idx_peso_usr ON historial_peso (usuario);",
            "CREATE INDEX IF NOT EXISTS idx_hist_ayunos_usr ON historial_ayunos (usuario);"
        ]
        for idx_sql in indices:
            try:
                c.execute(idx_sql)
                conn.commit()
            except Exception:
                conn.rollback()

        if es_pg:
            nombres_tablas = [
                "usuarios", "perfil", "comidas", "historial_peso",
                "ayuno", "historial_ayunos", "ejercicios"
            ]
            for nombre_t in nombres_tablas:
                try:
                    c.execute(f"ALTER TABLE {nombre_t} ENABLE ROW LEVEL SECURITY;")
                    conn.commit()
                except Exception:
                    conn.rollback()
    return True


# --- FUNCIONES DE AUTENTICACIÓN Y SEGURIDAD ---
def crear_usuario(usuario, password, pregunta="", respuesta=""):
    """Crea un usuario con contraseña y respuesta de seguridad protegidas con PBKDF2-HMAC-SHA256 + salt."""
    pwd_hash = _hash_password(password)
    resp_limpia = str(respuesta or "").strip().lower()
    resp_hash = _hash_password(resp_limpia) if resp_limpia else ""
    try:
        with _sesion_db(commit=True) as (c, _, es_pg):
            p = _ph(es_pg, 4)
            c.execute(
                f"INSERT INTO usuarios (usuario, password, pregunta_seguridad, respuesta_hash) VALUES ({p})",
                (usuario, pwd_hash, str(pregunta or "").strip(), resp_hash)
            )
        return True
    except Exception:
        return False


def verificar_usuario(usuario, password):
    """Verifica credenciales en tiempo constante y migra automáticamente hashes antiguos a PBKDF2."""
    with _sesion_db() as (c, conn, es_pg):
        s = "%s" if es_pg else "?"
        c.execute(f"SELECT password FROM usuarios WHERE usuario = {s}", (usuario,))
        fila = c.fetchone()
        if not fila:
            return False

        es_valida, migrar = _verificar_hash(password, fila[0])
        if es_valida and migrar:
            nuevo_hash = _hash_password(password)
            c.execute(f"UPDATE usuarios SET password = {s} WHERE usuario = {s}", (nuevo_hash, usuario))
            conn.commit()
        return es_valida


def cambiar_password(usuario, password_actual, password_nueva):
    """Cambia la contraseña verificando primero la contraseña actual del usuario."""
    if not verificar_usuario(usuario, password_actual):
        return False
    nuevo_hash = _hash_password(password_nueva)
    with _sesion_db(commit=True) as (c, _, es_pg):
        s = "%s" if es_pg else "?"
        c.execute(f"UPDATE usuarios SET password = {s} WHERE usuario = {s}", (nuevo_hash, usuario))
    return True


def obtener_pregunta_seguridad(usuario):
    """Retorna (existe_usuario: bool, pregunta: str)."""
    with _sesion_db() as (c, _, es_pg):
        s = "%s" if es_pg else "?"
        c.execute(f"SELECT pregunta_seguridad FROM usuarios WHERE usuario = {s}", (usuario,))
        fila = c.fetchone()
        if fila is None:
            return False, ""
        return True, str(fila[0] or "").strip()


def guardar_pregunta_seguridad(usuario, pregunta, respuesta):
    """Guarda o actualiza la pregunta y respuesta de seguridad encriptada del usuario."""
    resp_limpia = str(respuesta).strip().lower()
    resp_hash = _hash_password(resp_limpia)
    with _sesion_db(commit=True) as (c, _, es_pg):
        s = "%s" if es_pg else "?"
        c.execute(
            f"UPDATE usuarios SET pregunta_seguridad = {s}, respuesta_hash = {s} WHERE usuario = {s}",
            (str(pregunta).strip(), resp_hash, usuario)
        )
    return True


def recuperar_password_pregunta(usuario, respuesta_ingresada, password_nueva):
    """Verifica la respuesta de seguridad y restablece la contraseña."""
    with _sesion_db() as (c, conn, es_pg):
        s = "%s" if es_pg else "?"
        c.execute(f"SELECT respuesta_hash FROM usuarios WHERE usuario = {s}", (usuario,))
        fila = c.fetchone()
        if not fila or not fila[0]:
            return False

        resp_limpia = str(respuesta_ingresada).strip().lower()
        es_valida, _ = _verificar_hash(resp_limpia, fila[0])
        if not es_valida:
            return False

        nuevo_hash = _hash_password(password_nueva)
        c.execute(f"UPDATE usuarios SET password = {s} WHERE usuario = {s}", (nuevo_hash, usuario))
        conn.commit()
        return True


# --- FUNCIONES DEL TRACKER (CON AISLAMIENTO ESTRICTO POR USUARIO) ---
def obtener_perfil(usuario):
    with _sesion_db() as (c, _, es_pg):
        s = "%s" if es_pg else "?"
        c.execute(
            f"SELECT peso, altura, edad, meta_kcal, meta_prot, meta_carbs, meta_grasas FROM perfil WHERE usuario = {s}",
            (usuario,)
        )
        return c.fetchone()


def crear_perfil(usuario, peso, altura, edad, kcal, prot, carbs, grasas):
    with _sesion_db(commit=True) as (c, _, es_pg):
        p = _ph(es_pg, 8)
        c.execute(
            f"INSERT INTO perfil (usuario, peso, altura, edad, meta_kcal, meta_prot, meta_carbs, meta_grasas) VALUES ({p})",
            (usuario, peso, altura, edad, kcal, prot, carbs, grasas)
        )


def actualizar_perfil(usuario, peso, altura, edad, kcal, prot, carbs, grasas):
    with _sesion_db(commit=True) as (c, _, es_pg):
        s = "%s" if es_pg else "?"
        c.execute(
            f"""
            UPDATE perfil 
            SET peso={s}, altura={s}, edad={s}, meta_kcal={s}, meta_prot={s}, meta_carbs={s}, meta_grasas={s}
            WHERE usuario={s}
            """,
            (peso, altura, edad, kcal, prot, carbs, grasas, usuario)
        )


def agregar_comida(usuario, fecha_sel, nombre, kcal, prot, carbs, grasas):
    with _sesion_db(commit=True) as (c, _, es_pg):
        p = _ph(es_pg, 7)
        c.execute(
            f"INSERT INTO comidas (usuario, fecha, nombre, kcal, proteina, carbs, grasas) VALUES ({p})",
            (usuario, str(fecha_sel), str(nombre)[:150], int(kcal), int(prot), int(carbs), int(grasas))
        )


def obtener_comidas_por_fecha(usuario, fecha_sel):
    with _sesion_db() as (c, _, es_pg):
        s = "%s" if es_pg else "?"
        c.execute(
            f"SELECT id, nombre, kcal, proteina, carbs, grasas FROM comidas WHERE usuario = {s} AND fecha = {s}",
            (usuario, str(fecha_sel))
        )
        return c.fetchall()


def eliminar_comida(id_comida, usuario=None):
    with _sesion_db(commit=True) as (c, _, es_pg):
        s = "%s" if es_pg else "?"
        if usuario:
            c.execute(f"DELETE FROM comidas WHERE id = {s} AND usuario = {s}", (id_comida, usuario))
        else:
            c.execute(f"DELETE FROM comidas WHERE id = {s}", (id_comida,))


def registrar_peso_diario(usuario, fecha_sel, peso_val):
    with _sesion_db(commit=True) as (c, _, es_pg):
        p = _ph(es_pg, 3)
        s = "%s" if es_pg else "?"
        c.execute(f"INSERT INTO historial_peso (usuario, fecha, peso) VALUES ({p})", (usuario, str(fecha_sel), peso_val))
        c.execute(f"UPDATE perfil SET peso = {s} WHERE usuario = {s}", (peso_val, usuario))


def obtener_historial_peso(usuario):
    with _sesion_db() as (c, _, es_pg):
        s = "%s" if es_pg else "?"
        c.execute(f"SELECT fecha, peso FROM historial_peso WHERE usuario = {s} ORDER BY fecha ASC", (usuario,))
        return c.fetchall()


# --- FUNCIONES DE AYUNO INTERMITENTE ---
def obtener_ayuno(usuario):
    with _sesion_db() as (c, _, es_pg):
        s = "%s" if es_pg else "?"
        c.execute(f"SELECT inicio_iso, horas_meta, activo FROM ayuno WHERE usuario = {s}", (usuario,))
        return c.fetchone()


def iniciar_ayuno(usuario, inicio_iso, horas_meta):
    with _sesion_db(commit=True) as (c, _, es_pg):
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


def detener_ayuno(usuario, fecha_sel, protocolo, horas_completadas, horas_meta):
    with _sesion_db(commit=True) as (c, _, es_pg):
        s = "%s" if es_pg else "?"
        p = _ph(es_pg, 5)
        c.execute(f"UPDATE ayuno SET activo = 0 WHERE usuario = {s}", (usuario,))
        if horas_completadas >= 0.1:
            c.execute(
                f"INSERT INTO historial_ayunos (usuario, fecha, protocolo, horas_completadas, horas_meta) VALUES ({p})",
                (usuario, str(fecha_sel), protocolo, round(float(horas_completadas), 2), int(horas_meta))
            )


def obtener_historial_ayunos(usuario):
    with _sesion_db() as (c, _, es_pg):
        s = "%s" if es_pg else "?"
        c.execute(
            f"SELECT id, fecha, protocolo, horas_completadas, horas_meta FROM historial_ayunos WHERE usuario = {s} ORDER BY id DESC LIMIT 10",
            (usuario,)
        )
        return c.fetchall()


def cancelar_ayuno(usuario):
    with _sesion_db(commit=True) as (c, _, es_pg):
        s = "%s" if es_pg else "?"
        c.execute(f"UPDATE ayuno SET activo = 0 WHERE usuario = {s}", (usuario,))


def eliminar_historial_ayuno(id_ayuno, usuario=None):
    with _sesion_db(commit=True) as (c, _, es_pg):
        s = "%s" if es_pg else "?"
        if usuario:
            c.execute(f"DELETE FROM historial_ayunos WHERE id = {s} AND usuario = {s}", (id_ayuno, usuario))
        else:
            c.execute(f"DELETE FROM historial_ayunos WHERE id = {s}", (id_ayuno,))


def obtener_resumen_dias(usuario, fechas_lista):
    if not fechas_lista:
        return {}
    with _sesion_db() as (c, _, es_pg):
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


# --- FUNCIONES DE EJERCICIO Y GASTO CALÓRICO ---
def agregar_ejercicio(usuario, fecha_sel, nombre, duracion_min, kcal_quemadas):
    with _sesion_db(commit=True) as (c, _, es_pg):
        p = _ph(es_pg, 5)
        c.execute(
            f"INSERT INTO ejercicios (usuario, fecha, nombre, duracion_min, kcal_quemadas) VALUES ({p})",
            (usuario, str(fecha_sel), str(nombre)[:150], int(duracion_min), int(kcal_quemadas))
        )


def obtener_ejercicios_por_fecha(usuario, fecha_sel):
    with _sesion_db() as (c, _, es_pg):
        s = "%s" if es_pg else "?"
        c.execute(
            f"SELECT id, nombre, duracion_min, kcal_quemadas FROM ejercicios WHERE usuario = {s} AND fecha = {s}",
            (usuario, str(fecha_sel))
        )
        return c.fetchall()


def eliminar_ejercicio(id_ejercicio, usuario=None):
    with _sesion_db(commit=True) as (c, _, es_pg):
        s = "%s" if es_pg else "?"
        if usuario:
            c.execute(f"DELETE FROM ejercicios WHERE id = {s} AND usuario = {s}", (id_ejercicio, usuario))
        else:
            c.execute(f"DELETE FROM ejercicios WHERE id = {s}", (id_ejercicio,))


def obtener_kcal_quemadas_dias(usuario, fechas_lista):
    if not fechas_lista:
        return {}
    with _sesion_db() as (c, _, es_pg):
        s = "%s" if es_pg else "?"
        placeholders = _ph(es_pg, len(fechas_lista))
        parametros = [usuario] + [str(f) for f in fechas_lista]
        c.execute(
            f"""
            SELECT fecha, SUM(kcal_quemadas)
            FROM ejercicios
            WHERE usuario = {s} AND fecha IN ({placeholders})
            GROUP BY fecha
            """,
            tuple(parametros)
        )
        filas = c.fetchall()
        return {fila[0]: int(fila[1] or 0) for fila in filas}
