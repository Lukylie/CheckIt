from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date

app = Flask(__name__)
app.config['SECRET_KEY'] = 'checkit-secret-2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///checkit.db'

db = SQLAlchemy(app)

class User(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(100), nullable=False)
    email    = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    course   = db.Column(db.String(100), default='')
    theme    = db.Column(db.String(20), default='dark')

class Task(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    category    = db.Column(db.String(100), default='General')
    priority    = db.Column(db.String(20), default='Medium')
    due_date    = db.Column(db.String(20), default='')
    status      = db.Column(db.String(20), default='Pending')
    pinned      = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

class Collab(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    buddy_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    task_id  = db.Column(db.Integer, db.ForeignKey('task.id'), nullable=False)

with app.app_context():
    db.create_all()

def days_left(due_date_str):
    if not due_date_str:
        return None
    try:
        due = datetime.strptime(due_date_str, '%Y-%m-%d').date()
        return (due - date.today()).days
    except:
        return None

app.jinja_env.globals['days_left'] = days_left

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name     = request.form.get('name')
        email    = request.form.get('email')
        password = request.form.get('password')
        course   = request.form.get('course')
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return redirect(url_for('register'))
        user = User(name=name, email=email,
                    password=generate_password_hash(password), course=course)
        db.session.add(user)
        db.session.commit()
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email')
        password = request.form.get('password')
        user     = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            session['user_id']   = user.id
            session['user_name'] = user.name
            session['theme']     = user.theme
            return redirect(url_for('dashboard'))
        flash('Wrong email or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/theme/<theme_name>')
def set_theme(theme_name):
    if 'user_id' in session and theme_name in ['dark', 'pink', 'light']:
        user = User.query.get(session['user_id'])
        user.theme = theme_name
        db.session.commit()
        session['theme'] = theme_name
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid     = session['user_id']
    filter_ = request.args.get('filter', 'all')
    all_tasks = Task.query.filter_by(user_id=uid).all()
    total     = len(all_tasks)
    pending   = len([t for t in all_tasks if t.status == 'Pending'])
    done      = len([t for t in all_tasks if t.status == 'Done'])
    if filter_ == 'pending':
        tasks = Task.query.filter_by(user_id=uid, status='Pending').order_by(Task.pinned.desc(), Task.created_at.desc()).all()
    elif filter_ == 'done':
        tasks = Task.query.filter_by(user_id=uid, status='Done').order_by(Task.created_at.desc()).all()
    elif filter_ == 'pinned':
        tasks = Task.query.filter_by(user_id=uid, pinned=True).order_by(Task.created_at.desc()).all()
    else:
        tasks = Task.query.filter_by(user_id=uid).order_by(Task.pinned.desc(), Task.created_at.desc()).all()
    collabs = Collab.query.filter_by(buddy_id=uid).all()
    shared  = []
    for c in collabs:
        task  = Task.query.get(c.task_id)
        owner = User.query.get(c.owner_id)
        if task and owner:
            shared.append({'task': task, 'owner': owner})
    return render_template('dashboard.html', tasks=tasks, shared=shared,
                           total=total, pending=pending, done=done, filter_=filter_)

@app.route('/calendar')
def calendar():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    uid   = session['user_id']
    tasks = Task.query.filter_by(user_id=uid).filter(Task.due_date != '').all()
    cal_data = {}
    for t in tasks:
        cal_data.setdefault(t.due_date, []).append({
            'title': t.title,
            'priority': (t.priority or 'Medium').capitalize(),
            'status': t.status or 'Pending'
        })
    return render_template('calendar.html', cal_data=cal_data)

@app.route('/add', methods=['GET', 'POST'])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        task = Task(
            user_id     = session['user_id'],
            title       = request.form.get('title'),
            description = request.form.get('description', ''),
            category    = request.form.get('category'),
            priority    = request.form.get('priority'),
            due_date    = request.form.get('due_date'),
            pinned      = bool(request.form.get('pinned'))
        )
        db.session.add(task)
        db.session.commit()
        flash('Task added!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('add_task.html')

@app.route('/edit/<int:task_id>', methods=['GET', 'POST'])
def edit_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    task = Task.query.get_or_404(task_id)
    if request.method == 'POST':
        task.title       = request.form.get('title')
        task.description = request.form.get('description', '')
        task.category    = request.form.get('category')
        task.priority    = request.form.get('priority')
        task.due_date    = request.form.get('due_date')
        task.status      = request.form.get('status')
        task.pinned      = bool(request.form.get('pinned'))
        db.session.commit()
        flash('Task updated!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('edit_task.html', task=task)

@app.route('/toggle/<int:task_id>')
def toggle_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    task = Task.query.get_or_404(task_id)
    task.status = 'Done' if task.status == 'Pending' else 'Pending'
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/pin/<int:task_id>')
def pin_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    task = Task.query.get_or_404(task_id)
    task.pinned = not task.pinned
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/delete/<int:task_id>')
def delete_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    task = Task.query.get_or_404(task_id)
    Collab.query.filter_by(task_id=task_id).delete()
    db.session.delete(task)
    db.session.commit()
    flash('Task deleted.', 'success')
    return redirect(url_for('dashboard'))

@app.route('/collab/<int:task_id>', methods=['GET', 'POST'])
def collab(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    task     = Task.query.get_or_404(task_id)
    users    = User.query.filter(User.id != session['user_id']).all()
    existing = Collab.query.filter_by(task_id=task_id).all()
    buddies  = [User.query.get(c.buddy_id) for c in existing]
    if request.method == 'POST':
        buddy_id = request.form.get('buddy_id')
        if Collab.query.filter_by(task_id=task_id, buddy_id=buddy_id).first():
            flash('Already added!', 'error')
        else:
            db.session.add(Collab(owner_id=session['user_id'], buddy_id=buddy_id, task_id=task_id))
            db.session.commit()
            flash('Collaborator added!', 'success')
        return redirect(url_for('collab', task_id=task_id))
    return render_template('collab.html', task=task, users=users, buddies=buddies)

@app.route('/remove_collab/<int:task_id>/<int:buddy_id>')
def remove_collab(task_id, buddy_id):
    c = Collab.query.filter_by(task_id=task_id, buddy_id=buddy_id).first()
    if c:
        db.session.delete(c)
        db.session.commit()
        flash('Collaborator removed.', 'success')
    return redirect(url_for('collab', task_id=task_id))

if __name__ == '__main__':
    app.run(debug=True)