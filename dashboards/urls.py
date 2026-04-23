from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('profile/', views.my_profile, name='my_profile'),
    path('profile/edit/', views.edit_my_profile, name='edit_my_profile'),
    path('settings/', views.settings_page, name='settings'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/open/<int:pk>/', views.open_notification, name='open_notification'),
    path('feedback/', views.feedback_list, name='dashboard_feedback'),
    path('feedback/edit/<int:pk>/', views.edit_feedback, name='edit_feedback'),
    path('reports/', views.reports, name='reports'),
    path('reports/edit/<int:pk>/', views.edit_report, name='edit_report'),
    path('reports/delete/<int:pk>/', views.delete_report, name='delete_report'),
    
    path('categories/', views.categories, name='categories'),
    path('categories/add/', views.add_category, name='add_category'),
    path('categories/edit/<int:pk>/', views.edit_category, name='edit_category'),
    path('categories/delete/<int:pk>/', views.delete_category, name='delete_category'),
    
    path('posts/', views.posts, name='posts'),
    path('posts/add/', views.add_post, name='add_post'),
    path('posts/edit/<int:pk>/', views.edit_post, name='edit_post'),
    path('posts/delete/<int:pk>/', views.delete_post, name='delete_post'),
    path('posts/preview/<int:pk>/', views.preview_post, name='preview_post'),
    path('saved-posts/', views.saved_posts, name='saved_posts'),
    path('analytics/', views.analytics, name='analytics'),
    path('followers/', views.followers, name='followers'),
    path('users/', views.users, name='users'),
    path('users/add/', views.add_user, name='add_user'),
    path('users/edit/<int:pk>/', views.edit_user, name='edit_user'),
    path('users/delete/<int:pk>/', views.delete_user, name='delete_user'),
]
