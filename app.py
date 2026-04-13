from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_socketio import SocketIO, emit, join_room, leave_room
from sqlalchemy import text, or_
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os, re
from datetime import datetime

app = Flask(__name__)

# Ensure instance folder exists and use an absolute SQLite path
os.makedirs(app.instance_path, exist_ok=True)
db_path = os.path.join(app.instance_path, 'lost_and_found.db')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + db_path
app.secret_key = os.environ.get('SESSION_SECRET', 'secretkey-change-in-production')

# Uploads & Database Config
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploaded')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
socketio = SocketIO(
    app,
    cors_allowed_origins="*",
    async_mode='threading',
    logger=False,
    engineio_logger=False,
    ping_timeout=60,
    ping_interval=25,
    allow_upgrades=True,
    transports=['websocket', 'polling']
)

# Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Track online users {user_id: True}
online_users: set = set()

# -----------------------
# MODELS
# -----------------------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20))
    password_hash = db.Column(db.String(128), nullable=False)

    sent_messages = db.relationship('Message', back_populates='sender', foreign_keys='Message.sender_id', lazy='dynamic')
    received_messages = db.relationship('Message', back_populates='receiver', foreign_keys='Message.receiver_id', lazy='dynamic')
    comments = db.relationship('Comment', backref='user', lazy='dynamic')
    lost_items = db.relationship('LostItem', backref='user', lazy='dynamic')
    found_items = db.relationship('FoundItem', backref='user', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_type = db.Column(db.String(10))  # lost/found
    item_id = db.Column(db.Integer)
    is_read = db.Column(db.Boolean, default=False)

    sender = db.relationship('User', back_populates='sent_messages', foreign_keys=[sender_id])
    receiver = db.relationship('User', back_populates='received_messages', foreign_keys=[receiver_id])

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lost_item_id = db.Column(db.Integer, db.ForeignKey('lost_item.id'))
    found_item_id = db.Column(db.Integer, db.ForeignKey('found_item.id'))
    replies = db.relationship('CommentReply', backref='comment',
                              lazy='dynamic', cascade='all, delete-orphan')

class CommentReply(db.Model):
    """A reply to a specific comment, optionally @mentioning the original commenter."""
    id          = db.Column(db.Integer, primary_key=True)
    content     = db.Column(db.Text, nullable=False)
    mention     = db.Column(db.String(120))          # username that was @mentioned
    timestamp   = db.Column(db.DateTime, default=datetime.utcnow)
    user_id     = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    comment_id  = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=False)
    user        = db.relationship('User')

class LostItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))
    location = db.Column(db.String(200))
    image = db.Column(db.String(120), nullable=False)
    date_lost = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    comments = db.relationship('Comment', backref='lost_item', lazy='dynamic')

class FoundItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    image = db.Column(db.String(120), nullable=False)
    date_found = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    comments = db.relationship('Comment', backref='found_item', lazy='dynamic')

class Story(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User')

# -----------------------
# NOTIFICATION MODEL
# type: 'message' | 'comment' | 'lost_post' | 'found_post' | 'general'
# -----------------------
class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(30), default='general')
    link = db.Column(db.String(200), default='/')
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Report Model
class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer)
    reason = db.Column(db.String(200))


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

# -----------------------
# ADMIN SYSTEM
# -----------------------
ADMIN_EMAILS = {
    "admin@diu.edu.bd",
}

def require_admin():
    if not current_user.is_authenticated:
        abort(403)
    if current_user.email not in ADMIN_EMAILS:
        abort(403)

# -----------------------
# NOTIFICATION HELPER
# -----------------------
def create_notification(user_id, msg, notif_type='general', link='/'):
    """
    Creates a Notification record.
    Call db.session.commit() AFTER calling this function.

    Args:
        user_id    – who receives the notification
        msg        – short text shown in the dropdown / page
        notif_type – 'message' | 'comment' | 'lost_post' | 'found_post' | 'general'
        link       – URL opened when the user clicks the notification
    """
    note = Notification(user_id=user_id, message=msg, type=notif_type, link=link)
    db.session.add(note)


