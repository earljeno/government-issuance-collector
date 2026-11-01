import os
import requests
from config import DATA_DIR, EXPORTS_DIR, IS_VERCEL


def save_document(file_bytes, filename):
    """Saves to local storage, or uploads to Vercel Blob if deployed."""
    file_path = EXPORTS_DIR / filename

    # 1. Always write to the working directory first (Local disk or Vercel /tmp)
    with open(file_path, "wb") as f:
        f.write(file_bytes)

    # 2. If on Vercel, push to Blob for permanent storage
    if IS_VERCEL:
        token = os.environ.get("BLOB_READ_WRITE_TOKEN")
        url = f"https://blob.vercel-storage.com/{filename}"

        with open(file_path, "rb") as f:
            response = requests.put(url, data=f, headers={"authorization": f"Bearer {token}"})

        # Clean up the temporary Vercel file to save memory
        file_path.unlink()

        # Return the permanent cloud URL
        return response.json().get("url")

    # If local, just return the local file path
    return str(file_path)
