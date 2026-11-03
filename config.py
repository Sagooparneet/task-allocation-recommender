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

    # Separate sign-in OAuth client. The Gmail delivery client has different permissions.
    INTELLITASK_GOOGLE_SIGNIN_CLIENT_FILE = os.environ.get('INTELLITASK_GOOGLE_SIGNIN_CLIENT_FILE')
    INTELLITASK_GOOGLE_SIGNIN_CLIENT_ID = os.environ.get('INTELLITASK_GOOGLE_SIGNIN_CLIENT_ID')
    INTELLITASK_GOOGLE_SIGNIN_CLIENT_SECRET = os.environ.get('INTELLITASK_GOOGLE_SIGNIN_CLIENT_SECRET')
    INTELLITASK_GOOGLE_SIGNIN_REDIRECT_URI = os.environ.get('INTELLITASK_GOOGLE_SIGNIN_REDIRECT_URI')
