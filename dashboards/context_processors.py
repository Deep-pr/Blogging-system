from .models import Notification, Profile


def current_user_profile(request):
    if request.user.is_authenticated:
        profile, _ = Profile.objects.get_or_create(user=request.user)
        unread_notification_count = Notification.objects.filter(user=request.user, is_read=False).count()
        return {
            'current_user_profile': profile,
            'unread_notification_count': unread_notification_count,
        }
    return {
        'current_user_profile': None,
        'unread_notification_count': 0,
    }
