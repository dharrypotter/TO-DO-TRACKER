import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort,
    jsonify,
)
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-me')

DATABASE = os.environ.get(
    'DATABASE_PATH',
    os.path.join(os.path.dirname(__file__), 'todo.db'),
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


def init_db():
    """Initialize the database by executing schema.sql."""
    conn = get_db_connection()
    with open(os.path.join(os.path.dirname(__file__), 'schema.sql')) as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()


def ensure_db():
    """Make sure the DB file and schema exist."""
    if not os.path.exists(DATABASE):
        init_db()
    else:
        # Always run schema (CREATE TABLE IF NOT EXISTS) so new installs upgrade.
        init_db()


# ---------------------------------------------------------------------------
# Auth model
# ---------------------------------------------------------------------------
class User(UserMixin):
    def __init__(self, row):
        self.id = row['id']
        self.username = row['username']
        self.email = row['email']
        self.password_hash = row['password_hash']

    @staticmethod
    def get(user_id):
        conn = get_db_connection()
        row = conn.execute('SELECT * FROM user WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        return User(row) if row else None

    @staticmethod
    def get_by_username(username):
        conn = get_db_connection()
        row = conn.execute(
            'SELECT * FROM user WHERE username = ?', (username,)
        ).fetchone()
        conn.close()
        return User(row) if row else None


@login_manager.user_loader
def load_user(user_id):
    return User.get(int(user_id))


# ---------------------------------------------------------------------------
# Template helpers
# ---------------------------------------------------------------------------
PRIORITY_LABELS = {1: 'Low', 2: 'Medium', 3: 'High'}
PRIORITY_COLORS = {1: 'success', 2: 'warning', 3: 'danger'}


@app.context_processor
def inject_helpers():
    return {
        'priority_labels': PRIORITY_LABELS,
        'priority_colors': PRIORITY_COLORS,
        'today': date.today(),
    }


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        error = None
        if not username or not email or not password:
            error = 'All fields are required.'
        elif len(password) < 6:
            error = 'Password must be at least 6 characters.'

        if not error:
            conn = get_db_connection()
            try:
                cur = conn.execute(
                    'INSERT INTO user (username, email, password_hash) VALUES (?, ?, ?)',
                    (username, email, generate_password_hash(password)),
                )
                user_id = cur.lastrowid

                # Seed a couple of helpful default categories for new users
                for name, color in [
                    ('Work', '#0d6efd'),
                    ('Personal', '#20c997'),
                    ('Errands', '#fd7e14'),
                ]:
                    conn.execute(
                        'INSERT INTO category (user_id, name, color) VALUES (?, ?, ?)',
                        (user_id, name, color),
                    )

                conn.commit()
            except sqlite3.IntegrityError:
                error = 'That username or email is already taken.'
            finally:
                conn.close()

        if error:
            flash(error, 'danger')
        else:
            flash('Account created — please log in.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        user = User.get_by_username(username)
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            return redirect(request.args.get('next') or url_for('index'))

        flash('Invalid username or password.', 'danger')

    return render_template('login.html')


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Signed out.', 'info')
    return redirect(url_for('login'))


# ---------------------------------------------------------------------------
# Todo routes
# ---------------------------------------------------------------------------
@app.route('/')
@login_required
def index():
    """Show the user's TODOs with optional filtering."""
    search_query = request.args.get('search_query', '').strip()
    status_filter = request.args.get('status', 'active')   # active | completed | all
    category_filter = request.args.get('category', '')     # category id or '' (all)
    priority_filter = request.args.get('priority', '')     # 1, 2, 3 or ''

    conn = get_db_connection()

    # Build SQL dynamically
    sql = """
        SELECT t.*, c.name AS category_name, c.color AS category_color
        FROM todo t
        LEFT JOIN category c ON c.id = t.category_id
        WHERE t.user_id = ?
    """
    params = [current_user.id]

    if search_query:
        sql += " AND (t.title LIKE ? OR t.description LIKE ?)"
        like = f'%{search_query}%'
        params += [like, like]

    if status_filter == 'active':
        sql += " AND t.completed = 0"
    elif status_filter == 'completed':
        sql += " AND t.completed = 1"

    if category_filter.isdigit():
        sql += " AND t.category_id = ?"
        params.append(int(category_filter))

    if priority_filter in ('1', '2', '3'):
        sql += " AND t.priority = ?"
        params.append(int(priority_filter))

    sql += ' ORDER BY t.completed ASC, t."order" ASC'

    todos = conn.execute(sql, params).fetchall()
    categories = conn.execute(
        'SELECT * FROM category WHERE user_id = ? ORDER BY name',
        (current_user.id,),
    ).fetchall()
    conn.close()

    return render_template(
        'index.html',
        todos=todos,
        categories=categories,
        search_query=search_query,
        status_filter=status_filter,
        category_filter=category_filter,
        priority_filter=priority_filter,
    )


@app.route('/add', methods=('GET', 'POST'))
@login_required
def add():
    """Add a new TODO."""
    conn = get_db_connection()
    categories = conn.execute(
        'SELECT * FROM category WHERE user_id = ? ORDER BY name',
        (current_user.id,),
    ).fetchall()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        priority = int(request.form.get('priority', 2) or 2)
        due_date = request.form.get('due_date') or None
        category_id = request.form.get('category_id') or None

        if priority not in (1, 2, 3):
            priority = 2
        if category_id and not str(category_id).isdigit():
            category_id = None
        if category_id is not None:
            category_id = int(category_id)
            owns = conn.execute(
                'SELECT 1 FROM category WHERE id = ? AND user_id = ?',
                (category_id, current_user.id),
            ).fetchone()
            if not owns:
                category_id = None

        if not title:
            flash('Title is required.', 'danger')
            conn.close()
            return render_template('add.html', categories=categories)

        row = conn.execute(
            'SELECT MAX("order") AS max_order FROM todo WHERE user_id = ?',
            (current_user.id,),
        ).fetchone()
        max_order = row['max_order'] if row['max_order'] is not None else 0

        conn.execute(
            '''INSERT INTO todo
               (user_id, title, description, priority, due_date, category_id, "order")
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (
                current_user.id,
                title,
                description,
                priority,
                due_date,
                category_id,
                max_order + 1,
            ),
        )
        conn.commit()
        conn.close()
        flash('Task added.', 'success')
        return redirect(url_for('index'))

    conn.close()
    return render_template('add.html', categories=categories)


def _get_owned_todo(conn, todo_id):
    """Fetch a todo that belongs to the current user, or None."""
    return conn.execute(
        'SELECT * FROM todo WHERE id = ? AND user_id = ?',
        (todo_id, current_user.id),
    ).fetchone()


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    conn = get_db_connection()
    todo = _get_owned_todo(conn, id)
    if not todo:
        conn.close()
        abort(404)

    categories = conn.execute(
        'SELECT * FROM category WHERE user_id = ? ORDER BY name',
        (current_user.id,),
    ).fetchall()

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        priority = int(request.form.get('priority', 2) or 2)
        due_date = request.form.get('due_date') or None
        category_id = request.form.get('category_id') or None

        if priority not in (1, 2, 3):
            priority = 2
        if category_id and str(category_id).isdigit():
            category_id = int(category_id)
            owns = conn.execute(
                'SELECT 1 FROM category WHERE id = ? AND user_id = ?',
                (category_id, current_user.id),
            ).fetchone()
            if not owns:
                category_id = None
        else:
            category_id = None

        if not title:
            flash('Title is required.', 'danger')
            conn.close()
            return render_template('edit.html', todo=todo, categories=categories)

        conn.execute(
            '''UPDATE todo
               SET title = ?, description = ?, priority = ?, due_date = ?, category_id = ?
               WHERE id = ? AND user_id = ?''',
            (title, description, priority, due_date, category_id, id, current_user.id),
        )
        conn.commit()
        conn.close()
        flash('Task updated.', 'success')
        return redirect(url_for('index'))

    conn.close()
    return render_template('edit.html', todo=todo, categories=categories)


@app.route('/complete/<int:id>', methods=['POST'])
@login_required
def complete(id):
    """Toggle completed state."""
    conn = get_db_connection()
    todo = _get_owned_todo(conn, id)
    if not todo:
        conn.close()
        abort(404)

    new_state = 0 if todo['completed'] else 1
    completed_at = datetime.utcnow().isoformat() if new_state else None
    conn.execute(
        'UPDATE todo SET completed = ?, completed_at = ? WHERE id = ? AND user_id = ?',
        (new_state, completed_at, id, current_user.id),
    )
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('index'))


@app.route('/resort/<int:id>/<string:direction>', methods=['POST'])
@login_required
def resort(id, direction):
    conn = get_db_connection()
    current_todo = _get_owned_todo(conn, id)
    if not current_todo:
        conn.close()
        abort(404)

    current_order = current_todo['order']

    if direction == 'up':
        neighbor = conn.execute(
            'SELECT * FROM todo WHERE user_id = ? AND "order" < ? ORDER BY "order" DESC LIMIT 1',
            (current_user.id, current_order),
        ).fetchone()
    else:
        neighbor = conn.execute(
            'SELECT * FROM todo WHERE user_id = ? AND "order" > ? ORDER BY "order" ASC LIMIT 1',
            (current_user.id, current_order),
        ).fetchone()

    if neighbor:
        # Swap orders. No UNIQUE constraint here so a direct swap is fine.
        conn.execute(
            'UPDATE todo SET "order" = ? WHERE id = ? AND user_id = ?',
            (neighbor['order'], id, current_user.id),
        )
        conn.execute(
            'UPDATE todo SET "order" = ? WHERE id = ? AND user_id = ?',
            (current_order, neighbor['id'], current_user.id),
        )
        conn.commit()

    conn.close()
    return redirect(request.referrer or url_for('index'))


@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    conn = get_db_connection()
    conn.execute(
        'DELETE FROM todo WHERE id = ? AND user_id = ?',
        (id, current_user.id),
    )
    conn.commit()
    conn.close()
    flash('Task deleted.', 'info')
    return redirect(request.referrer or url_for('index'))


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------
@app.route('/categories', methods=['GET', 'POST'])
@login_required
def categories():
    conn = get_db_connection()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        color = request.form.get('color', '#6c757d').strip() or '#6c757d'
        if name:
            try:
                conn.execute(
                    'INSERT INTO category (user_id, name, color) VALUES (?, ?, ?)',
                    (current_user.id, name, color),
                )
                conn.commit()
                flash(f'Category "{name}" added.', 'success')
            except sqlite3.IntegrityError:
                flash('You already have a category with that name.', 'warning')
        else:
            flash('Category name is required.', 'danger')
        conn.close()
        return redirect(url_for('categories'))

    cats = conn.execute(
        '''SELECT c.*,
              (SELECT COUNT(*) FROM todo t WHERE t.category_id = c.id) AS task_count
           FROM category c WHERE c.user_id = ?
           ORDER BY c.name''',
        (current_user.id,),
    ).fetchall()
    conn.close()
    return render_template('categories.html', categories=cats)


@app.route('/categories/<int:id>/delete', methods=['POST'])
@login_required
def delete_category(id):
    conn = get_db_connection()
    conn.execute(
        'DELETE FROM category WHERE id = ? AND user_id = ?',
        (id, current_user.id),
    )
    conn.commit()
    conn.close()
    flash('Category deleted.', 'info')
    return redirect(url_for('categories'))


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    uid = current_user.id
    today = date.today()
    week_start = today - timedelta(days=6)  # last 7 days inclusive

    total = conn.execute(
        'SELECT COUNT(*) AS n FROM todo WHERE user_id = ?', (uid,)
    ).fetchone()['n']
    done = conn.execute(
        'SELECT COUNT(*) AS n FROM todo WHERE user_id = ? AND completed = 1', (uid,)
    ).fetchone()['n']
    active = total - done

    completed_today = conn.execute(
        '''SELECT COUNT(*) AS n FROM todo
           WHERE user_id = ? AND completed = 1
             AND DATE(completed_at) = DATE(?)''',
        (uid, today.isoformat()),
    ).fetchone()['n']

    completed_week = conn.execute(
        '''SELECT COUNT(*) AS n FROM todo
           WHERE user_id = ? AND completed = 1
             AND DATE(completed_at) >= DATE(?)''',
        (uid, week_start.isoformat()),
    ).fetchone()['n']

    overdue = conn.execute(
        '''SELECT COUNT(*) AS n FROM todo
           WHERE user_id = ? AND completed = 0
             AND due_date IS NOT NULL AND DATE(due_date) < DATE(?)''',
        (uid, today.isoformat()),
    ).fetchone()['n']

    # Activity over the past 14 days (for chart)
    chart_days = []
    for i in range(13, -1, -1):
        d = today - timedelta(days=i)
        n = conn.execute(
            '''SELECT COUNT(*) AS n FROM todo
               WHERE user_id = ? AND completed = 1
                 AND DATE(completed_at) = DATE(?)''',
            (uid, d.isoformat()),
        ).fetchone()['n']
        chart_days.append({'date': d.strftime('%b %d'), 'count': n})

    # Streak: consecutive days (ending today) with at least one completion
    streak = 0
    cursor = today
    while True:
        n = conn.execute(
            '''SELECT COUNT(*) AS n FROM todo
               WHERE user_id = ? AND completed = 1
                 AND DATE(completed_at) = DATE(?)''',
            (uid, cursor.isoformat()),
        ).fetchone()['n']
        if n > 0:
            streak += 1
            cursor -= timedelta(days=1)
        else:
            break
        if streak > 365:  # safety
            break

    # Tasks by category (for chart)
    by_category = conn.execute(
        '''SELECT COALESCE(c.name, 'Uncategorized') AS name,
                  COALESCE(c.color, '#6c757d') AS color,
                  COUNT(t.id) AS n
           FROM todo t
           LEFT JOIN category c ON c.id = t.category_id
           WHERE t.user_id = ?
           GROUP BY c.id''',
        (uid,),
    ).fetchall()

    conn.close()

    completion_rate = round((done / total) * 100) if total else 0

    return render_template(
        'dashboard.html',
        total=total,
        done=done,
        active=active,
        completed_today=completed_today,
        completed_week=completed_week,
        overdue=overdue,
        completion_rate=completion_rate,
        streak=streak,
        chart_days=chart_days,
        by_category=by_category,
    )


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
ensure_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_DEBUG') == '1')