# -----------------------
# ROUTES
# -----------------------

@app.route('/')
def get_started():
    return render_template("get_started.html")

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/home')
def home():
    q = request.args.get('q', '').strip()
    lost_query = LostItem.query
    found_query = FoundItem.query
    if q:
        lost_query = lost_query.filter(
            (LostItem.title.ilike(f"%{q}%")) |
            (LostItem.description.ilike(f"%{q}%")) |
            (LostItem.category.ilike(f"%{q}%")) |
            (LostItem.location.ilike(f"%{q}%"))
        )
        found_query = found_query.filter(
            (FoundItem.title.ilike(f"%{q}%")) |
            (FoundItem.description.ilike(f"%{q}%"))
        )
    lost_items = lost_query.order_by(LostItem.date_lost.desc()).all()
    found_items = found_query.order_by(FoundItem.date_found.desc()).all()
    comments = Comment.query.order_by(Comment.timestamp.desc()).all()
    return render_template('index.html', lost=lost_items, found=found_items, comments=comments, q=q)

@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    lost_results = []
    found_results = []
    story_results = []

    if q:
        lost_results = LostItem.query.filter(
            (LostItem.title.ilike(f"%{q}%")) |
            (LostItem.description.ilike(f"%{q}%")) |
            (LostItem.category.ilike(f"%{q}%")) |
            (LostItem.location.ilike(f"%{q}%"))
        ).order_by(LostItem.date_lost.desc()).all()

        found_results = FoundItem.query.filter(
            (FoundItem.title.ilike(f"%{q}%")) |
            (FoundItem.description.ilike(f"%{q}%"))
        ).order_by(FoundItem.date_found.desc()).all()

        story_results = Story.query.filter(
            (Story.title.ilike(f"%{q}%")) |
            (Story.content.ilike(f"%{q}%"))
        ).order_by(Story.timestamp.desc()).all()

    total = len(lost_results) + len(found_results) + len(story_results)
    return render_template('search.html',
                           q=q,
                           lost=lost_results,
                           found=found_results,
                           stories=story_results,
                           total=total)

@app.route('/stories')
def stories():
    all_stories = Story.query.order_by(Story.timestamp.desc()).all()
    return render_template('stories.html', stories=all_stories)

@app.route('/share_story', methods=['GET', 'POST'])
@login_required
def share_story():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        new_story = Story(title=title, content=content, user_id=current_user.id)
        db.session.add(new_story)
        db.session.flush()

        # Notify all other users that a new story was shared
        other_users = User.query.filter(User.id != current_user.id).all()
        for u in other_users:
            create_notification(
                user_id=u.id,
                msg=f"📖 {current_user.email} shared a new story: \"{title}\"",
                notif_type='story',
                link='/stories'
            )

        db.session.commit()
        flash('Your story has been shared!')
        return redirect(url_for('stories'))
    return render_template('share_story.html')

@app.route('/stories_wall')
def stories_wall():
    stories = Story.query.order_by(Story.timestamp.desc()).all()
    return render_template('stories_wall.html', stories=stories)

@app.route('/submit_story', methods=['GET', 'POST'])
@login_required
def submit_story():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        new_story = Story(title=title, content=content, user_id=current_user.id)
        db.session.add(new_story)
        db.session.flush()

        # Notify all other users that a new story was submitted
        other_users = User.query.filter(User.id != current_user.id).all()
        for u in other_users:
            create_notification(
                user_id=u.id,
                msg=f"📖 {current_user.email} posted a new story: \"{title}\"",
                notif_type='story',
                link='/stories_wall'
            )

        db.session.commit()
        return redirect(url_for('stories_wall'))
    return render_template('submit_story.html')

