import waitress
from backend.wsgi import application

if __name__ == "__main__":
    waitress.serve(
        application,
        host="0.0.0.0",
        port=8130,
        threads=16
    )
