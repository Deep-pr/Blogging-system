from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    bio = models.TextField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}'s profile"


class Feedback(models.Model):
    TYPE_BUG = 'Bug'
    TYPE_SUGGESTION = 'Suggestion'
    TYPE_CONTENT = 'Content issue'
    TYPE_GENERAL = 'General feedback'
    TYPE_CHOICES = (
        (TYPE_BUG, 'Bug'),
        (TYPE_SUGGESTION, 'Suggestion'),
        (TYPE_CONTENT, 'Content issue'),
        (TYPE_GENERAL, 'General feedback'),
    )

    STATUS_NEW = 'New'
    STATUS_REVIEWED = 'Reviewed'
    STATUS_RESOLVED = 'Resolved'
    STATUS_CHOICES = (
        (STATUS_NEW, 'New'),
        (STATUS_REVIEWED, 'Reviewed'),
        (STATUS_RESOLVED, 'Resolved'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='feedback_entries')
    name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    feedback_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=TYPE_GENERAL)
    subject = models.CharField(max_length=150)
    message = models.TextField(max_length=1200)
    page_url = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f"{self.subject} ({self.feedback_type})"


class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=150)
    message = models.TextField(max_length=500)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.user.username}: {self.title}'


@receiver(post_save, sender=User)
def create_or_update_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)
    else:
        Profile.objects.get_or_create(user=instance)
