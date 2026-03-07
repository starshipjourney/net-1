from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import never_cache

def login_view(request):
    # if already logged in redirect to dashboard
    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard')
        else:
            messages.error(request, 'INVALID CREDENTIALS')

    return render(request, 'interface/login.html')

def logout_view(request):
    logout(request)
    return redirect('login')

@never_cache
@login_required(login_url='login')
def dashboard_view(request):
    return render(request, 'interface/dashboard.html')
