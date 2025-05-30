import os
from flask import Flask, render_template, redirect, url_for, request, flash, session
from flask_pymongo import PyMongo
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from functools import wraps
from bson.objectid import ObjectId
from urllib.parse import urlparse, parse_qs

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)  # For production, use a fixed secret key!

# MongoDB URI from .env
app.config["MONGO_URI"] = os.getenv("MONGODB_URI")

mongo = PyMongo(app)

# Admin credentials from .env or fallback
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "hasan")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "anam")


# Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("Please log in first to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user') != ADMIN_USERNAME:
            flash("Admin access required.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def convert_to_embed_link(link):
    if "youtu.be/" in link:
        video_id = link.split("youtu.be/")[1].split("?")[0]
        si_value = parse_qs(urlparse(link).query).get("si", [""])[0]
        return f"https://www.youtube.com/embed/{video_id}?si={si_value}" if si_value else f"https://www.youtube.com/embed/{video_id}"
    
    elif "youtube.com/watch" in link:
        parsed_url = urlparse(link)
        video_id = parse_qs(parsed_url.query).get("v", [""])[0]
        si_value = parse_qs(parsed_url.query).get("si", [""])[0]
        return f"https://www.youtube.com/embed/{video_id}?si={si_value}" if si_value else f"https://www.youtube.com/embed/{video_id}"

    return link


# Routes

@app.route('/')
def home():
    seasons = list(mongo.db.seasons.find())
    selected_season = request.args.get('season') or session.get('selected_season') or '3'
    session['selected_season'] = selected_season
    posts = list(mongo.db.posts.find({"season_id": int(selected_season)}))
    return render_template('home.html', seasons=seasons, selected_season=selected_season, posts=posts)

@app.route('/class')
@login_required
def class_page():
    season_id = request.args.get('season') or session.get('selected_season') or '3'
    classes = list(mongo.db.classes.find({"season_id": int(season_id)}))

    # Convert link to embed format
    for cls in classes:
        if "link" in cls:
            cls["embed_link"] = convert_to_embed_link(cls["link"])

    return render_template('class.html', classes=classes, season_id=season_id)



@app.route('/notes')
@login_required
def notes_page():
    season_id = request.args.get('season') or session.get('selected_season') or '3'
    notes = list(mongo.db.notes.find({"season_id": int(season_id)}))
    return render_template('notes.html', notes=notes, season_id=season_id)

@app.route('/exams')
@login_required
def exams_page():
    season_id = request.args.get('season') or session.get('selected_season') or '3'
    exams = list(mongo.db.exams.find({"season_id": int(season_id)}))
    return render_template('exams.html', exams=exams, season_id=season_id)

@app.route('/members')
def members_page():
    members = list(mongo.db.members.find())
    return render_template('members.html', members=members)

# Admin panel page
@app.route('/admin')
@admin_required
def admin_page():
    seasons = list(mongo.db.seasons.find())
    members = list(mongo.db.members.find())
    classes = list(mongo.db.classes.find())
    notes = list(mongo.db.notes.find())
    posts = list(mongo.db.posts.find())
    exams = list(mongo.db.exams.find())

    return render_template('admin.html', seasons=seasons, members=members,
                           classes=classes, notes=notes, posts=posts, exams=exams)


# --- Admin POST routes for form submissions ---

@app.route('/admin/add_member', methods=['POST'])
@admin_required
def admin_add_member():
    name = request.form.get('name')
    role = request.form.get('role')
    contact = request.form.get('contact')
    photo = request.files.get('photo')

    if not (name and role and contact and photo):
        flash("All fields are required for adding a member.", "danger")
        return redirect(url_for('admin_page'))

    # Save photo to static folder (ensure folder exists)
    photo_filename = None
    if photo:
        filename = photo.filename
        ext = os.path.splitext(filename)[1]
        photo_filename = f"member_{name.lower().replace(' ', '_')}{ext}"
        save_path = os.path.join('static', 'uploads', 'members')
        os.makedirs(save_path, exist_ok=True)
        photo.save(os.path.join(save_path, photo_filename))

    member_data = {
        "name": name,
        "role": role,
        "contact": contact,
        "photo_url": url_for('static', filename=f"uploads/members/{photo_filename}")
    }
    mongo.db.members.insert_one(member_data)
    flash(f"Member '{name}' added successfully.", "success")
    return redirect(url_for('admin_page'))


@app.route('/admin/add_season', methods=['POST'])
@admin_required
def admin_add_season():
    try:
        season_id = int(request.form.get('season_id'))
    except (ValueError, TypeError):
        flash("Invalid Season ID.", "danger")
        return redirect(url_for('admin_page'))

    title = request.form.get('title')
    description = request.form.get('description')

    if not (title):
        flash("Season Title is required.", "danger")
        return redirect(url_for('admin_page'))

    season_data = {
        "season_id": season_id,
        "title": title,
        "description": description or ""
    }
    mongo.db.seasons.insert_one(season_data)
    flash(f"Season '{title}' added successfully.", "success")
    return redirect(url_for('admin_page'))


@app.route('/admin/add_class', methods=['POST'])
@admin_required
def admin_add_class():
    try:
        season_id = int(request.form.get('season_id'))
    except (ValueError, TypeError):
        flash("Invalid Season ID.", "danger")
        return redirect(url_for('admin_page'))

    class_name = request.form.get('class_name')
    description = request.form.get('description')
    link = request.form.get('link')

    if not class_name:
        flash("Class Name is required.", "danger")
        return redirect(url_for('admin_page'))

    class_data = {
        "season_id": season_id,
        "class_name": class_name,
        "description": description or "",
    }

    if link:
        class_data["link"] = convert_to_embed_link(link.strip())

    mongo.db.classes.insert_one(class_data)
    flash(f"Class '{class_name}' added successfully.", "success")
    return redirect(url_for('admin_page'))




@app.route('/admin/add_note', methods=['POST'])
@admin_required
def admin_add_note():
    try:
        season_id = int(request.form.get('season_id'))
    except (ValueError, TypeError):
        flash("Invalid Season ID.", "danger")
        return redirect(url_for('admin_page'))

    title = request.form.get('title')
    drive_link = request.form.get('drive_link')
    description = request.form.get('description')

    if not (title and drive_link):
        flash("Note Title and Drive Link are required.", "danger")
        return redirect(url_for('admin_page'))

    note_data = {
        "season_id": season_id,
        "title": title,
        "drive_link": drive_link,
        "description": description or ""
    }
    mongo.db.notes.insert_one(note_data)
    flash(f"Note '{title}' added successfully.", "success")
    return redirect(url_for('admin_page'))


@app.route('/admin/add_post', methods=['POST'])
@admin_required
def admin_add_post():
    try:
        season_id = int(request.form.get('season_id'))
    except (ValueError, TypeError):
        flash("Invalid Season ID.", "danger")
        return redirect(url_for('admin_page'))

    title = request.form.get('title')
    enroll_link = request.form.get('enroll_link')
    image_url = request.form.get('image_url')

    if not (title and enroll_link and image_url):
        flash("Post Title, Enroll Link, and Image URL are required.", "danger")
        return redirect(url_for('admin_page'))

    post_data = {
        "season_id": season_id,
        "title": title,
        "enroll_link": enroll_link,
        "image_url": image_url
    }
    mongo.db.posts.insert_one(post_data)
    flash(f"Post '{title}' added successfully.", "success")
    return redirect(url_for('admin_page'))


@app.route('/admin/add_exam', methods=['POST'])
@login_required
def admin_add_exam():
    title = request.form.get('title')
    link = request.form.get('link')
    season_id = int(request.form.get('season_id'))

    mongo.db.exams.insert_one({
        "title": title,
        "link": link,
        "season_id": season_id
    })

    flash('Exam added successfully!', 'success')
    return redirect(url_for('admin_page'))  # Adjust redirect target as needed



# Login route
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        # Admin login check
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['user'] = ADMIN_USERNAME
            session['selected_season'] = '3'  # Set default season
            flash("Admin logged in successfully.", "success")
            return redirect(url_for('admin_page'))

        # User login check in DB
        user = mongo.db.users.find_one({"username": username})
        if user and check_password_hash(user.get('password_hash', ''), password):
            if user.get('student', False) and user.get('approved', False):
                session['user'] = username
                session['selected_season'] = '3'  # Set default season
                flash("Logged in successfully.", "success")
                return redirect(url_for('home'))
            else:
                flash("Your account is not approved by admin yet.", "warning")
        else:
            flash("Invalid username or password.", "danger")

    return render_template('login.html')

# Logout
@app.route('/logout')
def logout():
    session.pop('user', None)
    flash("Logged out successfully.", "info")
    return redirect(url_for('home'))


# Registration route
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username').strip()
        password = request.form.get('password')
        email = request.form.get('email').strip()

        if mongo.db.users.find_one({"username": username}):
            flash("Username already exists. Please choose another.", "danger")
            return redirect(url_for('register'))

        pw_hash = generate_password_hash(password)
        mongo.db.users.insert_one({
            "username": username,
            "password_hash": pw_hash,
            "email": email,
            "student": False,
            "approved": False,
            "courses_access": []
        })
        flash("Registration successful! Please wait for admin approval.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/admin/exam-center', methods=['GET', 'POST'])
@admin_required
def admin_exam_center():
    if request.method == 'POST':
        exam_title = request.form['exam_title']
        max_attempts = int(request.form['max_attempts'])
        questions = []

        form_dict = request.form.to_dict(flat=False)

        i = 0
        while True:
            q_key = f'questions[{i}][question]'
            if q_key not in form_dict:
                break
            question = form_dict[q_key][0]
            option1 = form_dict.get(f'questions[{i}][option1]', [''])[0]
            option2 = form_dict.get(f'questions[{i}][option2]', [''])[0]
            option3 = form_dict.get(f'questions[{i}][option3]', [''])[0]
            option4 = form_dict.get(f'questions[{i}][option4]', [''])[0]
            answer = form_dict.get(f'questions[{i}][answer]', [''])[0]

            questions.append({
                'question': question,
                'options': [option1, option2, option3, option4],
                'answer': answer
            })
            i += 1

        # TODO: Save exam to DB/storage here
        # Example: save_exam_to_db(exam_title, max_attempts, questions)

        flash("Exam added successfully!", "success")
        return redirect(url_for('admin_exam_center'))

    return render_template('admin_exam_center.html')


@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True)


