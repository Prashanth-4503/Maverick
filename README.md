# MaveRick Coding Platform – Hackathon Portal

### Team: 404Error

**Install dependencies in one go:**

```bash
pip install django reportlab pillow requests django-unfold "bw2io[multifunctional]" PyPDF2 celery
```

A **gamified coding and hackathon platform** built with Django ⚡.
This portal empowers developers to **learn, practice, and compete** with secure authentication, problem management, leaderboards, and a full admin panel.

---

## ✨ Features

* 🔐 **Authentication System** – Register/Login with Django auth
* 🛠️ **Admin Panel** – Manage problems, users, submissions
* 📝 **Quiz/MCQ Engine** – Auto-grading support
* 💾 **Submission Tracking** – Store and evaluate code attempts
* 📊 **Leaderboard** – Rank users by performance
* 🎨 **Custom UI Templates** – Responsive frontend with Bootstrap/Tailwind
* 📦 **Static & Media Handling** – Organized assets
* ☁️ **Deployment Ready** – Gunicorn + Nginx (Production Setup)

---

## 📂 Project Structure

```
Maverick/
├── manage.py
├── myproject/
│   ├── __init__.py
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── hackathon/         # Hackathon app
├── problems/          # Coding challenges
├── submissions/       # Submission handling
├── users/             # User accounts
├── static/            # CSS, JS, Images
├── media/             # Uploaded files
├── requirements.txt
└── README.md
```

---

## ⚡ Getting Started

### 🔹 1. Clone the Repository

```bash
git clone https://github.com/Prashanth-4503/Maverick.git
cd Maverick
```

### 🔹 2. Create Virtual Environment

```bash
python -m venv venv
# Activate
# On Linux/Mac:
source venv/bin/activate
# On Windows:
venv\Scripts\activate
```

### 🔹 3. Install Dependencies

```bash
pip install django
pip install -r requirements.txt
```

### 🔹 4. Apply Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 🔹 5. Create Superuser

```bash
python manage.py createsuperuser
```

### 🔹 6. Run Development Server

```bash
python manage.py runserver
```

Visit 👉 `http://127.0.0.1:8000/`

---

## Deployment (Ubuntu/Linux Guide)

```bash
sudo apt update
sudo apt install python3-pip python3-venv nginx
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

* Run with **Gunicorn**
* Reverse proxy using **Nginx**
* Configure **static & media files**

---

## 🎯 Roadmap / Future Enhancements

* 🤖 AI-powered Recommendation Engine (suggest problems)
* 🏆 Gamification (XP, Badges, Achievements)
* 📱 Progressive Web App (PWA) support
* 🌐 Multi-language problem statements
* 📡 Real-time code execution with Docker/Judge0

---

## ⚠️ Security Notice

We recently detected and removed exposed **OpenRouter API Keys** from:

* `myproject/settings.py` (line 193)
* `myapp/views.py` (line 5941)

Anyone with read access could have viewed these secrets. All keys have been **revoked** and should be rotated immediately to prevent misuse.

---

## 👨‍👩‍👧 Team 404Error

⭐ Don’t forget to **star this repo** if you find it useful!
