from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, send_file
from flask_login import LoginManager, login_user, logout_user, login_required, UserMixin, current_user
import json
import os
import datetime
import copy

app = Flask(__name__)
# 生产环境中建议修改为随机字符串
app.secret_key = os.environ.get("SECRET_KEY", "default_secret_key_123")

# --- 1. 多用户认证配置 ---
login_manager = LoginManager(app)
login_manager.login_view = 'login' 

# 定义允许登录的用户及其密码
# 你可以在这里添加任意数量的用户
USERS_CONFIG = {
    "user1": "123456",
    "user2": "123456",
    "user3": "123456",
    "admin": "123456"
}

class User(UserMixin):
    def __init__(self, id):
        self.id = id

@login_manager.user_loader
def load_user(user_id):
    if user_id in USERS_CONFIG:
        return User(user_id)
    return None

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # 验证用户名和密码
        if username in USERS_CONFIG and USERS_CONFIG[username] == password:
            login_user(User(username))
            next_page = request.args.get('next')
            return redirect(next_page or '/')
        else:
            flash('用户名或密码错误')
            
    return '''
    <div style="text-align:center; margin-top:50px; font-family:sans-serif;">
        <form method="post" style="display:inline-block; border:1px solid #ccc; padding:20px;">
            <h3>多用户登录</h3>
            <p style="font-size:0.8em; color:#666;">可用账号: user1, user2, user3 (密码: 123456)</p>
            用户名: <input name="username" autofocus><br><br>
            密　码: <input name="password" type="password"><br><br>
            <input type="submit" value="登录" style="width:100%">
        </form>
    </div>
    '''

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect('/login')

# --- 2. 自定义过滤器 ---
@app.template_filter('pretty_json')
def pretty_json(value):
    return json.dumps(value, ensure_ascii=False, indent=2)

# --- 3. 多用户数据处理逻辑 ---

# 原始数据文件（作为所有用户的初始模板）
BASE_DATA_PATH = os.environ.get("DATA_FILE", "data/output_data.json")
# 图片根目录
IMAGE_FOLDER = "images"

# 内存缓存：{ 'user1': [...data...], 'user2': [...data...] }
USER_DATA_CACHE = {}

def get_user_filename(username):
    """获取特定用户的数据文件路径"""
    # 例如: data/output_data_user1.json
    filename = f"output_data_{username}.json"
    return os.path.join("data", filename)

def load_data_for_current_user():
    """为当前用户加载数据"""
    uid = current_user.id
    
    # 1. 如果内存里已经有，直接返回
    if uid in USER_DATA_CACHE:
        return USER_DATA_CACHE[uid]
    
    user_file = get_user_filename(uid)
    
    # 2. 尝试加载用户专属文件
    if os.path.exists(user_file):
        try:
            with open(user_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                USER_DATA_CACHE[uid] = data
                return data
        except json.JSONDecodeError:
            print(f"User file {user_file} corrupted.")
    
    # 3. 如果用户文件不存在（第一次登录），加载基础模板文件
    if os.path.exists(BASE_DATA_PATH):
        try:
            with open(BASE_DATA_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 使用 deepcopy 防止修改影响到缓存中的模板
                USER_DATA_CACHE[uid] = copy.deepcopy(data) 
                return USER_DATA_CACHE[uid]
        except json.JSONDecodeError:
            print(f"Base file {BASE_DATA_PATH} corrupted.")
            
    # 4. 如果都没找到
    return []

def save_data_for_current_user():
    """将当前用户内存中的数据保存到硬盘"""
    uid = current_user.id
    if uid not in USER_DATA_CACHE:
        return "No data to save"
    
    user_file = get_user_filename(uid)
    try:
        with open(user_file, 'w', encoding='utf-8') as f:
            json.dump(USER_DATA_CACHE[uid], f, ensure_ascii=False, indent=4)
        return None # Success
    except Exception as e:
        return str(e)

@app.route('/')
@login_required
def index():
    # 获取属于当前用户的数据
    annotations = load_data_for_current_user()
    
    image_names = [item['image'] for item in annotations] if annotations else []
    
    if not annotations:
        return "No data found. Please ensure data/output_data.json exists as a template."

    current_img_name = request.args.get('img')
    if not current_img_name and image_names:
        current_img_name = image_names[0]

    current_data = next((item for item in annotations if item['image'] == current_img_name), None)
    
    if not current_data:
        return f"Image not found in your data: {current_img_name}"

    try:
        curr_idx = image_names.index(current_img_name)
    except ValueError:
        curr_idx = 0
    
    total = len(image_names)
    prev_img = image_names[(curr_idx - 1) % total]
    next_img = image_names[(curr_idx + 1) % total]

    return render_template('index.html', 
                           data=current_data, 
                           current_index=curr_idx + 1,
                           total=total,
                           prev_img=prev_img,
                           next_img=next_img)

@app.route('/annotate', methods=['POST'])
@login_required
def annotate():
    img_name = request.form.get('image_name')
    if not img_name:
        return "Error: Missing image name"

    # 获取表单数据
    new_concepts = [x for x in request.form.getlist('concepts') if x.strip()]
    new_attributes = [x for x in request.form.getlist('attributes') if x.strip()]
    
    raw_relations = request.form.get('relations', '[]')
    try:
        new_relations = json.loads(raw_relations)
    except:
        new_relations = [] 

    # 获取并更新当前用户的数据
    annotations = load_data_for_current_user()
    updated = False
    
    for item in annotations:
        if item['image'] == img_name:
            item['concepts'] = new_concepts
            item['attributes'] = new_attributes
            item['relations'] = new_relations
            updated = True
            break
    
    if updated:
        # 保存到用户专属文件
        err = save_data_for_current_user()
        if err:
            return f"Save Error: {err}"
    
    next_img = request.form.get('next_img_name')
    target = next_img if next_img else img_name
    return redirect(url_for('index', img=target))

# --- 4. 智能图片路由 ---
@app.route('/images/<path:filename>')
@login_required
def image_file(filename):
    full_path_direct = os.path.join(IMAGE_FOLDER, filename)
    if os.path.exists(full_path_direct):
        return send_from_directory(IMAGE_FOLDER, filename)
    
    filename_only = os.path.basename(filename)
    for root, dirs, files in os.walk(IMAGE_FOLDER):
        if filename_only in files:
            rel_dir = os.path.relpath(root, IMAGE_FOLDER)
            if rel_dir == '.':
                return send_from_directory(IMAGE_FOLDER, filename_only)
            else:
                return send_from_directory(os.path.join(IMAGE_FOLDER, rel_dir), filename_only)

    return "Image not found", 404

# --- 5. 下载接口 (下载当前用户的专属数据) ---
@app.route('/download')
@login_required
def download_data():
    """下载当前用户的 json 文件"""
    uid = current_user.id
    
    # 确保保存了最新的内存数据
    save_data_for_current_user()
    
    user_file = get_user_filename(uid)
    
    if os.path.exists(user_file):
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M')
        # 下载文件名例如: annotations_user1_20231125.json
        download_name = f"annotations_{uid}_{timestamp}.json"
        return send_file(user_file, as_attachment=True, download_name=download_name)
    elif os.path.exists(BASE_DATA_PATH):
        # 如果用户还没保存过，下载基础文件
        return send_file(BASE_DATA_PATH, as_attachment=True, download_name="base_template.json")
    else:
        return "No data available to download."

if __name__ == '__main__':
    os.makedirs(IMAGE_FOLDER, exist_ok=True)
    os.makedirs(os.path.dirname(BASE_DATA_PATH), exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)