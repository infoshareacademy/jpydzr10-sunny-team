from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
import random
from django.utils.translation import gettext_lazy as _
class MainPageView(LoginRequiredMixin,TemplateView):
    template_name = 'core/main.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        request = self.request
        user = request.user
        active_role = request.session.get('active_role', getattr(user, 'role', None))

        phrases = {
            'Worker': [
                _("Planujesz zasłużony odpoczynek czy na razie po prostu sprawdzasz, ile dni wolnych Ci zostało?"),
                _("Szukasz idealnego momentu na złapanie oddechu czy masz już konkretne plany na wyjazd?"),
                _("Czas na ładowanie baterii? Sprawdź swój kalendarz i zaplanuj kolejny urlop."),
                _("Pogoda za oknem kusi – myślisz już o wolnym piątku czy sprawdzasz opcje na dłuższy wypad?"),
                _("Masz już w głowie plan na kolejny relaks czy potrzebujesz chwili, by go spokojnie rozpisać?"),
            ],
            'Manager': [
                _("Planujesz własny urlop czy przyszedł czas na zatwierdzanie wniosków w Twoim zespole?"),
                _("Szykuje się chwila wytchnienia czy trzymasz rękę na pulsie i sprawdzasz dostępność ekipy?"),
                _("Twój zespół myśli już o wakacjach – czas zerknąć w grafik i zadbać o ciągłość pracy."),
                _("Przeglądasz kalendarz pod kątem własnych planów czy pomagasz zespołowi w organizacji wolnego?"),
                _("Chwila dla siebie czy szybka weryfikacja planów urlopowych Twoich ludzi? Zobaczmy, co w projekcie."),
            ],
            'HR': [
                _("Planujesz własny wyjazd czy czuwasz dziś nad urlopowym porządkiem w całej firmie?"),
                _("Szykuje się urlopowa ucieczka od biurka czy pilnujesz, żeby w naszym kalendarzu wszystko idealnie grało?"),
                _("Sprawdzasz statusy zaległych wniosków czy kompletujesz dokumenty przed własnymi wakacjami?"),
                _("Dbasz o to, by każdy w firmie mógł spokojnie odpocząć – a kiedy czas na Twój relaks?"),
                _("Masz dziś oko na plany urlopowe wszystkich działów czy właśnie domykasz swój własny wniosek?"),
            ],
        }

        role_phrases = phrases.get(active_role, phrases.get('Worker'))
        context['random_role_phrase'] = random.choice(role_phrases)
        context['active_role'] = active_role

        return context

