import os
from flask import Flask, render_template, redirect, url_for, request

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret')

@app.route('/')
def home():
    return render_template('index.html', title='Bachatagram')

@app.route('/feed')
def feed():
    posts = [
        {'user':'Doodlez','text':'Вечером танцуем на набережной! 💃🕺','img':'https://images.unsplash.com/photo-1547153760-18fc86324498?q=80&w=1200&auto=format&fit=crop'},
        {'user':'Miroslav','text':'Фото с последней тусовки 📸','img':'https://images.unsplash.com/photo-1519741497674-611481863552?q=80&w=1200&auto=format&fit=crop'},
        {'user':'DJ Husky','text':'Свежий ремикс уже в эфире 🎧','img':'https://images.unsplash.com/photo-1483412033650-1015ddeb83d1?q=80&w=1200&auto=format&fit=crop'},
    ]
    return render_template('feed.html', title='Лента — Bachatagram', posts=posts)

@app.route('/auth', methods=['GET','POST'])
def auth():
    if request.method == 'POST':
        # демо: просто редирект в ленту
        return redirect(url_for('feed'))
    return render_template('auth.html', title='Вход — Bachatagram')

@app.route('/profile/<name>')
def profile(name):
    return render_template('profile.html', title=f'@{name} — Bachatagram', name=name)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.getenv('PORT', 5000)), debug=True)
