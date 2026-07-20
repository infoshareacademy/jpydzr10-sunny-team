from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect
from logs.utils import get_client_ip, get_lockout_until, reset_failed_attempts, log_failed_attempt
from django.utils import timezone
from datetime import timedelta
import random
from mail.models import EmailVerificationCode
from logs.models import AuthLog
from django.core.mail import send_mail

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_MINUTES = 5

User = get_user_model()


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        form.error_messages['invalid_login'] = 'Błędne dane.'
        form.error_messages['inactive'] = 'Konto nieaktywne.'
        ip_address = get_client_ip(request)
        username = request.POST.get('username', '')

        # Próba dopasowania wpisanego username do istniejącego konta
        existing_user = None
        if username:
            try:
                existing_user = User.objects.get(username=username)
            except User.DoesNotExist:
                existing_user = None

        # Blokada juz aktywna - NIC nie logujemy, tylko pokazujemy komunikat.
        lockout_until = get_lockout_until(ip_address)
        if lockout_until is not None:
            form.add_error(
                None,
                f'Zbyt wiele prób logowania. Blokada do {lockout_until.strftime("%H:%M:%S")}'
            )
            return render(request, 'login.html', {
                'form': form,
                'lockout_until': lockout_until,
            })

        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
            if user is None:
                # Login poprawny pod kątem formy, ale hasło błędne. Przekazujemy dopasowanego użytkownika.
                new_lockout = log_failed_attempt(existing_user, username, ip_address)
                if new_lockout is not None:
                    return render(request, 'login.html', {
                        'form': form,
                        'lockout_until': new_lockout,
                    })
            elif not user.is_active:
                new_lockout = log_failed_attempt(user, username, ip_address)
                if new_lockout is not None:
                    return render(request, 'login.html', {
                        'form': form,
                        'lockout_until': new_lockout,
                    })
            else:
                AuthLog.objects.create(
                    user=user,
                    username=None,
                    ip_address=ip_address,
                    action='login_success',
                    severity='info',
                    details='Poprawne uwierzytelnienie hasłem. Rozpoczęto procedurę 2FA.'
                )
                # Udane logowanie - unieważniamy poprzednie nieudane proby 
                reset_failed_attempts(username, ip_address)
                code = str(random.randint(100000, 999999))
                EmailVerificationCode.objects.create(user=user, code=code)
                request.session['2fa_user_id'] = user.id
                print(f"KOD 2FA: {code}") # DO ZMIANY NA MAILA JAK JUZ BEDZIE GOTOWY DO WYYSLEK :)
                # send_mail(
                # subject='Kod weryfikacyjny 2FA',
                # message=f'Twój kod weryfikacyjny: {code}',
                # from_email='noreply@sunnyteam.pl',
                # recipient_list=[user.email],
                # )
                return redirect('verify_2fa')
        else:
            # Formularz nie przeszedł walidacji (np. puste hasło lub nieistniejący user)
            new_lockout = log_failed_attempt(existing_user, username, ip_address)
            if new_lockout is not None:
                return render(request, 'login.html', {
                    'form': form,
                    'lockout_until': new_lockout,
                })
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    if request.user.is_authenticated:
        AuthLog.objects.create(
            user=request.user,
            username=None,
            ip_address=get_client_ip(request),
            action='logout',
            severity='info',
            details='Poprawne wylogowanie.'
        )
    logout(request)
    return redirect('login')


def home(request):
    if request.user.is_authenticated:
        pass
    return redirect('login')


def verify_2fa(request):
    user_id = request.session.get('2fa_user_id')
    if not user_id:
        return redirect('login')

    if request.method == 'POST':
        code_input = request.POST.get('code')
        try:
            user = User.objects.get(id=user_id)
            verification = EmailVerificationCode.objects.filter(
                user=user,
                is_used=False
            ).last()

            if verification and verification.code == code_input:
                verification.is_used = True
                verification.save()
                del request.session['2fa_user_id']
                login(request, user)
                return redirect('dashboard')
            else:
                return render(request, 'verify_2fa.html', {'error': 'Nieprawidłowy kod.'})
        except User.DoesNotExist:
            return redirect('login')
    return render(request, 'verify_2fa.html')