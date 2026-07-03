import asyncio
import os
import sys

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi_app.database import AsyncSessionLocal
from fastapi_app.security import create_access_token
from fastapi_app.main import app
from datetime import timedelta
import httpx

async def main():
    print("Testing upload API in-memory ASGI...")
    
    # 1. Create a token for client user NOone@gmail.com
    access_token = create_access_token(
        data={"sub": "NOone@gmail.com", "type": "access"},
        expires_delta=timedelta(minutes=30)
    )
    print("Generated token:", access_token)
    
    # 2. Prepare dummy file upload
    file_content = b"dummy file content for testing"
    files = {"file": ("test_doc.pdf", file_content, "application/pdf")}
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 3. Call the API
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            res = await client.post(
                "/api/client/cases/2/documents?document_type=aadhaar",
                files=files,
                headers=headers
            )
            print("Response Status Code:", res.status_code)
            print("Response Content:", res.text)
        except Exception as e:
            print("Error running ASGI app:", e)
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
