import os
from dotenv import load_dotenv, find_dotenv
from taskiq_nats import NatsBroker

# THIS FORCES PYTHON TO FIND THE .ENV FILE NO MATTER WHERE IT IS
load_dotenv(find_dotenv())

# Configure the NATS URL. Defaulting to localhost:4222 if not set in environment.
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")

# Initialize the Taskiq NatsBroker
broker = NatsBroker(
    servers=[NATS_URL],
    queue="fastapi_tasks_queue"
)

# You can add middlewares here (e.g., for logging, retry logic, or result backends)

# THIS LINE IS MANDATORY: It forces the broker to discover and register your tasks!
try:
    import divorce_connect.fastapi_app.tasks
except ModuleNotFoundError:
    import fastapi_app.tasks