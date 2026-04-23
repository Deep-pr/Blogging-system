from django.db import models
from django.contrib.auth.models import User
import uuid
from django.utils import timezone
from django.utils.html import strip_tags
from datetime import timedelta
from django.urls import reverse
import math
import re


class Category(models.Model):
    category_name = models.CharField(max_length=50, unique=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='categories')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = 'categories'

    def __str__(self):
        return self.category_name
    

STATUS_CHOICES = (
    ("Draft", "Draft"),
    ("Published", "Published")
)

class Blog(models.Model):
    title = models.CharField(max_length=100)
    slug = models.SlugField(max_length=150, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    featured_image = models.ImageField(upload_to='posts/featured/%Y/%m/%d')
    short_description = models.TextField(max_length=500)
    blog_body = models.TextField(max_length=5000)
    seo_description = models.CharField(max_length=160, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Draft")
    is_featured = models.BooleanField(default=False)
    scheduled_for = models.DateTimeField(blank=True, null=True)
    published_at = models.DateTimeField(blank=True, null=True)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def estimated_read_time(self):
        content = ' '.join(
            part for part in [
                self.short_description or '',
                strip_tags(self.blog_body or ''),
            ]
            if part
        )
        words = len(re.findall(r"\b[\w'-]+\b", content))
        return max(1, math.ceil(words / 180))

    @property
    def meta_description(self):
        return self.seo_description or self.short_description

    def get_absolute_url(self):
        return reverse('blogs', kwargs={'slug': self.slug})


class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE)
    comment = models.TextField(max_length=250)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.comment


class Bookmark(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookmarks')
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE, related_name='bookmarks')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'blog')
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.user.username} saved {self.blog.title}'


class AuthorFollow(models.Model):
    follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followed_authors')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='author_followers')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('follower', 'author')
        ordering = ('-created_at',)

    def __str__(self):
        return f'{self.follower.username} follows {self.author.username}'


class NewsletterSubscription(models.Model):
    email = models.EmailField(unique=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='newsletter_subscriptions')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return self.email


class PostReaction(models.Model):
    LIKE = 'Like'
    INSIGHTFUL = 'Insightful'
    HELPFUL = 'Helpful'
    REACTION_CHOICES = (
        (LIKE, 'Like'),
        (INSIGHTFUL, 'Insightful'),
        (HELPFUL, 'Helpful'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_reactions', null=True, blank=True)
    guest_token = models.CharField(max_length=40, blank=True)
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE, related_name='reactions')
    reaction_type = models.CharField(max_length=20, choices=REACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)
        constraints = [
            models.UniqueConstraint(
                fields=('user', 'blog', 'reaction_type'),
                condition=models.Q(user__isnull=False),
                name='unique_user_post_reaction',
            ),
            models.UniqueConstraint(
                fields=('guest_token', 'blog', 'reaction_type'),
                condition=models.Q(user__isnull=True) & ~models.Q(guest_token=''),
                name='unique_guest_post_reaction',
            ),
        ]

    def __str__(self):
        actor = self.user.username if self.user else f'guest:{self.guest_token[:8]}'
        return f'{actor} · {self.reaction_type} · {self.blog.title}'


class ContentReport(models.Model):
    STATUS_NEW = 'New'
    STATUS_REVIEWED = 'Reviewed'
    STATUS_RESOLVED = 'Resolved'
    STATUS_CHOICES = (
        (STATUS_NEW, 'New'),
        (STATUS_REVIEWED, 'Reviewed'),
        (STATUS_RESOLVED, 'Resolved'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='content_reports')
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE, related_name='reports')
    reason = models.CharField(max_length=100)
    details = models.TextField(max_length=1000, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ('-created_at',)

    def __str__(self):
        return f'Report for {self.blog.title}'


# ── Email Verification ─────────────────────────────────────────
class EmailVerificationToken(models.Model):
    user        = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_token')
    token       = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at  = models.DateTimeField(auto_now_add=True)
    is_verified = models.BooleanField(default=False)

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(hours=24)

    def __str__(self):
        return f"Token for {self.user.email}"
