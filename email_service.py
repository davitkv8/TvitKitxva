import boto3
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

REGION = "eu-central-1"
FROM = "davitkvaratskhelia@shipifydev.com"

ses = boto3.client("sesv2", region_name=REGION)

def send_mp3_attachment(to_email: str, mp3_file_path: str, subject: str = 'შენი ტექსტი მზადაა!'):

    text = "შესრულებულია TvitKikxvAI ტექსტის გენერატეორების დეპარტამენტის მიერ.\n\nნებისმიერ დროს შემოდი: tvitkitxva.ge"

    mp3_path = Path(mp3_file_path)
    if not mp3_path.exists():
        raise FileNotFoundError(mp3_path)

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = FROM
    msg["To"] = to_email

    msg.attach(MIMEText(text, "plain", "utf-8"))

    part = MIMEBase("audio", "mpeg")
    part.set_payload(mp3_path.read_bytes())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{mp3_path.name}"')
    msg.attach(part)

    raw_bytes = msg.as_bytes()

    resp = ses.send_email(
        FromEmailAddress=FROM,
        Destination={"ToAddresses": [to_email]},
        Content={"Raw": {"Data": raw_bytes}},
    )
    return resp["MessageId"]