@app.route('/chatbot', methods=['POST'])
def chatbot():
    user_message = request.json.get('message', '').lower()
    if "lost" in user_message:
        reply = "To report a lost item, go to 'Post Lost Item' and fill in the form."
    elif "found" in user_message:
        reply = "To report a found item, click on 'Post Found Item' and provide details."
    elif "search" in user_message:
        reply = "To search items, use the 'Search Lost' or 'Search Found' section."
    elif "delete item" in user_message:
        reply = "To delete your post, go to your dashboard and click the delete icon."
    elif "edit" in user_message:
        reply = "To edit your item, click the edit button on your post in the dashboard."
    elif "help" in user_message:
        reply = "I can help you report, search, or view items. Try typing 'lost', 'found', or 'search'."
    else:
        reply = "I'm not sure how to help with that. Try typing 'lost', 'found', or 'search'."
    return jsonify({'reply': reply})

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/post_lost', methods=['GET', 'POST'])
@login_required
def post_lost():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        location = request.form['location']
        image = request.files['image']
        if image.filename == '':
            flash('No image selected!')
            return redirect(request.url)
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        lost_item = LostItem(title=title, description=description, category=category,
                             location=location, image=filename, user_id=current_user.id)
        db.session.add(lost_item)
        db.session.flush()  # get id before commit

        # Notify all other registered users
        other_users = User.query.filter(User.id != current_user.id).all()
        for u in other_users:
            create_notification(
                user_id=u.id,
                msg=f"🔍 {current_user.email} posted a new lost item: \"{title}\"",
                notif_type='lost_post',
                link='/home'
            )

        db.session.commit()
        flash('Lost item posted successfully!')
        return redirect(url_for('home'))
    return render_template('post_lost.html')

@app.route('/post_found', methods=['GET', 'POST'])
@login_required
def post_found():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        image = request.files['image']
        if image.filename == '':
            flash('No image selected!')
            return redirect(request.url)
        filename = secure_filename(image.filename)
        image.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        found_item = FoundItem(title=title, description=description,
                               image=filename, user_id=current_user.id)
        db.session.add(found_item)
        db.session.flush()

        # Notify all other registered users
        other_users = User.query.filter(User.id != current_user.id).all()
        for u in other_users:
            create_notification(
                user_id=u.id,
                msg=f"✅ {current_user.email} reported a found item: \"{title}\"",
                notif_type='found_post',
                link='/home'
            )

        db.session.commit()
        flash('Found item posted successfully!')
        return redirect(url_for('home'))
    return render_template('post_found.html')

@app.route('/add_comment/<item_type>/<int:item_id>', methods=['POST'])
@login_required
def add_comment(item_type, item_id):
    content = request.form['content']
    if not content:
        flash("Comment cannot be empty.")
        return redirect(url_for('home'))

    comment = Comment(content=content, user_id=current_user.id)
    owner_id = None

    if item_type == 'lost':
        comment.lost_item_id = item_id
        item = LostItem.query.get(item_id)
        if item:
            owner_id = item.user_id
    elif item_type == 'found':
        comment.found_item_id = item_id
        item = FoundItem.query.get(item_id)
        if item:
            owner_id = item.user_id

    db.session.add(comment)

    # Notify the item owner (skip if they commented on their own item)
    if owner_id and owner_id != current_user.id:
        create_notification(
            user_id=owner_id,
            msg=f"💬 {current_user.email} commented on your {item_type} item.",
            notif_type='comment',
            link='/home'
        )

    db.session.commit()
    flash("Comment added!")
    return redirect(url_for('home'))

