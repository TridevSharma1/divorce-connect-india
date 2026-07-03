import asyncio
import os
import sys

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi_app.database import AsyncSessionLocal
from fastapi_app.models import CaseDocument, CaseDocumentVerification
from sqlalchemy import select

async def main():
    print("Testing DB connection and inserts...")
    async with AsyncSessionLocal() as db:
        try:
            # Query existing case document
            res = await db.execute(select(CaseDocument).limit(5))
            docs = res.scalars().all()
            print(f"Found {len(docs)} documents:")
            for d in docs:
                print(f"ID: {d.id}, Case ID: {d.case_request_id}, Type: {d.document_type}, File: {d.document_file}")
                
            # Query verification records
            ver_res = await db.execute(select(CaseDocumentVerification).limit(5))
            vers = ver_res.scalars().all()
            print(f"Found {len(vers)} verifications:")
            for v in vers:
                print(f"ID: {v.id}, Doc ID: {v.document_id}, Status: {v.status}")
                
        except Exception as e:
            print("Error occurred:", e)
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
