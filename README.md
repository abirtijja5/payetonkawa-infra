# PayeTonKawa – Plateforme micro-services

Projet MSPR TPRE814 (Bloc 4 – EISI). PayeTonKawa, importateur de café, remplace son ERP et son CRM
par 3 micro-services REST indépendants pour vendre aussi aux professionnels via des distributeurs.

Tous les appels passent par la **passerelle Nginx** : http://localhost:8080

| Composant | Rôle | URL |
|---|---|---|
| **Service Clients** | inscription, connexion (JWT), CRUD clients | http://localhost:8080/client/api/docs/ |
| **Service Produits** | catalogue des cafés, stock | http://localhost:8080/product/api/docs/ |
| **Service Commandes** | prise et suivi des commandes | http://localhost:8080/order/api/docs/ |
| RabbitMQ | événements entre services | http://localhost:15672 |
| Prometheus | collecte des métriques et alertes | http://localhost:9090 |
| Grafana | tableau de bord de supervision | http://localhost:3000 (admin / mot de passe du `.env`) |

**Technologies :** Python 3.12, Django 5.2 + Django REST Framework, JWT (simplejwt), RabbitMQ,
PostgreSQL (une base par service), Nginx, Docker Compose, GitHub Actions, Prometheus + Grafana,
Swagger/OpenAPI, Postman/newman.

## Dépôts Git

| Dépôt | Contenu |
|---|---|
| `payetonkawa-client` | service Clients (dossier `services/client`) |
| `payetonkawa-product` | service Produits (dossier `services/product`) |
| `payetonkawa-order` | service Commandes (dossier `services/order`) |
| `payetonkawa-infra` | ce dépôt : Docker Compose, passerelle, supervision, Postman, tests d'intégration |

Chaque service a son propre pipeline CI/CD (`.github/workflows/ci.yml`).

## 1. Lancer la plateforme

Prérequis : Docker Desktop.

```bash
cp .env.example .env          # puis changer les mots de passe
docker compose up --build -d

# Créer l'administrateur et charger le catalogue de démonstration
docker compose exec client python manage.py createsuperuser
docker compose exec product python manage.py seed_products   # ou import_erp (ancien ERP)
docker compose exec client python manage.py import_crm       # reprise des clients du CRM
```

Montée en charge : `docker compose up -d --scale product=3` lance 3 instances de l'API Produits ;
la passerelle répartit les appels et RabbitMQ partage les événements entre elles.

Arrêter : `docker compose down` (ajouter `-v` pour effacer les données).

## 2. Tester l'API

- **Postman** : importer `postman/PayeTonKawa.postman_collection.json` et l'environnement
  `postman/PayeTonKawa.local.postman_environment.json`, puis lancer le *Runner* (29 requêtes, 35 vérifications).
- En ligne de commande : `newman run postman/PayeTonKawa.postman_collection.json -e postman/PayeTonKawa.local.postman_environment.json --delay-request 300`

## 3. Démonstration de bout en bout

```bash
pip install requests
ADMIN_EMAIL=<email admin> ADMIN_PASSWORD=<mot de passe> python scripts/demo.py
```

Le script : connexion admin → inscription d'un restaurateur → catalogue → commande →
baisse du stock via RabbitMQ → contrôle d'accès → validation → annulation et remise en stock.

## 4. Tests

```bash
cd services/order            # ou client, product
pip install -r requirements-dev.txt
python manage.py test        # tests unitaires et d'intégration
coverage run manage.py test && coverage report
flake8 .                     # qualité du code
```

84 tests, couverture de 97 % sur chaque service. Les mêmes commandes tournent dans la CI.

## 5. Principaux endpoints (préfixer par /client, /product ou /order)

| Méthode | URL | Accès |
|---|---|---|
| POST | `/api/auth/register/` · `/api/auth/login/` · `/api/auth/refresh/` (Clients) | public |
| GET/POST | `/api/clients/` (`?search=`, `?type_client=`) | admin |
| GET/PUT/PATCH/DELETE | `/api/clients/{id}/` · GET `/api/clients/me/` | admin ou le client lui-même |
| GET | `/api/products/` (`?search=`, `?ordering=price`, `?in_stock=true`) · `/api/products/{id}/` | public |
| POST/PUT/PATCH/DELETE | `/api/products/…` · GET `/api/products/low-stock/` | admin |
| GET/POST | `/api/orders/` (`?status=`, `?customer_id=`) | client connecté (ses commandes) |
| GET | `/api/orders/{id}/` · POST `/api/orders/{id}/cancel/` | propriétaire ou admin |
| PATCH | `/api/orders/{id}/status/` · DELETE `/api/orders/{id}/` | admin |

## 6. Événements RabbitMQ (exchange `payetonkawa.events`, type topic)

| Événement | Publié par | Écouté par | Effet |
|---|---|---|---|
| `client.created / updated / deleted` | Clients | Commandes (`deleted`) | annule les commandes non expédiées |
| `order.created` | Commandes | Produits | retire les quantités du stock |
| `order.cancelled` | Commandes | Produits | remet les quantités en stock |
| `order.status_changed` | Commandes | – | suivi |
| `product.created / updated / deleted / stock_updated` | Produits | – | synchronisation webshop |

## 7. Organisation

```
services/client|product|order   un dépôt Git par micro-service (code, tests, Dockerfile, CI/CD)
gateway/nginx.conf              passerelle d'API (routage, répartition de charge, limitation)
monitoring/                     Prometheus (collecte + alertes) et Grafana (tableau de bord)
postman/                        collection et environnement Postman
.github/workflows/integration.yml  tests d'intégration de la plateforme complète
scripts/demo.py                 scénario de démonstration
docs/                           schémas d'architecture
```

## 8. Workflow Git

GitFlow : `main` (production) ← `release/x.y` ← `develop` ← `feature/xxx` (+ `hotfix/xxx` depuis `main`).
Toute modification passe par une pull request relue et validée par la CI (flake8, tests, couverture ≥ 95 %,
Bandit, pip-audit) avant fusion. Messages de commit au format *Conventional Commits* (`feat:`, `fix:`, `test:`…).
Sur `develop`, `main` et les tags `v*`, les images Docker sont publiées sur GitHub Container Registry
(`ghcr.io/<organisation>/payetonkawa-<service>`), prêtes à être déployées.
