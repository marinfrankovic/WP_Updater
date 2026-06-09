"""WSGI / dev entrypoint for the WP Updater dashboard."""
from app.config import config
from app.routes import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT)
