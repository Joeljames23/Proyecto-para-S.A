from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime # NUEVO: Para manejar fechas

# ---------------------------------
# 1. INICIALIZACIÓN Y CONFIGURACIÓN
# ---------------------------------
app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:adgr@localhost/consultoria_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'adgr' 

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, inicia sesión para acceder a esta página.'

# ---------------------------------
# 2. DEFINICIÓN DE MODELOS
# ---------------------------------

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='client')
    empresa = db.Column(db.String(100), nullable=True)
    
    # NUEVO: Relación. Un usuario (cliente) puede tener muchos proyectos.
    # 'lazy=True' significa que SQLAlchemy cargará los proyectos solo cuando se necesiten.
    projects = db.relationship('Project', backref='client', lazy=True)

    def set_password(self, password_plana):
        self.password = generate_password_hash(password_plana)

    def check_password(self, password_plana):
        return check_password_hash(self.password, password_plana)

    def __repr__(self):
        return f'<User {self.email}>'

# NUEVO: Modelo para los Proyectos
class Project(db.Model):
    __tablename__ = 'projects'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(50), nullable=False, default='Pendiente') # Ej: Pendiente, En Progreso, Completado
    start_date = db.Column(db.Date, nullable=True)
    
    # NUEVO: Foreign Key. Esto conecta cada proyecto con un ID de usuario.
    # 'ondelete='CASCADE'' significa que si se borra un usuario, sus proyectos también se borran.
    client_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)

    def __repr__(self):
        return f'<Project {self.name}>'

# ---------------------------------
# 3. CONFIGURACIÓN DE FLASK-LOGIN
# ---------------------------------

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------------------------
# 4. RUTAS PÚBLICAS
# ---------------------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password_plana = request.form['password']
        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password_plana):
            login_user(user)
            if user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('client_dashboard'))
        else:
            flash('Correo o contraseña incorrectos.', 'error')
    return render_template('login.html')

# (La ruta de Registro y Logout no cambian)
@app.route('/register', methods=['GET', 'POST'])
def register():
    # ... (código sin cambios) ...
    if request.method == 'POST':
        email = request.form['email']
        name = request.form['name']
        password_plana = request.form['password']
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Ese correo electrónico ya está registrado.', 'error')
            return redirect(url_for('register'))
        new_user = User(email=email, name=name, role='client')
        new_user.set_password(password_plana)
        db.session.add(new_user)
        db.session.commit()
        flash('¡Cuenta creada exitosamente! Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# ---------------------------------
# 5. RUTAS PRIVADAS
# ---------------------------------

@app.route('/dashboard')
@login_required
def client_dashboard():
    if current_user.role != 'client':
        flash('Acceso no autorizado.', 'error')
        return redirect(url_for('index'))
    
    # NUEVO: Busca en la BD solo los proyectos que pertenecen al usuario logueado
    projects = Project.query.filter_by(client_id=current_user.id).all()
    
    # Pasamos el nombre del cliente y su lista de proyectos
    return render_template('dashboard.html', client_name=current_user.name, projects=projects)

@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash('Acceso no autorizado.', 'error')
        return redirect(url_for('index'))
    
    # Obtenemos todos los clientes para los formularios
    clients = User.query.filter_by(role='client').all()
    
    # NUEVO: Obtenemos todos los proyectos para mostrarlos (opcional, pero útil)
    all_projects = Project.query.order_by(Project.start_date.desc()).all()
        
    # Pasamos la lista de clientes y proyectos
    return render_template('admin.html', clients=clients, all_projects=all_projects)

@app.route('/create_client', methods=['POST'])
@login_required
def create_client():
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    nombre = request.form['nombre']
    apellido = request.form['apellido']
    email = request.form['email']
    password_plana = request.form['password']
    empresa = request.form['empresa']

    existing_user = User.query.filter_by(email=email).first()
    if existing_user:
        flash('Ese correo electrónico ya está registrado.', 'error')
        return redirect(url_for('admin_dashboard'))

    full_name = f"{nombre} {apellido}"
    new_client = User(email=email, name=full_name, empresa=empresa, role='client')
    new_client.set_password(password_plana)
    db.session.add(new_client)
    db.session.commit()

    flash('¡Cliente creado exitosamente!', 'success')
    return redirect(url_for('admin_dashboard'))

# NUEVO: RUTA PARA CREAR PROYECTOS
@app.route('/create_project', methods=['POST'])
@login_required
def create_project():
    if current_user.role != 'admin':
        return redirect(url_for('index'))

    # Obtenemos los datos del nuevo formulario de proyecto
    project_name = request.form['project_name']
    status = request.form['status']
    start_date_str = request.form['start_date']
    client_id = request.form['client_id'] # ID del cliente seleccionado

    # Convertimos la fecha de string a objeto Date
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()

    # Creamos el nuevo proyecto
    new_project = Project(
        name=project_name,
        status=status,
        start_date=start_date,
        client_id=client_id
    )
    
    db.session.add(new_project)
    db.session.commit()

    flash('¡Proyecto creado y asignado exitosamente!', 'success')
    return redirect(url_for('admin_dashboard')) # Redirigimos de vuelta al admin

# ---------------------------------
# 6. INICIAR EL SERVIDOR
# ---------------------------------

if __name__ == '__main__':
    with app.app_context():
        # db.create_all() creará AMBAS tablas (users y projects)
        db.create_all()
        
        if not User.query.filter_by(email='admin@consultoria.py').first():
            print("Creando usuario admin...")
            admin = User(email='admin@consultoria.py', name='Administrador', role='admin', empresa='Consultoría PY')
            admin.set_password('admin123') 
            db.session.add(admin)
            db.session.commit()
            print("Usuario admin creado.")
            
    app.run(debug=True)