@app.route('/reply_comment/<int:comment_id>', methods=['POST'])
@login_required
def reply_comment(comment_id):
    content = request.form.get('content', '').strip()
    mention = request.form.get('mention', '').strip()

    if not content:
        flash("Reply cannot be empty.")
        return redirect(url_for('home'))

    comment = Comment.query.get_or_404(comment_id)
    reply = CommentReply(
        content=content,
        mention=mention,
        user_id=current_user.id,
        comment_id=comment_id
    )
    db.session.add(reply)

    # Notify the original commenter (not yourself)
    if comment.user_id != current_user.id:
        create_notification(
            user_id=comment.user_id,
            msg=f"↩️ {current_user.email} replied to your comment: \"{content[:60]}\"",
            notif_type='comment',
            link='/home'
        )

    db.session.commit()
    return redirect(url_for('home'))

@app.route('/contact_owner/<item_type>/<int:item_id>')
@login_required
def contact_owner(item_type, item_id):
    return render_template("contact_owner.html", item_type=item_type, item_id=item_id)

@app.route('/send_message/<item_type>/<int:item_id>', methods=['POST'])
@login_required
def send_message(item_type, item_id):
    content = request.form['content']
    if item_type == 'lost':
        item = LostItem.query.get_or_404(item_id)
    else:
        item = FoundItem.query.get_or_404(item_id)

    receiver = item.user
    msg = Message(content=content, sender_id=current_user.id, receiver_id=receiver.id,
                  item_type=item_type, item_id=item_id)
    db.session.add(msg)

    # Notify the receiver about the new message
    create_notification(
        user_id=receiver.id,
        msg=f"📩 {current_user.email} sent you a message about your {item_type} item.",
        notif_type='message',
        link='/inbox'
    )

    db.session.commit()
    flash('Your message has been sent!')
    return redirect(url_for('home'))

@app.route('/inbox')
@login_required
def inbox():
    # Gather all messages involving current user
    all_msgs = Message.query.filter(
        or_(Message.sender_id == current_user.id,
            Message.receiver_id == current_user.id)
    ).order_by(Message.timestamp.desc()).all()

    # Group by the "other" user, keeping only the latest per conversation
    conversations = {}
    for msg in all_msgs:
        other_id = msg.receiver_id if msg.sender_id == current_user.id else msg.sender_id
        if other_id not in conversations:
            conversations[other_id] = {
                'user': db.session.get(User, other_id),
                'last': msg,
                'unread': 0,
            }
        if msg.receiver_id == current_user.id and not msg.is_read:
            conversations[other_id]['unread'] += 1

    convs = sorted(conversations.values(), key=lambda c: c['last'].timestamp, reverse=True)
    return render_template('inbox.html', conversations=convs, online_users=online_users)

@app.route('/messages')
@login_required
def messages():
    users = User.query.filter(User.id != current_user.id).all()
    return render_template('messages.html', users=users, online_users=online_users)

@app.route('/chat/<int:user_id>')
@login_required
def chat(user_id):
    other = db.session.get(User, user_id) or abort(404)
    # Mark messages from other user as read
    Message.query.filter_by(sender_id=user_id,
                            receiver_id=current_user.id,
                            is_read=False).update({'is_read': True})
    db.session.commit()

    sent     = Message.query.filter_by(sender_id=current_user.id, receiver_id=user_id)
    received = Message.query.filter_by(sender_id=user_id, receiver_id=current_user.id)
    all_msgs = sent.union(received).order_by(Message.timestamp.asc()).all()

    # SocketIO room name is deterministic — sorted user IDs
    room = f"chat_{min(current_user.id, user_id)}_{max(current_user.id, user_id)}"
    all_users = User.query.filter(User.id != current_user.id).all()
    return render_template('chat.html', other=other, messages=all_msgs,
                           room=room, online_users=online_users, all_users=all_users)

# -----------------------
# ADMIN ROUTES
# -----------------------
@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    require_admin()
    lost_items = LostItem.query.order_by(LostItem.date_lost.desc()).all()
    found_items = FoundItem.query.order_by(FoundItem.date_found.desc()).all()
    stories = Story.query.order_by(Story.timestamp.desc()).all()
    return render_template('admin_dashboard.html', lost=lost_items, found=found_items, stories=stories)

