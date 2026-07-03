from django.shortcuts import render

def reports_index(request):
    return render(request, 'reports/index.html')