#!/usr/bin/env python3
"""
Scénario de démonstration de bout en bout (à lancer quand la plateforme tourne) :
    python scripts/demo.py

1. Connexion administrateur   2. Inscription d'un restaurateur
3. Consultation du catalogue   4. Passage d'une commande
5. Vérification du stock       6. Annulation et remise en stock
"""
import os
import sys
import time
import uuid

import requests

CLIENT = os.environ.get("CLIENT_URL", "http://localhost:8080/client")
PRODUCT = os.environ.get("PRODUCT_URL", "http://localhost:8080/product")
ORDER = os.environ.get("ORDER_URL", "http://localhost:8080/order")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@payetonkawa.fr")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "AdminKawa!2026")


def step(title):
    print(f"\n=== {title}")


def check(response, expected):
    print(f"    {response.request.method} {response.url} -> {response.status_code}")
    if response.status_code != expected:
        print(f"    ERREUR, attendu {expected} : {response.text}")
        sys.exit(1)
    return response.json() if response.content else None


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


step("1. Connexion de l'administrateur")
admin = check(requests.post(f"{CLIENT}/api/auth/login/", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}), 200)

step("2. Inscription d'un restaurateur")
email = f"resto-{uuid.uuid4().hex[:6]}@exemple.fr"
user = check(requests.post(f"{CLIENT}/api/auth/register/", json={
    "email": email, "password": "Restaurant!2026", "nom": "Dupont", "prenom": "Léa",
    "type_client": "professionnel", "societe": "Le Petit Bistrot", "ville": "Lyon",
}), 201)
print(f"    Client créé : {user['client']['id']}")

step("3. Catalogue (public)")
products = check(requests.get(f"{PRODUCT}/api/products/", params={"in_stock": "true", "ordering": "price"}), 200)
for p in products:
    print(f"    #{p['id']} {p['name']:<18} {p['price']:>6} €  stock {p['stock']}")
product = products[0]

step("4. Le restaurateur passe commande")
order = check(requests.post(f"{ORDER}/api/orders/", headers=bearer(user["access"]),
                            json={"items": [{"product_id": product["id"], "quantity": 3}]}), 201)
print(f"    Commande #{order['id']} : total {order['total_amount']} €, statut {order['status']}")

step("5. Stock mis à jour par l'événement order.created (RabbitMQ)")
time.sleep(2)
after = check(requests.get(f"{PRODUCT}/api/products/{product['id']}/"), 200)
print(f"    Stock {product['name']} : {product['stock']} -> {after['stock']}")

step("6. Sécurité : le client ne peut pas voir les autres clients")
check(requests.get(f"{CLIENT}/api/clients/", headers=bearer(user["access"])), 403)

step("7. L'administrateur valide puis le client tente d'annuler (refusé)")
check(requests.patch(f"{ORDER}/api/orders/{order['id']}/status/", headers=bearer(admin["access"]),
                     json={"status": "validee"}), 200)
check(requests.post(f"{ORDER}/api/orders/{order['id']}/cancel/", headers=bearer(user["access"])), 400)

step("8. L'administrateur annule : le stock est remis")
check(requests.post(f"{ORDER}/api/orders/{order['id']}/cancel/", headers=bearer(admin["access"])), 200)
time.sleep(2)
final = check(requests.get(f"{PRODUCT}/api/products/{product['id']}/"), 200)
print(f"    Stock {product['name']} : {final['stock']}")

print("\nScénario terminé avec succès.")
