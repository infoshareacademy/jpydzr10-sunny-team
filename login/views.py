from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import render, redirect
from django.utils import timezone
from datetime import timedelta
import random
from logs.models import EmailVerificationCode
from accounts.models import User
from logs.models import LoginAttempt
from logs.utils import get_client_ip
from django.core.mail import send_mail

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_WINDOW_MINUTES = 5


def is_locked_out(username, ip_address):
    """Sprawdza czy dla danego username/IP przekroczono limit nieudanych prob logowania w oknie czasowym."""
    since = timezone.now() - timedelta(minutes=LOCKOUT_WINDOW_MINUTES)
    failed_count = LoginAttempt.objects.filter(
        username=username,
        ip_address=ip_address,
        success=False,
        invalidated=False,
        timestamp__gte=since,
    ).count()
    return failed_count >= MAX_FAILED_ATTEMPTS

def reset_failed_attempts(username, ip_address):
    """
    Oznacza dotychczasowe nieudane proby jako 'invalidated' po udanym zalogowaniu.
    Historia zostaje w bazie, ale nie liczy sie juz do lockout.
    """
    LoginAttempt.objects.filter(
        username=username,
        ip_address=ip_address,
        success=False,
        invalidated=False,
    ).update(invalidated=True)


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        form.error_messages['invalid_login'] = 'Invalid credentials.'
        form.error_messages['inactive'] = 'This account is disabled.'
        ip_address = get_client_ip(request)
        username = request.POST.get('username', '')

        if is_locked_out(username, ip_address):
            form.add_error(
                None,
                f'Too many failed login attempts. Try again in {LOCKOUT_WINDOW_MINUTES} minutes.'
            )
            return render(request, 'login.html', {'form': form})

        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'],
            )
            if user is None:
                LoginAttempt.objects.create(
                    user=None,
                    username=username,
                    ip_address=ip_address,
                    success=False,
                )
                form.add_error(None, 'Invalid credentials.')
            elif not user.is_active:
                LoginAttempt.objects.create(
                    user=user,
                    username=username,
                    ip_address=ip_address,
                    success=False,
                )
                form.add_error(None, 'This account is disabled.')
            else:
                LoginAttempt.objects.create(
                    user=user,
                    username=username,
                    ip_address=ip_address,
                    success=True,
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
            LoginAttempt.objects.create(
                user=None,
                username=username,
                ip_address=ip_address,
                success=False,
            )
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})


def logout_view(request):
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