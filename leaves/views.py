from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .services import count_leave_days_service

# Create your views here.

@login_required(login_url='/accounts/login/')
def dashboard(request):
    context = {
        'title': 'Dashboard Urlopowy',
    }
    return render(request, 'leaves/dashboard.html', context)

@login_required
def vacation_list(request):
    return render(request, 'leaves/vacation_list.html')

@login_required
def all_requests_list(request):
    return render(request, 'leaves/all_requests_list.html')

#@login_required
def new_request(request):
    return render(request, 'leaves/new_request.html')

#@login_required
def calculate_days_api(request):
    try:
        count = count_leave_days_service(
            request.GET.get('start'),
            request.GET.get('end')
        )
        return JsonResponse({'count': count})
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)

