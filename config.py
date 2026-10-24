import os


class Config:
    # Local fallback preserves the existing development installation.
    # The production startup will require a private secret.
    SECRET_KEY = os.environ.get(
        "INTELLITASK_SECRET_KEY",
        "dev-secret-key-change-later",
    )

    # A hosting server can provide its database connection address.
    # Without an override, the original local SQLite database is used.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "INTELLITASK_DATABASE_URL",
        "sqlite:///task_allocation.db",
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Prevent browser JavaScript from reading the login cookie.
    SESSION_COOKIE_HTTPONLY = True

    # Restrict sending the login cookie with cross-site requests.
    SESSION_COOKIE_SAMESITE = "Lax"