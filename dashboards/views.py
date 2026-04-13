from django.shortcuts import render, redirect, get_object_or_404
from blogs.models import Blog, Category
from django.contrib.auth.decorators import login_required
from .forms import CategoryForm, BlogPostForm, AddUserForm, EditUserForm, ProfileForm, FeedbackManageForm
from django.template.defaultfilters import slugify
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from .models import Feedback, Profile


# ── Permission helpers ─────────────────────────────────────────
def can_manage_all_content(user):
    return user.is_superuser or user.is_staff or user.groups.filter(name='Manager').exists()


def can_modify_post(user, post):
    if can_manage_all_content(user):
        return True
    if user.groups.filter(name='Editor').exists() and post.author == user:
        return True
    return False


def can_modify_category(user, category):
    if can_manage_all_content(user):
        return True
    if user.groups.filter(name='Editor').exists() and category.owner == user:
        return True
    return False


def get_allowed_categories(user):
    if can_manage_all_content(user):
        return Category.objects.all().order_by('-updated_at')
    return Category.objects.all().order_by('-updated_at')


def can_modify_user(requesting_user, target_user):
    """Manager cannot edit or delete superusers. Only superuser can."""
    if requesting_user.is_superuser:
        return True
    if target_user.is_superuser:
        return False
    return True


def get_user_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    return profile


def can_view_feedback(user):
    return user.is_superuser or user.groups.filter(name='Manager').exists()


def can_manage_feedback(user):
    return user.is_superuser


# ── Dashboard ──────────────────────────────────────────────────
@login_required(login_url='login')
def dashboard(request):
    first_login = request.session.pop('first_login', False)
    welcome = 'Welcome' if first_login else 'Welcome back'

    category_count = get_allowed_categories(request.user).count()
    blogs_count = Blog.objects.all().count() if can_manage_all_content(request.user) else Blog.objects.filter(author=request.user).count()

    context = {
        'category_count': category_count,
        'blogs_count': blogs_count,
        'feedback_count': Feedback.objects.count() if can_view_feedback(request.user) else 0,
        'welcome': welcome,
    }
    return render(request, 'dashboard/dashboard.html', context)


# ── Categories ─────────────────────────────────────────────────
@login_required(login_url='login')
def categories(request):
    manageable_category_ids = set()
    if can_manage_all_content(request.user):
        manageable_category_ids = set(Category.objects.values_list('id', flat=True))
    else:
        manageable_category_ids = set(
            Category.objects.filter(owner=request.user).values_list('id', flat=True)
        )

    context = {
        'categories': get_allowed_categories(request.user),
        'manageable_category_ids': manageable_category_ids,
    }
    return render(request, 'dashboard/categories.html', context)


@login_required(login_url='login')
def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            category = form.save(commit=False)
            category.owner = request.user
            category.save()
            return redirect('categories')
    else:
        form = CategoryForm()
    context = {
        'form': form,
        'categories': get_allowed_categories(request.user),
        'manageable_category_ids': set(
            Category.objects.values_list('id', flat=True)
            if can_manage_all_content(request.user)
            else Category.objects.filter(owner=request.user).values_list('id', flat=True)
        ),
    }
    return render(request, 'dashboard/add_category.html', context)


@login_required(login_url='login')
def edit_category(request, pk):
    category = get_object_or_404(Category, pk=pk)

    if not can_modify_category(request.user, category):
        raise PermissionDenied

    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            return redirect('categories')
    else:
        form = CategoryForm(instance=category)
    context = {'form': form, 'category': category}
    return render(request, 'dashboard/edit_category.html', context)


@login_required(login_url='login')
def delete_category(request, pk):
    category = get_object_or_404(Category, pk=pk)

    if not can_modify_category(request.user, category):
        raise PermissionDenied

    category.delete()
    return redirect('categories')


# ── Posts ──────────────────────────────────────────────────────
@login_required(login_url='login')
def posts(request):
    # Editors only see their own posts
    # Managers and superusers see all posts
    if can_manage_all_content(request.user):
        posts = Blog.objects.all()
    else:
        posts = Blog.objects.filter(author=request.user)

    context = {'posts': posts}
    return render(request, 'dashboard/posts.html', context)


@login_required(login_url='login')
def add_post(request):
    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES, user=request.user)
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
    form = BlogPostForm(user=request.user)
    context = {'form': form}
    return render(request, 'dashboard/add_post.html', context)


@login_required(login_url='login')
def edit_post(request, pk):
    post = get_object_or_404(Blog, pk=pk)

    if not can_modify_post(request.user, post):
        raise PermissionDenied

    if request.method == 'POST':
        form = BlogPostForm(request.POST, request.FILES, instance=post, user=request.user)
        if form.is_valid():
            post = form.save()
            post.slug = slugify(form.cleaned_data['title']) + '-' + str(post.id)
            post.save()
            return redirect('posts')
    form = BlogPostForm(instance=post, user=request.user)
    context = {'form': form, 'post': post}
    return render(request, 'dashboard/edit_post.html', context)


@login_required(login_url='login')
def delete_post(request, pk):
    post = get_object_or_404(Blog, pk=pk)

    if not can_modify_post(request.user, post):
        raise PermissionDenied

    post.delete()
    return redirect('posts')


# ── Profile ────────────────────────────────────────────────────
@login_required(login_url='login')
def my_profile(request):
    profile = get_user_profile(request.user)

    context = {
        'profile_user': request.user,
        'profile': profile,
    }
    return render(request, 'dashboard/my_profile.html', context)


@login_required(login_url='login')
def edit_my_profile(request):
    profile = get_user_profile(request.user)

    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            return redirect('my_profile')
    else:
        form = ProfileForm(instance=profile, user=request.user)

    context = {
        'form': form,
        'profile_user': request.user,
        'profile': profile,
    }
    return render(request, 'dashboard/edit_my_profile.html', context)


# ── Feedback ───────────────────────────────────────────────────
@login_required(login_url='login')
def feedback_list(request):
    if not can_view_feedback(request.user):
        raise PermissionDenied

    feedback_items = Feedback.objects.all()
    context = {
        'feedback_items': feedback_items,
        'can_manage_feedback': can_manage_feedback(request.user),
    }
    return render(request, 'dashboard/feedback.html', context)


@login_required(login_url='login')
def edit_feedback(request, pk):
    if not can_manage_feedback(request.user):
        raise PermissionDenied

    feedback_item = get_object_or_404(Feedback, pk=pk)

    if request.method == 'POST':
        form = FeedbackManageForm(request.POST, instance=feedback_item)
        if form.is_valid():
            form.save()
            return redirect('dashboard_feedback')
    else:
        form = FeedbackManageForm(instance=feedback_item)

    context = {
        'form': form,
        'feedback_item': feedback_item,
    }
    return render(request, 'dashboard/edit_feedback.html', context)


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
