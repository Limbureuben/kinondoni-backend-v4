from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings

@shared_task
def send_reset_email_task(email, reset_link):
    send_mail(
        subject='Password Reset',
        message=f'Click the link to reset your password: {reset_link}',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email]
    )
