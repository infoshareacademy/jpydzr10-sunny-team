from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import PasswordChangeView

from django.shortcuts import render, redirect
from django.urls import reverse_lazy

from logs.models import AuthLog
from logs.utils import get_client_ip, get_lockout_until, reset_failed_attempts, log_failed_attempt
import random
from mail.models import EmailVerificationCode
from django.core.mail import send_mail
from django.utils.translation import gettext_lazy as _
from django.utils.text import format_lazy
from logs.models import EmailVerificationCode, PasswordResetToken


User = get_user_model()


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        form.error_messages['invalid_login'] = _('Błędne dane.')
        form.error_messages['inactive'] = _('Konto nieaktywne.')
        ip_address = get_client_ip(request)
        raw_username = request.POST.get('username', '')

        # Próba dopasowania wpisanego username do istniejącego konta
        existing_user = User.objects.filter(username=raw_username).first()

        # Blokada juz aktywna - NIC nie logujemy, tylko pokazujemy komunikat.
        lockout_until = get_lockout_until(ip_address)
        if lockout_until is not None:
            form.add_error(
                None,
                format_lazy(
                    _('Zbyt wiele prób logowania. Blokada do {time}.'),
                    time=lockout_until.strftime("%H:%M:%S")
                )
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
            if user is None or not user.is_active:
                new_lockout = log_failed_attempt(existing_user, raw_username, ip_address)
                if new_lockout is not None:
                    return render(request, 'login.html', {
                        'form': form,
                        'lockout_until': new_lockout,
                    })
            else:
                AuthLog.objects.create(
                    user=user,
                    ip_address=ip_address,
                    action='login_success',
                    severity='info',
                    details=_('Poprawne uwierzytelnienie hasłem. Rozpoczęto procedurę 2FA.')
                )
                # Udane logowanie - unieważniamy poprzednie nieudane proby
                reset_failed_attempts(ip_address)
                code = str(random.randint(100000, 999999))
                EmailVerificationCode.objects.create(user=user, code=code)
                request.session['2fa_user_id'] = user.id
                print(f"KOD 2FA: {code}")
                send_mail(
                     subject=_('Kod weryfikacyjny 2FA'),
                     message=_('Twój kod weryfikacyjny: %(code)s') % {'code': code},
                     from_email='noreply@sunnyteam.pl',
                     recipient_list=[user.email],
                )
                return redirect('verify_2fa')
        else:
            # Formularz nie przeszedł walidacji (np. puste hasło lub nieistniejący user)
            new_lockout = log_failed_attempt(existing_user, raw_username, ip_address)
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
            ip_address=get_client_ip(request),
            action='logout',
            severity='info',
            details=_('Poprawne wylogowanie.')
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
        ip_address = get_client_ip(request)
        try:
            user = User.objects.get(id=user_id)
            verification = EmailVerificationCode.objects.filter(
                user=user,
                is_used=False
            ).last()

            if verification and verification.code == code_input:
                verification.is_used = True
                verification.save()
                AuthLog.objects.create(
                    user=user,
                    ip_address=ip_address,
                    action='2fa_success',
                    severity='info',
                    details=_('Pomyślna weryfikacja dwuetapowa (2FA). Zalogowano użytkownika.')
                )
                login(request, user)
                if '2fa_user_id' in request.session:
                    del request.session['2fa_user_id']
                request.session['must_change_password'] = user.must_change_password
                if user.must_change_password:
                    return redirect('first_password_change')
                return redirect('home')

            else:
                AuthLog.objects.create(
                    user=user,
                    ip_address=ip_address,
                    action='2fa_failed',
                    severity='warning',
                    details=_("Wprowadzono błędny kod 2FA.")
                )
                return render(request, 'verify_2fa.html', {'error': _('Nieprawidłowy kod.')})
        except User.DoesNotExist:
            return redirect('login')
    return render(request, 'verify_2fa.html')

class FirstPasswordChangeView(PasswordChangeView):
    template_name = 'first_password_change.html'
    success_url = reverse_lazy('first_password_change_done')

    def form_valid(self, form):
        user = self.request.user
        user.must_change_password = False
        user.save()
        self.request.session['must_change_password'] = False
        AuthLog.objects.create(
            user=user,
            ip_address=get_client_ip(self.request),
            action='password_changed',
            severity='info',
            details=_('Użytkownik pomyślnie zmienił tymczasowe hasło.')
        )

        return super().form_valid(form)
    
    return render(request, 'verify_2fa.html')

def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = User.objects.get(email=email)
            token = PasswordResetToken.objects.create(user=user)
            reset_link = f"http://127.0.0.1:8000/login/reset-password/{token.token}/"
            print(f"LINK RESETU: {reset_link}")  # TODO: zastąpić send_mail 
            # send_mail(
            #     subject='Reset hasła - Sunny Team',
            #     message=f'Kliknij w link aby zresetować hasło: {reset_link}',
            #     from_email='noreply@sunnyteam.pl',
            #     recipient_list=[user.email],
            # )
        except User.DoesNotExist:
            pass  
    return render(request, 'forgot_password.html')


def reset_password_confirm(request, token):
    try:
        reset_token = PasswordResetToken.objects.get(token=token, is_used=False)
    except PasswordResetToken.DoesNotExist:
        return render(request, 'reset_password_confirm.html', {'error': 'Nieprawidłowy lub wygasły link.'})

    if reset_token.is_expired():
       return render(request, 'reset_password_confirm.html', {'error': 'Link wygasł.'})
    
    if request.method == 'POST':
        new_password = request.POST.get('password')
        if len(new_password) < 6:
            return render(request, 'reset_password_confirm.html', {'error': 'Hasło musi mieć co najmniej 6 znaków.'})
        reset_token.user.set_password(new_password)
        reset_token.user.save()
        reset_token.is_used = True
        reset_token.save()
        return redirect('login')

    return render(request, 'reset_password_confirm.html')
