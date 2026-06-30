import asyncio
import websockets
from fastapi_app.security import create_access_token
from datetime import timedelta

async def test_ws():
    # Generate a valid access token for user_id = 9999
    token = create_access_token(data={"sub": "admin_test@example.com", "user_id": 9999}, expires_delta=timedelta(minutes=5))
    uri = f"ws://127.0.0.1:8000/ws/notifications/9999?token={token}"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Successfully connected!")
            # Send a dummy message or wait
            await asyncio.sleep(2)
            print("Closing connection...")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    # Start the server or check if it's already running
    asyncio.run(test_ws())
