

import csv
import os

# temporary solution for user base
UI_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(UI_DIR)
USERS_FILE = os.path.join(PROJECT_ROOT, "Userbase samples", "users.csv")


def _load_users() -> list[dict]:
    users = []
    if not os.path.exists(USERS_FILE):
        return users

    with open(USERS_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            users.append({
                "email": row["email"].strip(),
                "password": row["password"],
                "role": row["role"].strip(),
            })
    return users


def authenticate(email: str, password: str) -> str | None:

   #Checks the given email/password against users.csv.
     # returns the user's role (e.g. "pilot" or "agent") if the credentials match a row in the file, or None if there's no match.

    #Case-insensitive on email (so "Pilot@AbWildfire.ca" still matches), case-sensitive on password.

    email = email.strip().lower()
    for user in _load_users():
        if user["email"].lower() == email and user["password"] == password:
            return user["role"]
    return None