from django.shortcuts import render, redirect, get_object_or_404
from blogs.models import Blog, Category
from django.contrib.auth.decorators import login_required
from .forms import CategoryForm, BlogPostForm, AddUserForm, EditUserForm
from django.template.defaultfilters import slugify
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied


# ── Permission helpers ─────────────────────────────────────────
def can_modify_post(user, post):
    if user.is_superuser:
        return True
    if user.is_staff:
        return True
    if user.groups.filter(name='Manager').exists():
        return True
    if user.groups.filter(name='Editor').exists() and post.author == user:
        return True
    return False


def can_modify_user(requesting_user, target_user):
    """Manager cannot edit or delete superusers. Only superuser can."""
    if requesting_user.is_superuser:
        return True
    if target_user.is_superuser:
        return False
    return True


# ── Dashboard ──────────────────────────────────────────────────
@login_required(login_url='login')
def dashboard(request):
    first_login = request.session.pop('first_login', False)
    welcome = 'Welcome' if first_login else 'Welcome back'

    category_count = Category.objects.all().count()
    blogs_count = Blog.objects.all().count()

    context = {
        'category_count': category_count,
        'blogs_count': blogs_count,
        'welcome': welcome,
    }
    return render(request, 'dashboard/dashboard.html', context)


# ── Categories ─────────────────────────────────────────────────
def categories(request):
    return render(request, 'dashboard/categories.html')


def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('categories')
    else:
        form = CategoryForm()
    context = {'form': form}
    return render(request, 'dashboard/add_category.html', context)


def edit_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            return redirect('categories')
    else:
        form = CategoryForm(instance=category)
    context = {'form': form, 'category': category}
    return render(request, 'dashboard/edit_category.html', context)


def delete_category(request, pk):
    category = get_object_or_404(Category, pk=pk)
    category.delete()
    return redirect('categories')


# ── Posts ──────────────────────────────────────────────────────
def posts(request):
    # Editors only see their own posts
    # Managers and superusers see all posts
    if request.user.is_superuser or request.user.is_staff or request.user.groups.filter(name='Manager').exists():
        posts = Blog.objects.all()
    else:
        posts = Blog.objects.filter(author=request.user)

    context = {'posts': posts}
    return render(request, 'dashboard/posts.html', context)


def add_post(request):
    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.save()
            title = form.cleaned_data['title']
            post.slug = slugify(title) + '-' + str(post.id)
            post.save()
            return redirect('posts')
        else:
            print(form.errors)
    form = BlogPostForm()
    context = {'form': form}
    return render(request, 'dashboard/add_post.html', context)


def edit_post(request, pk):
    post = get_object_or_404(Blog, pk=pk)

    if not can_modify_post(request.user, post):
        raise PermissionDenied

    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            post = form.save()
            post.slug = slugify(form.cleaned_data['title']) + '-' + str(post.id)
            post.save()
            return redirect('posts')
    form = BlogPostForm(instance=post)
    context = {'form': form, 'post': post}
    return render(request, 'dashboard/edit_post.html', context)


def delete_post(request, pk):
    post = get_object_or_404(Blog, pk=pk)

    if not can_modify_post(request.user, post):
        raise PermissionDenied

    post.delete()
    return redirect('posts')


# ── Users ──────────────────────────────────────────────────────
def users(request):
    # Everyone can see all users including superusers
    users = User.objects.all()
    context = {'users': users}
    return render(request, 'dashboard/users.html', context)


def add_user(request):
    if request.method == 'POST':
        form = AddUserForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('users')
        else:
            print(form.errors)
    form = AddUserForm()
    context = {'form': form}
    return render(request, 'dashboard/add_user.html', context)


def edit_user(request, pk):
    user = get_object_or_404(User, pk=pk)

    if not can_modify_user(request.user, user):
        raise PermissionDenied

    if request.method == 'POST':
        form = EditUserForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            return redirect('users')
    form = EditUserForm(instance=user)
    context = {'form': form}
    return render(request, 'dashboard/edit_user.html', context)


def delete_user(request, pk):
    user = get_object_or_404(User, pk=pk)

    if not can_modify_user(request.user, user):
        raise PermissionDenied

    user.delete()
    return redirect('users')

def add_user(request):
    if request.method == 'POST':
        form = AddUserForm(request.POST, request=request)  # ← add request=request
        if form.is_valid():
            form.save()
            return redirect('users')
        else:
            print(form.errors)
    form = AddUserForm(request=request)                    # ← add request=request
    context = {'form': form}
    return render(request, 'dashboard/add_user.html', context)


def edit_user(request, pk):
    user = get_object_or_404(User, pk=pk)

    if not can_modify_user(request.user, user):
        raise PermissionDenied

    if request.method == 'POST':
        form = EditUserForm(request.POST, instance=user, request=request)  # ← add request=request
        if form.is_valid():
            updated_user = form.save(commit=False)
            # Block manager from granting superuser
            if not request.user.is_superuser:
                updated_user.is_superuser = False
            updated_user.save()
            form.save_m2m()
            return redirect('users')
    else:
        form = EditUserForm(instance=user, request=request)  # ← add request=request

    context = {'form': form}
    return render(request, 'dashboard/edit_user.html', context)