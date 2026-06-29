import os
from taskiq_nats import NatsBroker

# Configure the NATS URL. Defaulting to localhost:4222 if not set in environment.
NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")

# Initialize the Taskiq NatsBroker
broker = NatsBroker(
    servers=[NATS_URL],
    queue="fastapi_tasks_queue"
)

# You can add middlewares here (e.g., for logging, retry logic, or result backends)
