def init_db():
    with app.app_context():
        import sqlite3, os
        if not os.path.exists('data'): os.makedirs('data')
        con = sqlite3.connect('data/app.db')
        with open('schema.sql', 'r', encoding='utf-8') as f:
            con.executescript(f.read())
        con.commit(); con.close()