@app.route('/admin/reports')
@login_required
def admin_reports():
    require_admin()
    comments = Comment.query.order_by(Comment.timestamp.desc()).all()
    messages_all = Message.query.order_by(Message.timestamp.desc()).all()
    stories = Story.query.order_by(Story.timestamp.desc()).all()
    return render_template('admin_reports.html', comments=comments, messages=messages_all, stories=stories)

@app.route('/admin/delete/lost/<int:item_id>')
@login_required
def admin_delete_lost(item_id):
    require_admin()
    item = LostItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Lost post deleted.")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/found/<int:item_id>')
@login_required
def admin_delete_found(item_id):
    require_admin()
    item = FoundItem.query.get_or_404(item_id)
    db.session.delete(item)
    db.session.commit()
    flash("Found post deleted.")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/story/<int:story_id>')
@login_required
def admin_delete_story(story_id):
    require_admin()
    s = Story.query.get_or_404(story_id)
    db.session.delete(s)
    db.session.commit()
    flash("Story deleted.")
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete/comment/<int:comment_id>')
@login_required
def admin_delete_comment(comment_id):
    require_admin()
    c = Comment.query.get_or_404(comment_id)
    db.session.delete(c)
    db.session.commit()
    flash("Comment deleted.")
    return redirect(url_for('admin_reports'))

# -----------------------
# AUTH
# -----------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    error = None
    if request.method == 'POST':
        email    = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=request.form.get('remember') == 'on')
            return redirect(url_for('home'))
        else:
            error = 'The email or password you entered is incorrect.'
    return render_template('login.html', error=error)

@app.route('/logout')
@login_required
def logout():
    online_users.discard(current_user.id)
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    errors = {}
    form = {}
    if request.method == 'POST':
        fname    = request.form.get('first_name', '').strip()
        lname    = request.form.get('last_name', '').strip()
        email    = request.form.get('email', '').strip()
        phone    = request.form.get('phone', '').strip()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        form = {'first_name': fname, 'last_name': lname, 'email': email, 'phone': phone}

        if not fname:
            errors['first_name'] = 'First name is required.'
        if not lname:
            errors['last_name'] = 'Last name is required.'
        if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
            errors['email'] = 'Enter a valid email address.'
        elif User.query.filter_by(email=email).first():
            errors['email'] = 'This email is already registered.'
        if len(password) < 8:
            errors['password'] = 'Password must be at least 8 characters.'
        elif password != confirm:
            errors['confirm_password'] = 'Passwords do not match.'

        if not errors:
            user = User(name=f"{fname} {lname}", email=email, phone=phone)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('home'))
    return render_template('register.html', errors=errors, form=form)

# -----------------------
# NOTIFICATION ROUTES
# -----------------------

@app.route('/notifications')
@login_required
def notifications():
    """Full-page view of all notifications, marks them all as read on visit."""
    notes = (Notification.query
             .filter_by(user_id=current_user.id)
             .order_by(Notification.created_at.desc())
             .all())
    for n in notes:
        n.is_read = True
    db.session.commit()
    return render_template('notifications.html', notes=notes)

@app.route('/messages/unread-count')
@login_required
def messages_unread_count():
    """AJAX – returns unread message count for the chat icon badge."""
    count = Message.query.filter_by(receiver_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})

@app.route('/notifications/count')
@login_required
def notifications_count():
    """AJAX – returns JSON with unread notification count for the bell badge."""
    count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).count()
    return jsonify({'count': count})

@app.route('/notifications/recent')
@login_required
def notifications_recent():
    """AJAX – returns the 8 most recent notifications as JSON for the dropdown."""
    notes = (Notification.query
             .filter_by(user_id=current_user.id)
             .order_by(Notification.created_at.desc())
             .limit(8).all())
    data = [{
        'id': n.id,
        'message': n.message,
        'type': n.type,
        'link': n.link,
        'is_read': n.is_read,
        'created_at': n.created_at.strftime('%d %b, %I:%M %p')
    } for n in notes]
    return jsonify(data)

