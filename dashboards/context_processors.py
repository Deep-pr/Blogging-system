from .models import Profile


def current_user_profile(request):
    if request.user.is_authenticated:
        profile, _ = Profile.objects.get_or_create(user=request.user)
        return {'current_user_profile': profile}
    return {'current_user_profile': None}
