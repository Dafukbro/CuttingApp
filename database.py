import sqlite3
import streamlit as st

try:
    import psycopg2
except ImportError:
    psycopg2 = None


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


def init_db():
    conn, es_pg = _conectar()
    c = conn.cursor()
    id_tipo = "SERIAL PRIMARY KEY" if es_pg else "INTEGER PRIMARY KEY AUTOINCREMENT"

    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            usuario TEXT PRIMARY KEY,
            password TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS perfil (
            usuario TEXT PRIMARY KEY, 
            peso REAL, altura REAL, edad INTEGER,
            meta_kcal INTEGER, meta_prot INTEGER, meta_carbs INTEGER, meta_grasas INTEGER
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS comidas (
            id {id_tipo}, 
            usuario TEXT,
            fecha TEXT, nombre TEXT,
            kcal INTEGER, proteina INTEGER, carbs INTEGER, grasas INTEGER
        )
    """)

    c.execute(f"""
        CREATE TABLE IF NOT EXISTS historial_peso (
            id {id_tipo}, 
            usuario TEXT,
            fecha TEXT, peso REAL
        )
    """)
    conn.commit()
    conn.close()


# --- FUNCIONES DE AUTENTICACIÓN ---
def crear_usuario(usuario, password):
    """Intenta crear un usuario. Retorna False si ya existe."""
    conn, es_pg = _conectar()
    c = conn.cursor()
    p = _ph(es_pg, 2)
    try:
        c.execute(f"INSERT INTO usuarios (usuario, password) VALUES ({p})", (usuario, password))
        conn.commit()
        exito = True
    except Exception:
        conn.rollback()
        exito = False
    conn.close()
    return exito


def verificar_usuario(usuario, password):
    """Verifica si las credenciales coinciden en la base de datos."""
    conn, es_pg = _conectar()
    c = conn.cursor()
    simbolo = "%s" if es_pg else "?"
    c.execute(f"SELECT * FROM usuarios WHERE usuario = {simbolo} AND password = {simbolo}", (usuario, password))
    existe = c.fetchone() is not None
    conn.close()
    return existe


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
