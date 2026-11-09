import hashlib
import sqlite3
import streamlit as st

try:
    import psycopg2
except ImportError:
    psycopg2 = None


def _hash_password(password):
    """Encripta la contraseña con SHA-256."""
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


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
        return psycopg2.connect(url), True
    return sqlite3.connect("cutting.db"), False


def _ph(es_pg, cantidad=1):
    """Genera los placeholders correctos (%s para Postgres, ? para SQLite)."""
    simbolo = "%s" if es_pg else "?"
    return ", ".join([simbolo] * cantidad)


@st.cache_resource
def init_db(_version=2):
    conn, es_pg = _conectar()
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

    conn.close()
    return True


# --- FUNCIONES DE AUTENTICACIÓN ---
def crear_usuario(usuario, password):
    """Intenta crear un usuario con contraseña encriptada (SHA-256). Retorna False si ya existe."""
    conn, es_pg = _conectar()
    c = conn.cursor()
    p = _ph(es_pg, 2)
    pwd_hash = _hash_password(password)
    try:
        c.execute(f"INSERT INTO usuarios (usuario, password) VALUES ({p})", (usuario, pwd_hash))
        conn.commit()
        exito = True
    except Exception:
        conn.rollback()
        exito = False
    conn.close()
    return exito


def verificar_usuario(usuario, password):
    """Verifica credenciales con SHA-256 y migra automáticamente cuentas antiguas en texto plano."""
    conn, es_pg = _conectar()
    c = conn.cursor()
    simbolo = "%s" if es_pg else "?"
    pwd_hash = _hash_password(password)

    c.execute(f"SELECT password FROM usuarios WHERE usuario = {simbolo}", (usuario,))
    fila = c.fetchone()
    if not fila:
        conn.close()
        return False

    pwd_guardada = fila[0]
    if pwd_guardada == pwd_hash:
        conn.close()
        return True

    # Si era una cuenta anterior en texto plano, se valida y se encripta automáticamente
    if pwd_guardada == password:
        c.execute(f"UPDATE usuarios SET password = {simbolo} WHERE usuario = {simbolo}", (pwd_hash, usuario))
        conn.commit()
        conn.close()
        return True

    conn.close()
    return False


# --- FUNCIONES DEL TRACKER (PIDEN EL USUARIO) ---
def obtener_perfil(usuario):
    conn, es_pg = _conectar()
    c = conn.cursor()
    simbolo = "%s" if es_pg else "?"
    c.execute(
        f"SELECT peso, altura, edad, meta_kcal, meta_prot, meta_carbs, meta_grasas FROM perfil WHERE usuario = {simbolo}",
        (usuario,)
    )
    datos = c.fetchone()
    conn.close()
    return datos


def crear_perfil(usuario, peso, altura, edad, kcal, prot, carbs, grasas):
    conn, es_pg = _conectar()
    c = conn.cursor()
    p = _ph(es_pg, 8)
    c.execute(
        f"INSERT INTO perfil (usuario, peso, altura, edad, meta_kcal, meta_prot, meta_carbs, meta_grasas) VALUES ({p})",
        (usuario, peso, altura, edad, kcal, prot, carbs, grasas)
    )
    conn.commit()
    conn.close()


def actualizar_perfil(usuario, peso, altura, edad, kcal, prot, carbs, grasas):
    conn, es_pg = _conectar()
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
    conn.close()


def agregar_comida(usuario, fecha_sel, nombre, kcal, prot, carbs, grasas):
    conn, es_pg = _conectar()
    c = conn.cursor()
    p = _ph(es_pg, 7)
    c.execute(
        f"INSERT INTO comidas (usuario, fecha, nombre, kcal, proteina, carbs, grasas) VALUES ({p})",
        (usuario, str(fecha_sel), nombre, kcal, prot, carbs, grasas)
    )
    conn.commit()
    conn.close()


def obtener_comidas_por_fecha(usuario, fecha_sel):
    conn, es_pg = _conectar()
    c = conn.cursor()
    s = "%s" if es_pg else "?"
    c.execute(
        f"SELECT id, nombre, kcal, proteina, carbs, grasas FROM comidas WHERE usuario = {s} AND fecha = {s}",
        (usuario, str(fecha_sel))
    )
    filas = c.fetchall()
    conn.close()
    return filas


def eliminar_comida(id_comida):
    conn, es_pg = _conectar()
    c = conn.cursor()
    s = "%s" if es_pg else "?"
    c.execute(f"DELETE FROM comidas WHERE id = {s}", (id_comida,))
    conn.commit()
    conn.close()


def registrar_peso_diario(usuario, fecha_sel, peso_val):
    conn, es_pg = _conectar()
    c = conn.cursor()
    p = _ph(es_pg, 3)
    s = "%s" if es_pg else "?"
    c.execute(f"INSERT INTO historial_peso (usuario, fecha, peso) VALUES ({p})", (usuario, str(fecha_sel), peso_val))
    c.execute(f"UPDATE perfil SET peso = {s} WHERE usuario = {s}", (peso_val, usuario))
    conn.commit()
    conn.close()


def obtener_historial_peso(usuario):
    conn, es_pg = _conectar()
    c = conn.cursor()
    s = "%s" if es_pg else "?"
    c.execute(f"SELECT fecha, peso FROM historial_peso WHERE usuario = {s} ORDER BY fecha ASC", (usuario,))
    datos = c.fetchall()
    conn.close()
    return datos


# --- FUNCIONES DE AYUNO INTERMITENTE ---
def obtener_ayuno(usuario):
    conn, es_pg = _conectar()
    c = conn.cursor()
    s = "%s" if es_pg else "?"
    c.execute(f"SELECT inicio_iso, horas_meta, activo FROM ayuno WHERE usuario = {s}", (usuario,))
    datos = c.fetchone()
    conn.close()
    return datos


def iniciar_ayuno(usuario, inicio_iso, horas_meta):
    conn, es_pg = _conectar()
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
    conn.close()


def detener_ayuno(usuario, fecha_sel, protocolo, horas_completadas, horas_meta):
    conn, es_pg = _conectar()
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
    conn.close()


def obtener_historial_ayunos(usuario):
    conn, es_pg = _conectar()
    c = conn.cursor()
    s = "%s" if es_pg else "?"
    c.execute(
        f"SELECT id, fecha, protocolo, horas_completadas, horas_meta FROM historial_ayunos WHERE usuario = {s} ORDER BY id DESC LIMIT 10",
        (usuario,)
    )
    datos = c.fetchall()
    conn.close()
    return datos


def cancelar_ayuno(usuario):
    """Descarta el ayuno en curso sin guardarlo en el historial (Control y libertad del usuario)."""
    conn, es_pg = _conectar()
    c = conn.cursor()
    s = "%s" if es_pg else "?"
    c.execute(f"UPDATE ayuno SET activo = 0 WHERE usuario = {s}", (usuario,))
    conn.commit()
    conn.close()


def eliminar_historial_ayuno(id_ayuno):
    """Elimina un registro del historial de ayunos."""
    conn, es_pg = _conectar()
    c = conn.cursor()
    s = "%s" if es_pg else "?"
    c.execute(f"DELETE FROM historial_ayunos WHERE id = {s}", (id_ayuno,))
    conn.commit()
    conn.close()
