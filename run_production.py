"""Production entrypoint for running on a shop Windows computer.

Flask's built-in dev server (used by wsgi.py / `python wsgi.py`) is fine for local
testing but explicitly warns against production use and isn't designed to stay
running unattended for months. Waitress is a pure-Python WSGI server that works
natively on Windows (gunicorn does not - it requires fork(), which Windows lacks)
and is solid for exactly this use case: one app, modest traffic, needs to just work.

Usage:
    python run_production.py

This is what the Task Scheduler auto-start script (see deploy/windows/) actually
launches - not wsgi.py directly.
"""
import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

load_dotenv()

from waitress import serve
from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "production"))

# In production, Flask shows a generic "Internal Server Error" page instead of a
# traceback (correctly - real tracebacks shouldn't be shown to staff at a shop
# computer). Without this, that also means errors are otherwise invisible. This logs
# the full exception to error.log next to this file, so a 500 can actually be
# diagnosed instead of just seeing a blank error page with no detail.
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "error.log")
file_handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=3)
file_handler.setLevel(logging.ERROR)
file_handler.setFormatter(logging.Formatter(
    "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
))
app.logger.addHandler(file_handler)
app.logger.setLevel(logging.ERROR)

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    threads = int(os.environ.get("WAITRESS_THREADS", "4"))

    print(f"Tech-Pro+ CRM starting on http://{host}:{port} (production server)")
    print(f"Errors will be logged to {log_path}")
    serve(app, host=host, port=port, threads=threads)
