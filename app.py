import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = 'clave_secreta_super_segura_cecy'

# --- CONFIGURACIÓN DE SQLITE (Usuarios) ---
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_sqlite():
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            correo TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

init_sqlite()

# --- CONFIGURACIÓN DE MONGODB (CRUD Principal) ---
client = MongoClient('mongodb://localhost:27017/')
mongo_db = client['proyecto_integral_db']
coleccion_tareas = mongo_db['tareas']

# --- RUTAS PÚBLICAS ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        nombre = request.form['nombre']
        correo = request.form['correo']
        password = generate_password_hash(request.form['password'])

        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO usuarios (nombre, correo, password) VALUES (?, ?, ?)',
                         (nombre, correo, password))
            conn.commit()
            flash('Registro exitoso. Ahora inicia sesión.', 'exito')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Ese correo ya está registrado.', 'error')
        finally:
            conn.close()
    return render_template('registro.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        correo = request.form['correo']
        password = request.form['password']

        conn = get_db_connection()
        usuario = conn.execute('SELECT * FROM usuarios WHERE correo = ?', (correo,)).fetchone()
        conn.close()

        if usuario and check_password_hash(usuario['password'], password):
            session['usuario_id'] = usuario['id']
            session['usuario_nombre'] = usuario['nombre']
            return redirect(url_for('dashboard'))
        else:
            flash('Correo o contraseña incorrectos.', 'error')

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# --- RUTAS PRIVADAS (CRUD CON MONGODB) ---
@app.route('/dashboard')
def dashboard():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    # READ: Obtener registros de MongoDB del usuario actual
    tareas = list(coleccion_tareas.find({'usuario_id': session['usuario_id']}))
    return render_template('dashboard.html', tareas=tareas)

@app.route('/agregar', methods=['POST'])
def agregar():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    # CREATE: Insertar en MongoDB
    nueva_tarea = {
        'usuario_id': session['usuario_id'],
        'titulo': request.form['titulo'],
        'descripcion': request.form['descripcion'],
        'prioridad': request.form['prioridad'],
        'estado': 'Pendiente'
    }
    coleccion_tareas.insert_one(nueva_tarea)
    flash('Actividad agregada correctamente.', 'exito')
    return redirect(url_for('dashboard'))

@app.route('/editar/<id>', methods=['POST'])
def editar(id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    # UPDATE: Actualizar documento en MongoDB
    coleccion_tareas.update_one(
        {'_id': ObjectId(id)},
        {'$set': {
            'titulo': request.form['titulo'],
            'descripcion': request.form['descripcion'],
            'prioridad': request.form['prioridad'],
            'estado': request.form['estado']
        }}
    )
    flash('Actividad actualizada.', 'exito')
    return redirect(url_for('dashboard'))

@app.route('/eliminar/<id>')
def eliminar(id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    
    # DELETE: Eliminar documento en MongoDB
    coleccion_tareas.delete_one({'_id': ObjectId(id)})
    flash('Actividad eliminada.', 'exito')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True)