import os
import tempfile
import requests
from pathlib import Path

# Detect if running on Vercel
IS_VERCEL = os.environ.get("VERCEL") == "1"

# Route working directory based on environment
if IS_VERCEL:
    DATA_DIR = Path(tempfile.gettempdir()) / "data"
else:
    DATA_DIR = Path(__file__).parent / "data"

DATA_DIR.mkdir(parents=True, exist_ok=True)


def save_document(file_bytes, filename):
    """Saves to local storage, or uploads to Vercel Blob if deployed."""
    file_path = DATA_DIR / filename

    # 1. Write the file (to local disk OR Vercel's /tmp)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # 2. If local, we are done. If Vercel, push to Blob for persistence.
    if IS_VERCEL:
        token = os.environ.get("BLOB_READ_WRITE_TOKEN")
        url = f"https://blob.vercel-storage.com/{filename}"

        with open(file_path, "rb") as f:
            response = requests.put(url, data=f, headers={"authorization": f"Bearer {token}"})

        # Delete temporary file from Vercel's /tmp container
        file_path.unlink()

        return response.json().get("url")  # Returns permanent Blob URL

    return str(file_path)  # Returns local system path
