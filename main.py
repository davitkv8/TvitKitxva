import uvicorn

import shutil

from fastapi import FastAPI, File, UploadFile, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from elevenlabs.client import ElevenLabs

from PyPDF2 import PdfReader

from email_service import send_mp3_attachment

from pydantic import BaseModel, HttpUrl
from urllib.parse import urlparse
import httpx
import uuid
import pathlib

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tvitkitxva.ge", "https://api.tvitkitxva.ge", "0.0.0.0", "127.0.0.1"],
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

elevenlabs = ElevenLabs(
  api_key="sk_4e851ab64487d8f751cf6fc44ec111aa8097f568ccc318b8",
)

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_SIZE = 2 * 1024 * 1024  # 2 MB in bytes


class UploadFromUrlPayload(BaseModel):
    file_url: HttpUrl


def validate_source_url(url: str) -> None:
    """
    SSRF დაცვისთვის: არ მივცეთ ნებისმიერ URL-ზე request-ის გაკეთების უფლება.
    ამ შემთხვევაში ვუშვებთ მხოლოდ tawk-ის ჰოსტებს.
    """
    host = (urlparse(url).netloc or "").lower()
    allowed = (
        host.endswith("tawk.link")
        or host.endswith("tawk.to")
        or host.endswith("embed.tawk.to")
    )
    if not allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file host: {host}")


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.post("/upload-pdf-from-url")
async def upload_pdf_from_url(
    payload: UploadFromUrlPayload,
    recipient_email: str = Query(..., min_length=3),
):
    file_url = str(payload.file_url)
    validate_source_url(file_url)

    # უნიკალური სახელი (სურვილისამებრ ცალკე საქაღალდე email-ით)
    dest_path = UPLOAD_DIR / f"{uuid.uuid4()}.pdf"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60) as client:
            resp = await client.get(file_url)

            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to download file from source (status {resp.status_code})",
                )

            content_type = (resp.headers.get("content-type") or "").lower()
            # ზოგჯერ content-type შეიძლება არ იყოს იდეალური, მაგრამ ვეცდებით შევამოწმოთ
            if ("pdf" not in content_type) and (not file_url.lower().endswith(".pdf")):
                raise HTTPException(status_code=400, detail=f"Not a PDF (content-type={content_type})")

            # streaming write (დიდ ფაილებზე RAM-ს არ ჭამს)
            with dest_path.open("wb") as f:
                async for chunk in resp.aiter_bytes():
                    f.write(chunk)

    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Download error: {type(e).__name__}")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Download timeout")


    return {
        "ok": True,
        "recipient_email": recipient_email,
        "saved_file": dest_path.name,
        "source_url": file_url,
    }


@app.post("/upload-pdf")
async def upload_pdf(recipient_email: str, file: UploadFile = File(...)):
    # 1) Basic validation
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    # 2) Read file content to validate its size (max 2MB)
    content = await file.read()

    if len(content) > MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File too large. Max allowed size is 2MB"
        )

    # Reset pointer so saving still works
    file.file.seek(0)

    # 3) Build a safe path
    file_path = UPLOAD_DIR / file.filename

    # 4) Save to disk (streaming)
    try:
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        await file.close()

        # 5) Read content back from saved file
        text = ""
        with file_path.open("rb") as f:
            reader = PdfReader(f)
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"

        print("======== PDF CONTENT START ========\n\n\n")
        print(text)
        print("======== PDF CONTENT END ==========\n\n\n")


        print("======== SENDING PDF TO ELEVENLABS ========")
        audio = elevenlabs.text_to_speech.convert(
            text=text,
            voice_id="JBFqnCBsd6RMkjVDRZzb",
            model_id="eleven_flash_v2_5",
            output_format="mp3_22050_32",
        )
        print("======== AUDIO CONTENT RECEIVED ========")

        mp3_filename = f"{file.filename.split('.')[0]}.mp3"
        with open(mp3_filename, "wb") as f:
            for chunk in audio:
                f.write(chunk)

        mid = send_mp3_attachment(
            to_email=recipient_email,
            subject="Your MP3 is ready",
            mp3_file_path=mp3_filename,
        )

        print(f"Finishing ..... {mid}")

    return {
        "filename": file.filename,
        "saved_as": str(file_path),
        "message": "File uploaded and saved successfully",
        "status": 200,
    }


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # for dev only
    )