@app.route('/notifications/mark-read/<int:notif_id>', methods=['POST'])
@login_required
def mark_notification_read(notif_id):
    """AJAX – marks a single notification as read when clicked."""
    note = Notification.query.get_or_404(notif_id)
    if note.user_id == current_user.id:
        note.is_read = True
        db.session.commit()
    return jsonify({'success': True, 'link': note.link})

@app.route('/notifications/mark-all-read', methods=['POST'])
@login_required
def mark_all_notifications_read():
    """AJAX – marks every unread notification as read."""
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})

# Report Item
@app.route('/report/<int:item_id>', methods=['GET', 'POST'])
@login_required
def report(item_id):
    if request.method == 'POST':
        reason = request.form['reason']
        rep = Report(item_id=item_id, reason=reason)
        db.session.add(rep)
        db.session.commit()
        return redirect(url_for('home'))
    return render_template('report.html', item_id=item_id)


def run_db_migrations():
    """Auto-add missing columns so old databases keep working."""
    with db.engine.connect() as conn:
        migration_sqls = [
            "ALTER TABLE notification ADD COLUMN type VARCHAR(30) DEFAULT 'general'",
            "ALTER TABLE notification ADD COLUMN link VARCHAR(200) DEFAULT '/'",
            "ALTER TABLE notification ADD COLUMN created_at DATETIME",
            "ALTER TABLE message ADD COLUMN is_read BOOLEAN DEFAULT 0",
            "ALTER TABLE user ADD COLUMN name VARCHAR(100)",
        ]
        for sql in migration_sqls:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # column already exists — skip

# ─────────────────────────────────────────────────────────
# SOCKET.IO EVENT HANDLERS
# ─────────────────────────────────────────────────────────

@socketio.on('connect')
def on_connect():
    if current_user.is_authenticated:
        online_users.add(current_user.id)
        emit('user_online', {'user_id': current_user.id}, broadcast=True)

@socketio.on('disconnect')
def on_disconnect():
    if current_user.is_authenticated:
        online_users.discard(current_user.id)
        emit('user_offline', {'user_id': current_user.id}, broadcast=True)

@socketio.on('join')
def on_join(data):
    room = data.get('room')
    if room:
        join_room(room)

@socketio.on('leave')
def on_leave(data):
    room = data.get('room')
    if room:
        leave_room(room)

@socketio.on('send_message')
def on_send_message(data):
    if not current_user.is_authenticated:
        return
    room        = data.get('room', '')
    content     = data.get('content', '').strip()
    receiver_id = int(data.get('receiver_id', 0))
    if not content or not receiver_id:
        return

    msg = Message(sender_id=current_user.id, receiver_id=receiver_id,
                  content=content, is_read=False)
    db.session.add(msg)

    create_notification(
        user_id=receiver_id,
        msg=f"📩 {current_user.name or current_user.email} sent you a message.",
        notif_type='message',
        link='/inbox'
    )

    db.session.commit()

    sender_name = current_user.name or current_user.email.split('@')[0]
    emit('new_message', {
        'msg_id':      msg.id,
        'sender_id':   current_user.id,
        'sender_name': sender_name,
        'content':     content,
        'timestamp':   msg.timestamp.strftime('%I:%M %p'),
    }, room=room)

@socketio.on('typing')
def on_typing(data):
    if current_user.is_authenticated:
        room = data.get('room', '')
        name = current_user.name or current_user.email.split('@')[0]
        emit('typing', {'name': name}, room=room, include_self=False)

@socketio.on('stop_typing')
def on_stop_typing(data):
    if current_user.is_authenticated:
        emit('stop_typing', {}, room=data.get('room', ''), include_self=False)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    with app.app_context():
        db.create_all()
        run_db_migrations()
    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=False,
        allow_unsafe_werkzeug=True
    )

