from django.contrib import admin
from .models import (
    AuthorFollow,
    Blog,
    Bookmark,
    Category,
    Comment,
    ContentReport,
    NewsletterSubscription,
    PostReaction,
)

class BlogAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('title',)}
    list_display = ('title', 'category', 'author', 'status', 'scheduled_for', 'view_count', 'is_featured')
    search_fields = ('id', 'title', 'category__category_name', 'status')
    list_filter = ('status', 'category', 'is_featured')
    list_editable = ('is_featured',)

admin.site.register(Category)
admin.site.register(Blog, BlogAdmin)
admin.site.register(Comment)
admin.site.register(Bookmark)
admin.site.register(AuthorFollow)
admin.site.register(NewsletterSubscription)
admin.site.register(PostReaction)
admin.site.register(ContentReport)
