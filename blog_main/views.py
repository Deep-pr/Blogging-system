

from blogs.models import Blog, Category
from django.shortcuts import render
from about.models import About

def home(request):
   
    featured_posts= Blog.objects.filter(is_featured=True, status='Published').order_by('updated_at')
    posts = Blog.objects.filter(is_featured=False, status='Published')
    
    
    try:
        about = About.objects.get()
    except:
        about = None

    context={
        'about': about,
        'featured_posts': featured_posts,
        'posts': posts
    }
    return render(request, 'home.html', context)