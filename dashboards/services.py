from django.contrib.auth.models import User

from .models import Notification, Profile


def user_allows_notification(user, preference_name):
    if user is None:
        return False

    profile, _ = Profile.objects.get_or_create(user=user)
    return getattr(profile, preference_name, True)


def create_user_notification(user, title, message, link='', preference_name=None):
    if user is None:
        return None

    if preference_name and not user_allows_notification(user, preference_name):
        return None

    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        link=link,
    )


def notify_managers(title, message, link=''):
    manager_ids = (
        User.objects.filter(
            groups__name='Manager',
            is_active=True,
            profile__notify_staff_alerts=True,
        )
        .values_list('id', flat=True)
        .distinct()
    )
    for manager_id in manager_ids:
        Notification.objects.create(user_id=manager_id, title=title, message=message, link=link)
