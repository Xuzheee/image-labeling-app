from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin
import json, os

app = Flask(__name__)
app.secret_key = 'your_secret_key'

login_manager = LoginManager(app)

USER_INFO = {"admin": "123456"}

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    return User(user_id) if user_id in USER_INFO else None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in USER_INFO and USER_INFO[username] == password:
            login_user(User(username))
            return redirect('/')
        else:
            return "登录失败"
    return '''<form method="post">
                用户名:<input name="username"><br>密码:<input name="password" type="password"><br>
                <input type="submit" value="登录">
              </form>'''

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

with open('annotations.json', 'r', encoding='utf-8') as f:
    annotations = json.load(f)
image_names = [item['image'] for item in annotations]

def get_annotation(img_name):
    for item in annotations:
        if item['image'] == img_name:
            return item['annotation']
    return []

@app.route('/')
@login_required
def index():
    img = request.args.get('img')
    if not img:
        img = image_names[0]
    annotation = get_annotation(img)
    return render_template('index.html', img=img, images=image_names, annotation=annotation)

@app.route('/annotate', methods=['POST'])
@login_required
def annotate():
    img = request.form['img']
    labels = request.form.getlist('labels')
    with open(f'results/{img}.json', 'w', encoding='utf-8') as f:
        json.dump({"image": img, "annotation": labels}, f, ensure_ascii=False)
    idx = image_names.index(img)
    next_img = image_names[(idx + 1) % len(image_names)]
    return redirect(url_for('index', img=next_img))

@app.route('/images/<filename>')
def image_file(filename):
    return send_from_directory('images', filename)

if __name__ == '__main__':
    os.makedirs('results', exist_ok=True)
    app.run(debug=True)
