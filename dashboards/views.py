from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Count
from django.utils import timezone
from blogs.models import AuthorFollow, Blog, Bookmark, Category, ContentReport
from django.contrib.auth.decorators import login_required
from .forms import (
    CategoryForm,
    BlogPostForm,
    AddUserForm,
    EditUserForm,
    ProfileForm,
    FeedbackManageForm,
    ContentReportManageForm,
)
from django.template.defaultfilters import slugify
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from .models import Feedback, Notification, Profile
from blogs.services import notify_followers_of_post, publish_scheduled_posts
from urllib.parse import urlparse


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


def can_view_followers(user):
    return can_manage_all_content(user) or user.groups.filter(name='Editor').exists()


def can_manage_reports(user):
    return can_manage_all_content(user)


# ── Dashboard ──────────────────────────────────────────────────
@login_required(login_url='login')
def dashboard(request):
    publish_scheduled_posts()
    first_login = request.session.pop('first_login', False)
    welcome = 'Welcome' if first_login else 'Welcome back'

    category_count = get_allowed_categories(request.user).count()
    blogs_count = Blog.objects.all().count() if can_manage_all_content(request.user) else Blog.objects.filter(author=request.user).count()

    context = {
        'category_count': category_count,
        'blogs_count': blogs_count,
        'feedback_count': Feedback.objects.count() if can_view_feedback(request.user) else 0,
        'saved_count': Bookmark.objects.filter(user=request.user).count(),
        'notification_count': Notification.objects.filter(user=request.user, is_read=False).count(),
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
            should_notify_followers = False
            if post.status == 'Published' and not post.published_at:
                post.published_at = timezone.now()
                should_notify_followers = True
            if post.scheduled_for and post.scheduled_for > timezone.now():
                post.status = 'Draft'
                should_notify_followers = False
            post.save()
            title = form.cleaned_data['title']
            post.slug = slugify(title) + '-' + str(post.id)
            post.save()
            if should_notify_followers:
                notify_followers_of_post(post)
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
        was_published = post.status == 'Published'
        form = BlogPostForm(request.POST, request.FILES, instance=post, user=request.user)
        if form.is_valid():
            post = form.save()
            should_notify_followers = False
            if post.status == 'Published' and not post.published_at:
                post.published_at = timezone.now()
            if post.status == 'Published' and not was_published:
                should_notify_followers = True
            if post.scheduled_for and post.scheduled_for > timezone.now():
                post.status = 'Draft'
                should_notify_followers = False
            post.slug = slugify(form.cleaned_data['title']) + '-' + str(post.id)
            post.save()
            if should_notify_followers:
                notify_followers_of_post(post)
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
        previous_status = feedback_item.status
        form = FeedbackManageForm(request.POST, instance=feedback_item)
        if form.is_valid():
            updated_feedback = form.save()
            if (
                updated_feedback.user
                and previous_status != updated_feedback.status
                and updated_feedback.status in {Feedback.STATUS_REVIEWED, Feedback.STATUS_RESOLVED}
            ):
                Notification.objects.create(
                    user=updated_feedback.user,
                    title='Feedback updated',
                    message=f'Your feedback "{updated_feedback.subject}" is now {updated_feedback.status.lower()}.',
                    link='/feedback/',
                )
            return redirect('dashboard_feedback')
    else:
        form = FeedbackManageForm(instance=feedback_item)

    context = {
        'form': form,
        'feedback_item': feedback_item,
    }
    return render(request, 'dashboard/edit_feedback.html', context)


# ── Users ──────────────────────────────────────────────────────
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


@login_required(login_url='login')
def users(request):
    users = User.objects.all().select_related('profile')
    context = {'users': users}
    return render(request, 'dashboard/users.html', context)


@login_required(login_url='login')
def delete_user(request, pk):
    user = get_object_or_404(User, pk=pk)

    if not can_modify_user(request.user, user):
        raise PermissionDenied

    user.delete()
    return redirect('users')


@login_required(login_url='login')
def preview_post(request, pk):
    post = get_object_or_404(Blog, pk=pk)
    if not can_modify_post(request.user, post):
        raise PermissionDenied

    context = {
        'single_blog': post,
        'comments': [],
        'comments_count': 0,
        'categories': Category.objects.all().order_by('category_name'),
        'related_posts': Blog.objects.filter(category=post.category, status='Published').exclude(pk=post.pk)[:3],
        'reaction_counts': {},
        'user_reactions': set(),
        'is_bookmarked': False,
        'is_preview': True,
        'page_title': f'Preview: {post.title}',
        'meta_description': post.meta_description,
    }
    return render(request, 'blogs.html', context)


@login_required(login_url='login')
def saved_posts(request):
    saved_items = Bookmark.objects.filter(user=request.user).select_related('blog__author', 'blog__category')
    return render(request, 'dashboard/saved_posts.html', {'saved_items': saved_items})


@login_required(login_url='login')
def analytics(request):
    publish_scheduled_posts()
    if can_manage_all_content(request.user):
        posts = Blog.objects.all()
    else:
        posts = Blog.objects.filter(author=request.user)

    top_posts = posts.order_by('-view_count', '-updated_at')[:10]
    top_categories = (
        posts.values('category__category_name')
        .annotate(total=Count('id'))
        .order_by('-total')[:5]
    )

    context = {
        'top_posts': top_posts,
        'top_categories': top_categories,
        'total_views': sum(post.view_count for post in posts),
    }
    return render(request, 'dashboard/analytics.html', context)


@login_required(login_url='login')
def notifications(request):
    items = Notification.objects.filter(user=request.user)
    items.update(is_read=True)
    return render(request, 'dashboard/notifications.html', {'notifications': items})


@login_required(login_url='login')
def open_notification(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    if notification.title == 'New follower':
        return redirect('followers')

    target = notification.link or '/dashboard/notifications/'
    path = urlparse(target).path

    if path.startswith('/blogs/'):
        slug = path.strip('/').split('/')[1] if len(path.strip('/').split('/')) > 1 else ''
        if slug and not Blog.objects.filter(slug=slug).exists():
            messages.info(request, 'This post was deleted, so the original notification link is no longer available.')
            return redirect('notifications')

    if path.startswith('/category/'):
        parts = path.strip('/').split('/')
        category_id = parts[1] if len(parts) > 1 else ''
        if category_id.isdigit() and not Category.objects.filter(pk=category_id).exists():
            messages.info(request, 'This category is no longer available.')
            return redirect('notifications')

    if path.startswith('/blogs/authors/'):
        parts = path.strip('/').split('/')
        username = parts[2] if len(parts) > 2 else ''
        if username and not User.objects.filter(username=username).exists():
            messages.info(request, 'This author profile is no longer available.')
            return redirect('notifications')

    return redirect(target)


@login_required(login_url='login')
def reports(request):
    if not can_manage_reports(request.user):
        raise PermissionDenied
    report_items = ContentReport.objects.select_related('blog', 'user')
    return render(
        request,
        'dashboard/reports.html',
        {
            'report_items': report_items,
            'can_manage_reports': can_manage_reports(request.user),
        },
    )


@login_required(login_url='login')
def edit_report(request, pk):
    if not can_manage_reports(request.user):
        raise PermissionDenied

    report_item = get_object_or_404(ContentReport.objects.select_related('blog', 'user'), pk=pk)

    if request.method == 'POST':
        previous_status = report_item.status
        form = ContentReportManageForm(request.POST, instance=report_item)
        if form.is_valid():
            updated_report = form.save()
            if (
                updated_report.user
                and previous_status != updated_report.status
                and updated_report.status in {ContentReport.STATUS_REVIEWED, ContentReport.STATUS_RESOLVED}
            ):
                Notification.objects.create(
                    user=updated_report.user,
                    title='Report updated',
                    message=f'Your report on "{updated_report.blog.title}" is now {updated_report.status.lower()}.',
                    link=updated_report.blog.get_absolute_url(),
                )
            return redirect('reports')
    else:
        form = ContentReportManageForm(instance=report_item)

    return render(
        request,
        'dashboard/edit_report.html',
        {
            'form': form,
            'report_item': report_item,
        },
    )


@login_required(login_url='login')
def delete_report(request, pk):
    raise PermissionDenied


@login_required(login_url='login')
def followers(request):
    if not can_view_followers(request.user):
        raise PermissionDenied

    if can_manage_all_content(request.user):
        authors = (
            User.objects.filter(groups__name='Editor')
            .distinct()
            .select_related('profile')
            .order_by('username')
        )
    else:
        authors = User.objects.filter(pk=request.user.pk).select_related('profile')

    author_sections = []
    for author in authors:
        followers_qs = (
            AuthorFollow.objects.filter(author=author)
            .select_related('follower__profile')
            .order_by('-created_at')
        )
        author_sections.append(
            {
                'author': author,
                'followers': followers_qs,
                'count': followers_qs.count(),
            }
        )

    context = {
        'author_sections': author_sections,
        'is_manager_view': can_manage_all_content(request.user),
    }
    return render(request, 'dashboard/followers.html', context)
