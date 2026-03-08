from django.contrib import admin
from blogs.models import Blog
from blogs.models import Category



class BlogAdmin(admin.ModelAdmin):
    prepopulated_fields = {'slug': ('title',)}
    list_display = ('title', 'author', 'category', 'status', 'is_featured', 'created_at')
    search_fields = ('id', 'title', 'status', 'author__username', 'category__category_name')
    list_editable = ('is_featured',)

admin.site.register(Category)
admin.site.register(Blog, BlogAdmin)