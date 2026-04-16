# 🏫 DIU Lost & Found Management System

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Python](https://img.shields.io/badge/Python-3.11%2B-green)
![Flask](https://img.shields.io/badge/Flask-3.0.3-red)
![License](https://img.shields.io/badge/license-MIT-yellow)

## 📌 Project Overview

The **DIU Lost & Found Management System** is a web-based platform designed specifically for **Daffodil International University** students to help them recover lost belongings and report found items easily. Instead of relying on scattered Facebook groups, this system provides a **centralized, secure, and user-friendly** solution.

### 🎯 Key Features

| Feature | Description |
|---------|-------------|
| 🔍 **Post Lost Items** | Add lost items with title, description, category, location, and image |
| ✅ **Post Found Items** | Report found items with title, description, and image |
| 💬 **Real-time Messaging** | Chat with other users instantly using Socket.IO |
| 📝 **Comments & Replies** | Interact on posts with @mention support |
| 🔔 **Live Notifications** | Get instant alerts for messages and comments |
| 📖 **Success Stories** | Share and read recovery success stories |
| 🛡️ **Admin Moderation** | Admin can delete inappropriate posts and comments |
| 🌓 **Dark/Light Mode** | Toggle between themes for comfortable viewing |
| 📱 **Mobile Responsive** | Works perfectly on all devices |

---

## 🚀 Live Demo

> *Currently running on localhost. Deployment planned on Render/PythonAnywhere.*

| User Type | Email | Password |
|-----------|-------|----------|
| Admin | admin@diu.edu.bd | (Set during registration) |
| Regular User | Register with your DIU email | Your chosen password |

---

## 🛠️ Technologies Used

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| Python | 3.11+ | Core programming language |
| Flask | 3.0.3 | Web framework |
| Flask-SQLAlchemy | 3.1.1 | ORM for database operations |
| Flask-Login | 0.6.3 | User authentication & session management |
| Flask-SocketIO | 5.3.6 | Real-time bidirectional communication |
| Werkzeug | 3.0.3 | Password hashing & secure file handling |

### Frontend
| Technology | Purpose |
|------------|---------|
| HTML5 | Structure |
| CSS3 | Styling |
| TailwindCSS | Utility-first CSS framework |
| Bootstrap 5 | Responsive components |
| Jinja2 | Template engine |
| JavaScript | Client-side interactivity |

### Database
| Technology | Purpose |
|------------|---------|
| SQLite | Lightweight relational database |
| SQLAlchemy ORM | Object-relational mapping |

---
📋 README.md-এর জন্য Installation Process (কপি করার জন্য):
markdown
## 🔧 Installation & Setup Guide

### Prerequisites

| Software | Version | How to Check |
|----------|---------|--------------|
| Python | 3.11 or higher | `python --version` |
| pip | Latest | `pip --version` |

---

### Step 1: Download the Project

```bash
git clone https://github.com/yourusername/DIU-Lost-And-Found.git
cd DIU-Lost-And-Found
No Git? Download ZIP directly and extract.

Step 2: Create Virtual Environment
⚠️ Important for Flask projects

Windows:

bash
python -m venv venv
venv\Scripts\activate
Mac / Linux:

bash
python3 -m venv venv
source venv/bin/activate
✅ After activation, you will see (venv) in your terminal.

Step 3: Install Dependencies
bash
pip install -r requirements.txt
If requirements.txt is missing, install manually:

bash
pip install Flask==3.0.3
pip install Flask-SQLAlchemy==3.1.1
pip install Flask-Login==0.6.3
pip install Flask-SocketIO==5.3.6
pip install Werkzeug==3.0.3
pip install python-dotenv==1.0.1
pip install simple-websocket
Step 4: Create Database
bash
python create_db.py
Expected output:

text
Database and tables created/migrated successfully.
Step 5: Run the Application
bash
python app.py
Expected output:


* Serving Flask app 'app'
* Running on http://127.0.0.1:5000
Step 6: Open in Browser
Go to: http://127.0.0.1:5000

Step 7: Create Account
Click Register

Fill your details

Click Sign Up

✅ Done! You can now use the system.

Step 8: Stop the Server
Press Ctrl + C in the terminal.

To start again later:

bash
venv\Scripts\activate   # Windows
# OR
source venv/bin/activate  # Mac/Linux

python app.py
🚀 Quick Installation (One by One)
Windows:
bash
git clone https://github.com/yourusername/DIU-Lost-And-Found.git
cd DIU-Lost-And-Found
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python create_db.py
python app.py
Mac / Linux:
bash
git clone https://github.com/yourusername/DIU-Lost-And-Found.git
cd DIU-Lost-And-Found
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 create_db.py
python3 app.py
❓ Troubleshooting
Problem	Solution
'python' not recognized	Reinstall Python and check ✅ "Add to PATH"
Module not found	Activate venv first, then pip install -r requirements.txt
Port 5000 in use	Change port in app.py or close other programs
Database error	Delete instance/lost_and_found.db → Run python create_db.py again
SocketIO not working	Run pip install simple-websocket
📌 Important Notes
Topic	Note
Virtual Environment	MUST activate every time before running
Keep Terminal Open	Don't close while using the website
Database File	Located in instance/lost_and_found.db
Uploaded Images	Saved in uploaded/ folder
