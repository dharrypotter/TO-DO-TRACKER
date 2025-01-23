import os
import sys

from flask import Flask, render_template, request, redirect, url_for
import sqlite3

app = Flask(__name__)

# Path to the SQLite database
DATABASE = os.path.join(os.path.dirname(__file__), 'todo.db')

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initialize the database by executing schema.sql script.
    """
    with app.app_context():
        conn = get_db_connection()
        with open(os.path.join(os.path.dirname(__file__), 'schema.sql')) as f:
            conn.executescript(f.read())
        conn.close()

@app.route('/')
def index():
    """
    Show all TODOs in sorted order by the "order" column.
    Allows an optional search query.
    """
    search_query = request.args.get('search_query', '').strip()
    conn = get_db_connection()

    if search_query:
        # Use LIKE search if there's a query
        todos = conn.execute(
            'SELECT * FROM todo WHERE title LIKE ? ORDER BY "order"',
            (f'%{search_query}%',)
        ).fetchall()
    else:
        # Otherwise, return all
        todos = conn.execute('SELECT * FROM todo ORDER BY "order"').fetchall()

    conn.close()
    return render_template('index.html', todos=todos)

@app.route('/add', methods=('GET', 'POST'))
def add():
    """
    Add a new TODO item. New items get an "order" which is the current max order + 1.
    """
    if request.method == 'POST':
        title = request.form['title'].strip()
        if title:
            conn = get_db_connection()

            # Find the maximum "order" value
            row = conn.execute('SELECT MAX("order") AS max_order FROM todo').fetchone()
            max_order = row['max_order'] if row['max_order'] is not None else 0

            # Insert with order = max_order + 1
            conn.execute(
                'INSERT INTO todo (title, "order") VALUES (?, ?)',
                (title, max_order + 1)
            )

            conn.commit()
            conn.close()

        return redirect(url_for('index'))

    return render_template('add.html')

@app.route('/resort/<int:id>/<string:direction>', methods=['POST'])
def resort(id, direction):
    conn = get_db_connection()
    current_todo = conn.execute('SELECT * FROM todo WHERE id = ?', (id,)).fetchone()

    if not current_todo:
        conn.close()
        return redirect(url_for('index'))

    current_order = current_todo['order']

    if direction == 'up':
        # Get the item directly above (largest order that's still less than current_order)
        above_todo = conn.execute(
            'SELECT * FROM todo WHERE "order" < ? ORDER BY "order" DESC LIMIT 1',
            (current_order,)
        ).fetchone()

        if above_todo:
            above_order = above_todo['order']
            # Perform a three-step swap to avoid UNIQUE constraint collisions
            # 1) Move the above item to a temporary unused order (e.g., -1)
            conn.execute('UPDATE todo SET "order" = -1 WHERE id = ?', (above_todo['id'],))
            
            # 2) Move the current item up
            conn.execute('UPDATE todo SET "order" = ? WHERE id = ?', (above_order, id))
            
            # 3) Move the above item down
            conn.execute('UPDATE todo SET "order" = ? WHERE id = ?', (current_order, above_todo['id']))

    elif direction == 'down':
        # Get the item directly below (smallest order that's still greater than current_order)
        below_todo = conn.execute(
            'SELECT * FROM todo WHERE "order" > ? ORDER BY "order" ASC LIMIT 1',
            (current_order,)
        ).fetchone()

        if below_todo:
            below_order = below_todo['order']
            # Three-step swap again
            # 1) Move the below item to a temporary unused order
            conn.execute('UPDATE todo SET "order" = -1 WHERE id = ?', (below_todo['id'],))
            
            # 2) Move the current item down
            conn.execute('UPDATE todo SET "order" = ? WHERE id = ?', (below_order, id))
            
            # 3) Move the below item up
            conn.execute('UPDATE todo SET "order" = ? WHERE id = ?', (current_order, below_todo['id']))

    conn.commit()
    conn.close()
    return redirect(url_for('index'))


@app.route('/delete/<int:id>', methods=['GET', 'POST'])
def delete(id):
    """
    Delete a TODO item.
    """
    conn = get_db_connection()
    conn.execute('DELETE FROM todo WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

# If running directly (not via a WSGI server), run the Flask dev server
if __name__ == '__main__':
    # Initialize DB if needed (run once to set up schema, or handle externally)
    if not os.path.exists(DATABASE):
        init_db()

    app.run(debug=True)
