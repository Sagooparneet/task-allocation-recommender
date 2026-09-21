class Config:
    SECRET_KEY = "dev-secret-key-change-later"

    SQLALCHEMY_DATABASE_URI = "sqlite:///task_allocation.db"
    SQLALCHEMY_TRACK_MODIFICATIONS = False