# Team Scheduler (MVP)

Premier jet d'une application de gestion des tâches d'équipe avec:
- création de tâches avec créneaux horaires (managers)
- inscription des employés et managers sur des tâches
- détection des conflits d'horaires
- consultation du planning via bot Telegram (`aujourd'hui` et `demain`)
- authentification Telegram + administration des rôles via JWT
- interface Web multi-rôles (admin, manager, employé)

## Stack proposée
- Backend API: FastAPI (Python)
- Base de données: PostgreSQL
- ORM: SQLAlchemy
- Validation: Pydantic
- Bot: python-telegram-bot
- Frontend: React + TypeScript + Vite + TailwindCSS
- Conteneurisation: Docker + docker-compose

## Démarrage rapide
1. Copier les variables d'environnement:
   - `copy .env.example .env`
2. Lancer les services:
   - `docker compose up --build`
3. Initialiser la base:
   - `docker compose exec api python -m app.init_db`
4. Accéder aux interfaces:
   - Frontend: `http://localhost`
   - API docs: `http://localhost:8000/docs`

## Architecture production (1 VM)

Une architecture "1 seule VM" (frontend + backend + base PostgreSQL via Docker Compose) est documentée dans :

- `DEPLOYMENT.md` -> section **5.1 Architecture recommandée (1 seule VM)**

Cette option est adaptée pour un premier lancement en production avec un coût réduit.

## Frontend (React)
Le frontend est dans le dossier `frontend/` et propose 3 interfaces:
- **Administrateur**:
  - gestion des utilisateurs
  - filtrage par rôle
  - attribution du rôle `employee` / `manager`
  - envoi d'alertes Telegram
- **Manager**:
  - vue planning complet du jour
  - vue des tâches non remplies
  - création / édition de tâches
  - affectation des tâches à des employés/managers
  - envoi d'alertes Telegram
- **Employé**:
  - vue planning personnel (aujourd'hui / demain)
  - mise en évidence des conflits d'horaires
  - auto-affectation aux tâches non remplies

### Lancer le frontend en développement
```bash
cd frontend
copy .env.example .env
npm install
npm run dev
```

Variables frontend:
- `VITE_API_BASE` (optionnel, vide par défaut avec proxy)
- `VITE_BOT_USERNAME` (nom du bot Telegram, sans `@`)

## Scenarios de test rapides
1. Login Telegram utilisateur:
   - `POST /auth/telegram/login`
   - payload (depuis Telegram Login Widget):
     - `{ "id": 900002, "first_name": "Alice", "username": "alice", "auth_date": 1711960000, "hash": "..." }`
2. Login admin:
   - `POST /auth/admin/login`
3. Assigner le role utilisateur:
   - `PATCH /auth/admin/users/{id}/role`
   - payload:
     - `{ "role": "employee" }` ou `{ "role": "manager" }`
4. Creer des taches (manager):
   - `POST /tasks`
   - payload:
     - `{ "title": "Support", "start_at": "2026-04-01T09:00:00", "end_at": "2026-04-01T11:00:00", "required_people": 2 }`
5. Affecter une personne a une tache:
   - `POST /assignments`
   - payload:
     - `{ "task_id": 1, "assignee_id": 2 }`
6. Verifier les conflits personnels:
   - `GET /assignments/me/conflicts?date_value=2026-04-01`

## Fonctionnement du bot Telegram
- Définir `TELEGRAM_BOT_TOKEN` dans `.env`.
- Définir aussi `WEBHOOK_URL` et `WEBHOOK_SECRET` pour les webhooks HTTPS.
- Le bot est traité par l'API FastAPI via `POST /webhook/telegram`.
- Chaque compte doit exister via login Telegram (champ `telegram_user_id`).
- Commandes disponibles:
  - `/today`
  - `/tomorrow`
   - `/alert <message>` (managers)

## Limites du MVP
- Pas de gestion des fuseaux horaires avancée
- Pas d'historique/audit des actions en interface

## Prochaines évolutions
- Notifications Telegram automatiques
- Audit log des modifications
- Tests end-to-end frontend

## Flux d'authentification
1. L'utilisateur se connecte avec son identité Telegram (`POST /auth/telegram/login`).
2. Le compte est créé automatiquement avec le rôle `pending`.
3. Un administrateur se connecte via JWT (`POST /auth/admin/login`).
4. L'administrateur assigne le rôle `employee` ou `manager` (`PATCH /auth/admin/users/{id}/role`).

### Protection d'accès (validé par admin)
- Un utilisateur en rôle `pending` **ne peut pas accéder aux routes applicatives**.
- Backend: `GET /auth/me` exige un rôle validé (`employee` ou `manager`).
- Frontend: si le backend refuse l'accès (403), l'interface affiche un écran de blocage en attente de validation admin.

## Endpoints principaux
- `POST /auth/telegram/login` : login utilisateur via identité Telegram.
- `POST /auth/admin/login` : login administrateur.
- `PATCH /auth/admin/users/{user_id}/role` : assignation de rôle.
- `GET /users` : liste des utilisateurs (admin).
- `GET /users/assignable` : utilisateurs affectables (manager).
- `POST /tasks` : création de tâche par un manager (avec `required_people`).
- `GET /tasks/unfilled?date_value=YYYY-MM-DD` : tâches non remplies.
- `POST /assignments` : affectation d'une personne à une tâche.
- `GET /assignments/me/schedule?date_value=YYYY-MM-DD` : planning personnel.
- `GET /assignments/me/conflicts?date_value=YYYY-MM-DD` : conflits personnels.
- `POST /alerts` : envoi d'une alerte Telegram (manager).

## Tests pytest
Lancement des tests avec les commandes suivantes :
```bash
cd backend
pip install -r requirements.txt -r requirements-test.txt
pytest
```
