from django.contrib import admin
from django.urls import include, path
from . import views
from django.conf.urls.static import static
from django.conf import settings
from blogs import views as BlogsView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('category/', include('blogs.urls')),
    path('blogs/search/', BlogsView.search, name='search'),
    path('blogs/<slug:slug>/', BlogsView.blogs, name='blogs'),

    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('feedback/', views.feedback, name='feedback'),

    path('verify-email/<uuid:token>/', views.verify_email, name='verify_email'),
    path('resend-verification/', views.resend_verification, name='resend_verification'),

    # ── New ──────────────────────────────────────────────────
    path('verify-wait/<int:user_id>/', views.verify_wait, name='verify_wait'),
    path('check-verification/<int:user_id>/', views.check_verification, name='check_verification'),

    path('dashboard/', include('dashboards.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
