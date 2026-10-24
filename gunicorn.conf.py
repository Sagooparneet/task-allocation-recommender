import os

bind = f"0.0.0.0:{os.environ.get('PORT', '10000')}"

# One process limits memory used by the ML artifacts.
workers = 1
worker_class = "sync"
timeout = 120

errorlog = "-"
loglevel = "info"