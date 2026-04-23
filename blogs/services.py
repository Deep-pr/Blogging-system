from django.contrib.auth.models import User
from django.utils import timezone

from dashboards.models import Notification
from dashboards.services import create_user_notification

from .models import AuthorFollow, Blog


def notify_followers_of_post(post):
    follower_ids = AuthorFollow.objects.filter(
        author=post.author,
        follower__profile__notify_post_updates=True,
    ).values_list('follower_id', flat=True)
    followers = User.objects.filter(id__in=follower_ids).select_related('profile')
    for follower in followers:
        if Notification.objects.filter(
            user=follower,
            title=f'New post from {post.author.username}',
            link=post.get_absolute_url(),
        ).exists():
            continue

        create_user_notification(
            user=follower,
            title=f'New post from {post.author.username}',
            message=f'"{post.title}" is now live. Tap to read the latest post from an author you follow.',
            link=post.get_absolute_url(),
            preference_name='notify_post_updates',
        )


def publish_scheduled_posts():
    due_posts = Blog.objects.filter(
        status='Draft',
        scheduled_for__isnull=False,
        scheduled_for__lte=timezone.now(),
    ).select_related('author')

    for post in due_posts:
        post.status = 'Published'
        if not post.published_at:
            post.published_at = timezone.now()
        post.save(update_fields=['status', 'published_at', 'updated_at'])
        create_user_notification(
            user=post.author,
            title=f'"{post.title}" is now live',
            message='Your scheduled post has been published.',
            link=post.get_absolute_url(),
            preference_name='notify_post_updates',
        )
        notify_followers_of_post(post)
