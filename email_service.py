import os
import base64
import requests

RESEND_API_KEY = "re_j8zYKZKg_77Asx1Vy39fAZgzHDWfcw6UN"

def send_email_with_mp3(
    to_email: str,
    mp3_path: str,
    from_email: str = "lasha@tvitkitxva.ge",
    reply_to: str = "lasha@tvitkitxva.ge",
):
    with open(mp3_path, "rb") as f:
        mp3_b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "from": from_email,
        "to": [to_email],
        "subject": "MP3 ფაილი მზადაა! - tvitkitxva.ge",
        "text": "🎧 ახლა კი, შეგიძლია მოუსმინო.\n📣 ნებისმიერ დროს შემოდი: tvitkitxva.ge\n-----------\n💜 შესრულებულია TvitKikxvAI მიერ 🤖",
        "reply_to": reply_to,
        "attachments": [
            {
                "filename": os.path.basename(mp3_path),
                "content": mp3_b64,
            }
        ],
    }

    r = requests.post(
        "https://api.resend.com/emails",
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    if r.status_code >= 400:
        raise RuntimeError(f"Resend error {r.status_code}: {r.text}")

    return r.json()
