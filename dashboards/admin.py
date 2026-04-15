from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User

from .models import Feedback, Notification, Profile


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0
    fields = ('profile_image', 'bio', 'created_at', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')


class CustomUserAdmin(UserAdmin):
    inlines = (ProfileInline,)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'has_profile_image', 'updated_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')

    def has_profile_image(self, obj):
        return bool(obj.profile_image)

    has_profile_image.boolean = True
    has_profile_image.short_description = 'Photo'


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('subject', 'feedback_type', 'status', 'name', 'email', 'created_at')
    list_filter = ('feedback_type', 'status', 'created_at')
    search_fields = ('subject', 'message', 'name', 'email', 'page_url')
    readonly_fields = ('created_at', 'updated_at')

    def can_view_feedback(self, request):
        return request.user.is_superuser or request.user.groups.filter(name='Manager').exists()

    def has_module_permission(self, request):
        return self.can_view_feedback(request)

    def has_view_permission(self, request, obj=None):
        return self.can_view_feedback(request)

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('title', 'user', 'is_read', 'created_at')
    list_filter = ('is_read', 'created_at')
    search_fields = ('title', 'message', 'user__username')
    readonly_fields = ('created_at',)


admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
