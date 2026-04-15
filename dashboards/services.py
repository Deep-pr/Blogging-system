from django.contrib.auth.models import User

from .models import Notification


def notify_managers(title, message, link=''):
    manager_ids = User.objects.filter(groups__name='Manager', is_active=True).values_list('id', flat=True).distinct()
    for manager_id in manager_ids:
        Notification.objects.create(
            user_id=manager_id,
            title=title,
            message=message,
            link=link,
        )
