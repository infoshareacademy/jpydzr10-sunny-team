from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

def send_approval_notification(employee_email, employee_name, request_details, site_url=None):
    """
    Wysyła mail do pracownika o zatwierdzeniu wniosku.
    """
    if site_url is None:
        site_url = settings.SITE_URL

    subject = 'Twój wniosek urlopowy został zatwierdzony'
    html_message = render_to_string('emails/request_approved.html', {
        'employee_name': employee_name,
        'request_details': request_details,
        'site_url': site_url,
    })
    send_mail(
        subject,
        '',  # wiadomość tekstowa (pusta, bo używamy HTML)
        settings.DEFAULT_FROM_EMAIL,
        [employee_email],
        html_message=html_message,
        fail_silently=False,
    )

def send_reject_notification(employee_email, employee_name, request_details, rejection_reason=None, site_url=None):
    """
    Wysyła mail do pracownika o odrzuceniu wniosku.
    """
    if site_url is None:
        site_url = settings.SITE_URL

    subject = 'Twój wniosek urlopowy został odrzucony'
    html_message = render_to_string('emails/request_rejected.html', {
        'employee_name': employee_name,
        'request_details': request_details,
        'rejection_reason': rejection_reason,
        'site_url': site_url,
    })
    send_mail(
        subject,
        '',
        settings.DEFAULT_FROM_EMAIL,
        [employee_email],
        html_message=html_message,
        fail_silently=False,
    )