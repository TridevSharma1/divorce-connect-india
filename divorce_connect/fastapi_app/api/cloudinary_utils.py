import asyncio
import io
from pathlib import Path
from dotenv import load_dotenv, find_dotenv
import cloudinary
import cloudinary.uploader
from fastapi import UploadFile

# Load environment variables from the project .env file before Cloudinary config.
env_path = Path(__file__).resolve().parents[2] / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv(find_dotenv())
cloudinary.config()

async def upload_to_cloudinary(upload_file: UploadFile, folder: str) -> str:
    """Upload an UploadFile to Cloudinary and return the secure URL."""
    contents = await upload_file.read()
    if not contents:
        raise ValueError("Uploaded file is empty")

    file_object = io.BytesIO(contents)
    result = await asyncio.to_thread(
        cloudinary.uploader.upload,
        file_object,
        folder=folder,
        resource_type="auto",
        use_filename=True,
        unique_filename=True,
        overwrite=False,
    )

    url = result.get("secure_url") or result.get("url")
    if not url:
        raise RuntimeError("Cloudinary upload failed to return a URL")
    return url
