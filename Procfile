web: cd divorce_connect && python create_tables.py && gunicorn fastapi_app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:$PORT
