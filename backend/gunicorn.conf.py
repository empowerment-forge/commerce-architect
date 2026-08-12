import os


bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
accesslog = "-"
errorlog = "-"
workers = int(os.environ.get("GUNICORN_WORKERS", "2"))
timeout = int(os.environ.get("GUNICORN_TIMEOUT", "30"))
