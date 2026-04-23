# FutureFlux — Django Blog Platform

A full-featured blog platform built with Django 5.2, featuring email verification, role-based access control, and a responsive editorial design.

🌐 **Live Demo:** [futureflux.pythonanywhere.com](https://futureflux.pythonanywhere.com)

---

## Features

- **Email Verification** — New users must verify their email before logging in. Auto-login after verification with a real-time waiting page that updates without refresh.
- **Role-Based Access Control** — Three roles: Superuser, Manager, and Editor. Editors can only edit/delete their own posts. Managers cannot modify superuser accounts.
- **Post Management** — Create, edit, delete, and feature blog posts with image uploads.
- **Category System** — Organize posts by category with a filterable navigation bar.
- **Search** — Full-text keyword search across all published posts.
- **Responsive Design** — Mobile-first UI with a custom hamburger menu showing a user profile card.
- **Dashboard** — Admin panel with post and category stats, quick actions, and user management.
- **Secure Auth** — Gmail SMTP email delivery with App Password configured in Django settings.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2 |
| Database | SQLite (dev) |
| Frontend | Tailwind CSS CDN, DM Sans, Playfair Display |
| Forms | django-crispy-forms + crispy-bootstrap4 |
| Email | Gmail SMTP via django email backend |
| Images | Pillow |
| Deployment | PythonAnywhere |
| Environment | python-dotenv |

---

## Project Structure

```
blog/
├── blog_main/          # Project config: settings, urls, views, forms
├── blogs/              # Blog posts, categories, comments, email token model
├── dashboards/         # Admin dashboard: posts, users, categories management
├── about/              # About page model
├── templates/          # All HTML templates
│   ├── dashboard/      # Dashboard templates
│   ├── base.html
│   ├── home.html
│   ├── login.html
│   ├── register.html
│   ├── verify_wait.html
│   ├── verify_success.html
│   └── resend_verification.html
├── media/              # User uploaded images
├── static/             # Collected static files
├── manage.py
├── requirements.txt
└── settings.py         # Email settings configured directly for local SMTP
```

---

## Local Setup

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/blog.git
cd blog
```

### 2. Create and activate virtual environment

```bash
python3 -m venv env
source env/bin/activate        # Mac/Linux
env\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Create a superuser

```bash
python manage.py createsuperuser
```

### 6. Run the development server

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000`

---

## Email Setup (Gmail)

1. Go to [myaccount.google.com](https://myaccount.google.com) → Security
2. Enable **2-Step Verification**
3. Search for **App Passwords** → Create one named `Django Blog`
4. Update the SMTP values directly in `blog_main/settings.py`

---

## User Roles

| Role | Posts | Users |
|---|---|---|
| **Superuser** | Edit / Delete all | Edit / Delete all including superusers |
| **Manager** | Edit / Delete all | Edit / Delete non-superusers only |
| **Editor** | Edit / Delete own posts only | No access |

To assign roles, go to `/admin/` → Groups → assign users to `Manager` or `Editor` group.

---

## Deployment (PythonAnywhere)

1. Upload project files to PythonAnywhere
2. Set up a virtual environment and install requirements
3. Configure WSGI file to point to `blog_main.settings`
4. Add Static Files mappings in the Web tab:
   - `/static/` → `/home/yourusername/blog/static`
   - `/media/` → `/home/yourusername/blog/media`
5. Update `settings.py`:

```python
DEBUG = False
ALLOWED_HOSTS = ['yourusername.pythonanywhere.com']
SITE_URL = 'https://yourusername.pythonanywhere.com'
```

6. Run `python manage.py collectstatic`
7. Reload the app from the Web tab

---

## Requirements

```
Django==5.2.12
asgiref==3.11.1
sqlparse==0.5.5
pillow==12.1.1
django-crispy-forms==2.6
crispy-bootstrap4==2024.1
python-dotenv==1.1.0
certifi==2026.2.25
```

---

## License

MIT License — feel free to use and modify.

---

## Author

Built by [deepprasadsah](https://github.com/deepprasadsah)
