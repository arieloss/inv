# AdminPanel — Dashboard FastAPI + PostgreSQL

Application de gestion avec authentification, dashboard admin et dashboard utilisateur.

## Stack technique
- **Backend** : FastAPI, SQLAlchemy, Jinja2
- **Base de données** : PostgreSQL
- **Auth** : JWT (python-jose) + Bcrypt (passlib)
- **Frontend** : HTML, CSS, Bootstrap 5, FontAwesome

## Identifiants par défaut
| Rôle | Identifiant | Mot de passe |
|------|------------|--------------|
| Admin | `admin` | `admin` |

## Lancement avec Docker (recommandé)

```bash
# 1. Cloner le projet
cd app/

# 2. Modifier le .env si nécessaire
nano .env

# 3. Lancer avec Docker Compose
docker-compose up -d

# 4. Accéder à l'app
http://localhost:8000
```

## Lancement sans Docker

```bash
# 1. Créer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows

# 2. Installer les dépendances
pip install -r requirements.txt

# 3. Configurer PostgreSQL
# Créer une base de données : admin_dashboard
# Mettre à jour DATABASE_URL dans .env

# 4. Lancer l'application
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 5. Accéder à l'app
http://localhost:8000
```

## Variables d'environnement (.env)

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/admin_dashboard
SECRET_KEY=votre_cle_secrete_tres_longue_et_complexe
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin
APP_NAME=AdminPanel
```

## Structure du projet

```
app/
├── main.py              # Point d'entrée FastAPI
├── database.py          # Config SQLAlchemy
├── models.py            # Modèles DB (User, Alert, History)
├── .env                 # Variables secrètes (ne pas commiter)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── routers/
│   ├── auth.py          # Login / Logout
│   ├── admin.py         # Dashboard admin
│   └── user.py          # Dashboard utilisateur
├── utils/
│   └── auth.py          # JWT, hashing
├── templates/
│   ├── base.html
│   ├── login.html
│   ├── admin/
│   │   └── dashboard.html
│   └── user/
│       ├── base_user.html
│       ├── dashboard.html
│       ├── history.html
│       ├── alerts.html
│       └── settings.html
└── static/
    ├── css/main.css
    └── js/main.js
```

## Fonctionnalités

### Admin
- Dashboard avec stats (total / actifs / inactifs)
- Créer un utilisateur (username, password, nom, email)
- Liste des utilisateurs avec mot de passe masquable
- Activer / désactiver un utilisateur
- Supprimer un utilisateur

### Utilisateur
- Dashboard avec activité récente
- Page Historique (journal complet)
- Page Alertes (notifications système)
- Page Paramètres (modifier profil + changer mot de passe)
