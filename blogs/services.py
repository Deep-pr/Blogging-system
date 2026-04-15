from django.utils import timezone

from dashboards.models import Notification

from .models import AuthorFollow, Blog


def notify_followers_of_post(post):
    follower_ids = AuthorFollow.objects.filter(author=post.author).values_list('follower_id', flat=True)
    for follower_id in follower_ids:
        if Notification.objects.filter(
            user_id=follower_id,
            title=f'New post from {post.author.username}',
            link=post.get_absolute_url(),
        ).exists():
            continue

        Notification.objects.create(
            user_id=follower_id,
            title=f'New post from {post.author.username}',
            message=f'"{post.title}" is now live. Tap to read the latest post from an author you follow.',
            link=post.get_absolute_url(),
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
        Notification.objects.get_or_create(
            user=post.author,
            title=f'"{post.title}" is now live',
            defaults={
                'message': 'Your scheduled post has been published.',
                'link': post.get_absolute_url(),
            },
        )
        notify_followers_of_post(post)
