from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings


def send_approval_notification(employee_email, employee_name, request_details, site_url=None):
    # Wysyła mail do pracownika o zatwierdzeniu wniosku.
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
    # Wysyła mail do pracownika o odrzuceniu wniosku.
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


def send_new_request_notification(manager_emails, employee_name, request_details, submission_date, site_url=None):
    # Wysyła mail do Menager/HR o nowym wniosku.
    if site_url is None:
        site_url = settings.SITE_URL
    subject = f"Nowy wniosek urlopowy od {employee_name}"
    html_message = render_to_string(
        "emails/new_request_notification.html",
        {
            "employee_name": employee_name,
            "request_details": request_details,
            "submission_date": submission_date,
            "site_url": site_url,
        }
    )
    send_mail(
        subject,
        "",
        settings.DEFAULT_FROM_EMAIL,
        manager_emails,
        html_message=html_message,
        fail_silently=False,
    )


def send_welcome_email(user_email, user_name, username, password, site_url=None):
    # Wysyła mail powitalny do nowego użytkownika z danymi logowania.
    if site_url is None:
        site_url = settings.SITE_URL

    subject = f"Witaj w systemie SunnyTeam, {user_name}!"
    html_message = render_to_string(
        "emails/welcome_email.html",
        {
            "user_name": user_name,
            "username": username,
            "password": password,  # Uwaga: hasło jest widoczne w mailu tylko przy pierwszej rejestracji
            "site_url": site_url,
        }
    )
    send_mail(
        subject,
        "",
        settings.DEFAULT_FROM_EMAIL,
        [user_email],
        html_message=html_message,
        fail_silently=False,
    )


def send_deactivation_email(user_email, user_name, site_url=None):
    # Wysyła mail do użytkownika informujący o dezaktywacji konta.
    if site_url is None:
        site_url = settings.SITE_URL

    subject = 'Twoje konto w SunnyTeam zostało dezaktywowane'
    html_message = render_to_string('emails/account_deactivated.html', {
        'user_name': user_name,
        'site_url': site_url,
    })
    send_mail(
        subject,
        '',
        settings.DEFAULT_FROM_EMAIL,
        [user_email],
        html_message=html_message,
        fail_silently=False,
    )