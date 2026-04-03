# Guide de déploiement — Team Scheduler

Ce guide couvre l'installation complète, la configuration et la maintenance de l'application Team Scheduler en production.

---

## Table des matières

1. [Prérequis](#1-prérequis)
2. [Configuration des variables d'environnement](#2-configuration-des-variables-denvironnement)
3. [Configurer le bot Telegram](#3-configurer-le-bot-telegram)
4. [Lancer l'application](#4-lancer-lapplication)
5. [Déploiement en production avec HTTPS](#5-déploiement-en-production-avec-https)
6. [Vérification post-démarrage](#6-vérification-post-démarrage)
7. [Maintenance en production](#7-maintenance-en-production)
8. [Dépannage](#8-dépannage)

---

## 1. Prérequis

### Logiciels requis

| Outil | Version minimale | Vérification |
|---|---|---|
| Docker | 24.x | `docker --version` |
| Docker Compose | 2.20.x | `docker compose version` |
| Git | 2.x | `git --version` |

> **Déploiement sans Docker** : Python 3.12+, Node.js 20+, PostgreSQL 16 sont nécessaires (voir [section 4.2](#42-sans-docker-développement)).

### Ports utilisés

| Port | Service |
|---|---|
| `80` | Frontend (Nginx) |
| `443` | Frontend HTTPS (si configuré) |
| `8000` | API FastAPI (interne, exposé en dev) |
| `5432` | PostgreSQL (interne, exposé en dev) |

---

## 2. Configuration des variables d'environnement

### 2.1 Créer le fichier `.env`

```bash
cp .env.example .env
```

### 2.2 Description des variables

Ouvrir `.env` et renseigner chaque variable :

```dotenv
# ── Base de données ──────────────────────────────────────────
# URL de connexion PostgreSQL (format SQLAlchemy)
# En production, remplacer les identifiants par des valeurs sécurisées
DATABASE_URL=postgresql+psycopg2://postgres:postgres@db:5432/team_scheduler

# ── API ──────────────────────────────────────────────────────
API_HOST=0.0.0.0
API_PORT=8000

# ── JWT (authentification admin) ─────────────────────────────
# Clé secrète : générer avec `python -c "import secrets; print(secrets.token_hex(32))"`
JWT_SECRET=change-me
JWT_ALGORITHM=HS256
# Durée de validité des tokens en minutes (720 = 12h)
JWT_EXP_MINUTES=720

# ── Administrateur ───────────────────────────────────────────
ADMIN_USERNAME=admin
# Choisir un mot de passe fort en production
ADMIN_PASSWORD=admin123

# ── Bot Telegram ─────────────────────────────────────────────
# Token fourni par @BotFather (voir section 3)
TELEGRAM_BOT_TOKEN=

# URL publique HTTPS de l'API (nécessaire pour les webhooks)
# Exemple : https://api.mondomaine.com
WEBHOOK_URL=https://api.example.com

# Secret de validation des webhooks Telegram
# Générer avec `python -c "import secrets; print(secrets.token_hex(32))"`
WEBHOOK_SECRET=change-me-webhook

# Durée de validité de l'authentification Telegram en secondes (86400 = 24h)
TELEGRAM_AUTH_MAX_AGE_SECONDS=86400

# ── CORS ─────────────────────────────────────────────────────
# Origines autorisées (séparées par des virgules)
# En production : uniquement le domaine du frontend
CORS_ORIGINS=http://localhost:5173,http://localhost
```

### 2.3 Valeurs à absolument changer en production

| Variable | Recommandation |
|---|---|
| `DATABASE_URL` | Utiliser un mot de passe PostgreSQL fort |
| `JWT_SECRET` | Générer une clé aléatoire de 32 octets min. |
| `ADMIN_PASSWORD` | Mot de passe fort (12+ caractères) |
| `WEBHOOK_SECRET` | Générer une clé aléatoire |
| `CORS_ORIGINS` | Restreindre au domaine de production uniquement |

**Générer des secrets sécurisés :**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 3. Configurer le bot Telegram

### 3.1 Créer le bot avec @BotFather

1. Ouvrir Telegram et chercher **@BotFather**.
2. Envoyer `/newbot` et suivre les instructions :
   - Choisir un nom affiché (ex. : `Team Scheduler`)
   - Choisir un username unique se terminant par `bot` (ex. : `team_scheduler_bot`)
3. BotFather renvoie un **token** de la forme `123456789:ABCDEFabcdef...`.
4. Copier ce token dans `.env` :
   ```dotenv
   TELEGRAM_BOT_TOKEN=123456789:ABCDEFabcdef...
   ```

### 3.2 Configurer les commandes du bot

Envoyer à **@BotFather** la commande `/setcommands`, sélectionner votre bot, puis coller :

```
today - Voir mon planning d'aujourd'hui
tomorrow - Voir mon planning de demain
alert - Envoyer une alerte (managers uniquement)
```

### 3.3 Configurer le Telegram Login Widget (frontend)

1. Envoyer `/setdomain` à **@BotFather**.
2. Sélectionner votre bot puis entrer le domaine du frontend (ex. : `mondomaine.com`).

> ⚠ Le Login Widget Telegram **exige HTTPS** et un domaine réel. Il ne fonctionne pas sur `localhost`.

Renseigner le username du bot dans les variables du frontend :
```dotenv
# frontend/.env
VITE_BOT_USERNAME=team_scheduler_bot
```

### 3.4 Configurer le webhook

Le bot fonctionne en mode **webhook** : Telegram envoie les messages à votre API via une requête POST.

- L'API doit être accessible en **HTTPS publique**.
- Le webhook est configuré automatiquement au démarrage de l'API via l'URL :
  ```
  {WEBHOOK_URL}/webhook/telegram
  ```
- Vérifier que `WEBHOOK_URL` pointe vers l'adresse publique de l'API.

**Vérifier le webhook manuellement :**
```bash
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
```

La réponse doit contenir `"url": "https://api.mondomaine.com/webhook/telegram"` et `"pending_update_count": 0`.

---

## 4. Lancer l'application

### 4.1 Avec Docker (recommandé)

```bash
# 1. Cloner le dépôt
git clone <url-du-depot>
cd team-scheduler

# 2. Configurer l'environnement
cp .env.example .env
# Éditer .env avec vos valeurs (voir section 2)

# 3. Construire et démarrer tous les services
docker compose up --build -d

# 4. Vérifier que les conteneurs sont actifs
docker compose ps
```

Les services suivants démarrent :
- `team_scheduler_db` — PostgreSQL 16
- `team_scheduler_api` — FastAPI sur le port 8000
- `team_scheduler_frontend` — Nginx + React sur le port 80

Les tables de la base de données sont créées **automatiquement** au premier démarrage grâce à `SQLAlchemy`.

### 4.2 Sans Docker (développement)

#### Backend

```bash
cd backend

# Créer un environnement virtuel
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # Linux/macOS

# Installer les dépendances
pip install -r requirements.txt

# Configurer les variables d'environnement
# (créer un .env à la racine avec DATABASE_URL pointant vers un PostgreSQL local)

# Lancer l'API
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

#### Frontend

```bash
cd frontend

# Créer un .env local (optionnel)
cp .env.example .env   # si présent

# Installer les dépendances
npm install

# Lancer le serveur de développement (avec proxy vers l'API sur :8000)
npm run dev
```

Le frontend sera disponible sur `http://localhost:5173`.

---

## 5. Déploiement en production avec HTTPS

Le bot Telegram et le Login Widget requièrent une URL publique en HTTPS. Voici la procédure recommandée.

### 5.1 Architecture recommandée (1 seule VM)

Cette architecture est idéale pour un démarrage en production avec un coût réduit et une maintenance simple.

```
Internet ──► Nginx (reverse proxy + TLS) ──► Docker Compose (sur 1 VM)
                                              ├── Frontend (port 80 interne)
                                              ├── API FastAPI (port 8000 interne)
                                              └── PostgreSQL (volume persistant)
```

**Ce que la VM héberge :**
- Docker Engine + Docker Compose
- Le code du projet (`docker-compose.yml`)
- Nginx + certificats TLS (Let's Encrypt)
- Sauvegardes SQL sur disque

**Configuration minimale conseillée :**
- 2 vCPU
- 4 Go RAM
- 40 Go SSD
- Ubuntu 22.04 LTS (ou équivalent)

**Réseau / DNS :**
- `mondomaine.com` -> IP publique de la VM (frontend)
- `api.mondomaine.com` -> IP publique de la VM (API + webhook Telegram)
- Ouvrir uniquement `80/tcp` et `443/tcp`

**Déploiement type (1 VM) :**
```bash
# 1) Installer Docker + Compose
sudo apt update
sudo apt install -y docker.io docker-compose-plugin git
sudo systemctl enable docker
sudo systemctl start docker

# 2) Cloner l'application
git clone <url-du-depot> team-scheduler
cd team-scheduler

# 3) Configurer l'environnement
cp .env.example .env
# puis éditer .env

# 4) Démarrer les services
docker compose up --build -d

# 5) (Optionnel) Injecter des données de démo
docker compose exec api python -m app.init_db
```

**Variables `.env` recommandées pour cette architecture :**
```dotenv
WEBHOOK_URL=https://api.mondomaine.com
CORS_ORIGINS=https://mondomaine.com
```

**Bonnes pratiques (1 VM) :**
- Conserver PostgreSQL avec volume Docker persistant
- Sauvegarder la base quotidiennement hors conteneur
- Mettre une policy de redémarrage (`restart: unless-stopped`)
- Surveiller le disque (`docker system df`, `df -h`)

### 5.2 Avec un reverse proxy Nginx externe + Certbot

**Installer Certbot (Ubuntu/Debian) :**
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d mondomaine.com -d api.mondomaine.com
```

**Configuration Nginx (`/etc/nginx/sites-available/team-scheduler`) :**
```nginx
# Frontend
server {
    listen 443 ssl;
    server_name mondomaine.com;

    ssl_certificate /etc/letsencrypt/live/mondomaine.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mondomaine.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:80;
        proxy_set_header Host $host;
    }
}

# API
server {
    listen 443 ssl;
    server_name api.mondomaine.com;

    ssl_certificate /etc/letsencrypt/live/api.mondomaine.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.mondomaine.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}

# Redirection HTTP → HTTPS
server {
    listen 80;
    server_name mondomaine.com api.mondomaine.com;
    return 301 https://$host$request_uri;
}
```

### 5.3 Adapter les variables d'environnement

```dotenv
WEBHOOK_URL=https://api.mondomaine.com
CORS_ORIGINS=https://mondomaine.com
```

---

## 6. Vérification post-démarrage

Après le démarrage, vérifier les points suivants :

```bash
# 1. Santé de l'API
curl http://localhost:8000/health
# Réponse attendue : {"status": "ok"}

# 2. Documentation interactive de l'API
# Ouvrir dans un navigateur : http://localhost:8000/docs

# 3. Logs des conteneurs
docker compose logs api        # Logs de l'API
docker compose logs db         # Logs PostgreSQL
docker compose logs frontend   # Logs Nginx

# 4. Statut du webhook Telegram
curl https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/getWebhookInfo

# 5. Test du login admin
curl -X POST http://localhost:8000/auth/admin/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
# Réponse attendue : {"access_token": "...", "token_type": "bearer"}
```

---

## 7. Maintenance en production

### 7.1 Mettre à jour l'application

```bash
# 1. Récupérer les nouvelles sources
git pull origin main

# 2. Reconstruire et redémarrer les services
docker compose up --build -d

# 3. Vérifier les logs
docker compose logs --tail=50 api
```

### 7.2 Sauvegarder la base de données

**Créer une sauvegarde (dump) :**
```bash
docker compose exec db pg_dump -U postgres team_scheduler > backup_$(date +%Y%m%d_%H%M%S).sql
```

**Restaurer une sauvegarde :**
```bash
docker compose exec -T db psql -U postgres team_scheduler < backup_20260402_120000.sql
```

**Automatiser (cron, Linux) :**
```bash
# Ajouter dans crontab (`crontab -e`) — sauvegarde quotidienne à 2h
0 2 * * * docker compose -f /chemin/vers/docker-compose.yml exec -T db pg_dump -U postgres team_scheduler > /backups/backup_$(date +\%Y\%m\%d).sql
```

### 7.3 Consulter les logs

```bash
# Logs en temps réel
docker compose logs -f api

# Logs des dernières 24h
docker compose logs --since 24h api

# Logs d'un conteneur spécifique avec horodatage
docker compose logs -t --tail=100 api
```

### 7.4 Redémarrer un service spécifique

```bash
docker compose restart api        # Redémarrer uniquement l'API
docker compose restart frontend   # Redémarrer uniquement le frontend
```

### 7.5 Gérer les mises à jour de schéma

Le schéma est créé automatiquement via `SQLAlchemy`. Pour les **migrations en production** (modification du schéma sans perte de données), il est recommandé d'intégrer **Alembic** :

```bash
# Installation (dans l'environnement backend)
pip install alembic

# Initialiser Alembic
alembic init migrations

# Créer une migration
alembic revision --autogenerate -m "description du changement"

# Appliquer les migrations
alembic upgrade head
```

### 7.6 Renouveler le certificat TLS

```bash
# Renouvellement automatique (à tester)
sudo certbot renew --dry-run

# Forcer le renouvellement
sudo certbot renew --force-renewal
```

Le renouvellement automatique via le timer systemd de Certbot s'effectue deux fois par jour.

### 7.7 Surveiller les ressources

```bash
# Utilisation des ressources par conteneur
docker stats

# Espace disque (volumes Docker)
docker system df

# Nettoyer les images et volumes non utilisés
docker system prune -f
```

### 7.8 Lancer les tests

```bash
# Depuis la racine du projet
cd backend
pip install -r requirements.txt -r requirements-test.txt
pytest -v

# Avec couverture de code
pytest --cov=app --cov-report=term-missing
```

---

## 8. Dépannage

### Le bot Telegram ne répond pas

1. Vérifier que `TELEGRAM_BOT_TOKEN` est correct dans `.env`.
2. Vérifier le webhook :
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo
   ```
3. Vérifier que `WEBHOOK_URL` est accessible depuis l'extérieur (HTTPS obligatoire).
4. Consulter les logs de l'API :
   ```bash
   docker compose logs -f api
   ```

### L'API renvoie `500 Internal Server Error`

```bash
# Inspecter les logs détaillés
docker compose logs --tail=100 api

# Vérifier la connexion à la base de données
docker compose exec api python -c "from app.database import engine; engine.connect(); print('OK')"
```

### Le frontend affiche une erreur CORS

Vérifier que `CORS_ORIGINS` dans `.env` contient bien l'origine du frontend :
```dotenv
# Développement
CORS_ORIGINS=http://localhost:5173,http://localhost

# Production
CORS_ORIGINS=https://mondomaine.com
```

Redémarrer l'API après modification : `docker compose restart api`.

### Le conteneur `db` ne démarre pas

```bash
# Voir les erreurs de PostgreSQL
docker compose logs db

# Supprimer le volume et repartir de zéro (⚠ perte de données)
docker compose down -v
docker compose up -d
```

### Un utilisateur reste bloqué en statut `pending`

1. Se connecter à l'interface admin (`/admin` sur le frontend).
2. Retrouver l'utilisateur et lui attribuer le rôle `employee` ou `manager`.
3. Ou via l'API :
   ```bash
   # Obtenir un token admin
   TOKEN=$(curl -s -X POST http://localhost:8000/auth/admin/login \
     -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

   # Assigner le rôle
   curl -X PATCH http://localhost:8000/auth/admin/users/{USER_ID}/role \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"role": "employee"}'
   ```
