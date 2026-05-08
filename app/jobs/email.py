import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.distributed.circuit_breaker import email_breaker

async def execute_email_job(payload: dict) -> str:
    recipient = payload.get("email", "test@gmail.com")
    subject = payload.get("subject", "Hello from Job Scheduler!")
    body = payload.get("body", "This was sent by your Distributed Job Scheduler!")

    if not email_breaker.can_call():
        raise Exception("Email service unavailable! Circuit breaker is OPEN!")

    try:
        print("Sending REAL email to " + recipient)

        msg = MIMEMultipart()
        msg['From'] = os.getenv("EMAIL_FROM")
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(
                os.getenv("EMAIL_FROM"),
                os.getenv("EMAIL_PASSWORD")
            )
            server.send_message(msg)

        email_breaker.on_success()
        print("Email sent to " + recipient + "!")
        return "Email successfully sent to " + recipient + "!"

    except Exception as e:
        email_breaker.on_failure()
        raise Exception("Email failed: " + str(e))