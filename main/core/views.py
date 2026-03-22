from django.contrib.auth import logout
from django.views.decorators.http import require_POST
from django.shortcuts import redirect

@require_POST
def logout_view(request):
    # Delete the session row entirely so it vanishes from live_users
    try:
        request.session.delete()
    except Exception:
        pass
    logout(request)
    return redirect('login')