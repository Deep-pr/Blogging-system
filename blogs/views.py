from django.contrib import messages
from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils import timezone

from dashboards.models import Notification
from dashboards.services import notify_managers

from .models import AuthorFollow, Blog, Bookmark, Category, Comment, ContentReport, PostReaction
from .services import publish_scheduled_posts


def _visible_blog_queryset():
    publish_scheduled_posts()
    return Blog.objects.filter(status='Published').select_related('author', 'category')


def _author_can_preview(user, blog):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff or user.groups.filter(name='Manager').exists():
        return True
    return blog.author == user


def _get_session_bookmarks(request):
    return set(request.session.get('guest_bookmarks', []))


def _get_session_reactions(request):
    return request.session.get('guest_reactions', {})


def _get_guest_reaction_token(request):
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key or ''


def _get_redirect_target(request, default_url):
    next_url = request.POST.get('next_url') or request.GET.get('next_url')
    if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
        return next_url
    return request.META.get('HTTP_REFERER', default_url)


def posts_by_category(request, category_id):
    posts = _visible_blog_queryset().filter(category_id=category_id).order_by('-published_at', '-created_at')
    category = get_object_or_404(Category, pk=category_id)
    context = {
        'posts': posts,
        'category': category,
        'page_title': f'{category.category_name} Articles | FutureFlux',
        'meta_description': f'Explore the latest {category.category_name.lower()} stories on FutureFlux.',
    }
    return render(request, 'posts_by_category.html', context)


def blogs(request, slug):
    base_queryset = Blog.objects.select_related('author', 'category')
    single_blog = get_object_or_404(base_queryset, slug=slug)

    if single_blog.status != 'Published':
        publish_scheduled_posts()
        single_blog.refresh_from_db()
        if single_blog.status != 'Published' and not _author_can_preview(request.user, single_blog):
            raise Http404

    if request.method == 'POST' and request.user.is_authenticated and request.POST.get('comment'):
        Comment.objects.create(
            user=request.user,
            blog=single_blog,
            comment=request.POST['comment'],
        )
        return HttpResponseRedirect(_get_redirect_target(request, f'{single_blog.get_absolute_url()}#comments'))

    session_key = f'viewed_blog_{single_blog.id}'
    if not request.session.get(session_key):
        Blog.objects.filter(pk=single_blog.pk).update(view_count=single_blog.view_count + 1)
        request.session[session_key] = True
        single_blog.refresh_from_db()

    comments = Comment.objects.filter(blog=single_blog).select_related('user')
    related_posts = _visible_blog_queryset().filter(category=single_blog.category).exclude(pk=single_blog.pk)[:3]
    reaction_counts = {
        reaction['reaction_type']: reaction['count']
        for reaction in single_blog.reactions.values('reaction_type').annotate(count=Count('id'))
    }
    reaction_summary = [
        {
            'value': reaction_type,
            'label': label,
            'count': reaction_counts.get(reaction_type, 0),
        }
        for reaction_type, label in PostReaction.REACTION_CHOICES
    ]
    user_reactions = set()
    is_bookmarked = False
    is_following_author = False
    follower_count = single_blog.author.author_followers.count()
    if request.user.is_authenticated:
        user_reactions = set(
            single_blog.reactions.filter(user=request.user).values_list('reaction_type', flat=True)
        )
        is_bookmarked = Bookmark.objects.filter(user=request.user, blog=single_blog).exists()
        if request.user != single_blog.author:
            is_following_author = AuthorFollow.objects.filter(follower=request.user, author=single_blog.author).exists()
    else:
        guest_token = _get_guest_reaction_token(request)
        user_reactions = set(
            single_blog.reactions.filter(user__isnull=True, guest_token=guest_token).values_list('reaction_type', flat=True)
        )
        is_bookmarked = single_blog.id in _get_session_bookmarks(request)

    context = {
        'single_blog': single_blog,
        'comments': comments,
        'comments_count': comments.count(),
        'categories': Category.objects.all().order_by('category_name'),
        'related_posts': related_posts,
        'reaction_counts': reaction_counts,
        'reaction_summary': reaction_summary,
        'user_reactions': user_reactions,
        'is_bookmarked': is_bookmarked,
        'is_following_author': is_following_author,
        'follower_count': follower_count,
        'page_title': f'{single_blog.title} | FutureFlux',
        'meta_description': single_blog.meta_description,
        'canonical_url': request.build_absolute_uri(single_blog.get_absolute_url()),
        'og_image': request.build_absolute_uri(single_blog.featured_image.url) if single_blog.featured_image else '',
    }
    return render(request, 'blogs.html', context)


def author_profile(request, username):
    author = get_object_or_404(User.objects.select_related('profile'), username=username)
    posts = _visible_blog_queryset().filter(author=author).order_by('-published_at', '-created_at')
    is_following = False
    follower_count = author.author_followers.count()
    if request.user.is_authenticated and request.user != author:
        is_following = AuthorFollow.objects.filter(follower=request.user, author=author).exists()
    context = {
        'author_profile_user': author,
        'posts': posts,
        'is_following_author': is_following,
        'follower_count': follower_count,
        'page_title': f'{author.username} | Author at FutureFlux',
        'meta_description': author.profile.bio or f'Read posts by {author.username} on FutureFlux.',
    }
    return render(request, 'author_profile.html', context)


def toggle_follow_author(request, username):
    author = get_object_or_404(User, username=username)

    if not request.user.is_authenticated:
        messages.info(request, 'Please sign in to follow authors.')
        return redirect('login')

    if request.user == author:
        messages.info(request, 'You cannot follow your own author profile.')
        return redirect(_get_redirect_target(request, reverse('author_profile', kwargs={'username': author.username})))

    follow, created = AuthorFollow.objects.get_or_create(follower=request.user, author=author)
    if created:
        Notification.objects.create(
            user=author,
            title='New follower',
            message=f'{request.user.username} started following your author profile.',
            link=reverse('followers'),
        )
        messages.success(request, f'You are now following {author.username}.')
    else:
        follow.delete()
        messages.success(request, f'You unfollowed {author.username}.')

    return redirect(_get_redirect_target(request, reverse('author_profile', kwargs={'username': author.username})))


def search(request):
    publish_scheduled_posts()
    keyword = (request.GET.get('keyword') or '').strip()
    category_id = request.GET.get('category')
    author_id = request.GET.get('author')
    published_after = request.GET.get('published_after')

    blogs = Blog.objects.filter(status='Published').select_related('author', 'category')
    if keyword:
        blogs = blogs.filter(
            Q(title__icontains=keyword)
            | Q(short_description__icontains=keyword)
            | Q(blog_body__icontains=keyword)
        )
    if category_id:
        blogs = blogs.filter(category_id=category_id)
    if author_id:
        blogs = blogs.filter(author_id=author_id)
    if published_after:
        blogs = blogs.filter(created_at__date__gte=published_after)

    context = {
        'blogs': blogs.order_by('-published_at', '-created_at'),
        'keyword': keyword,
        'filter_categories': Category.objects.all().order_by('category_name'),
        'filter_authors': User.objects.filter(blog__status='Published').distinct().order_by('username'),
        'selected_category': category_id or '',
        'selected_author': author_id or '',
        'selected_date': published_after or '',
        'page_title': 'Search Articles | FutureFlux',
        'meta_description': 'Search articles by keyword, category, author, and date on FutureFlux.',
    }
    return render(request, 'search.html', context)


def toggle_bookmark(request, slug):
    blog = get_object_or_404(Blog, slug=slug)
    if request.user.is_authenticated:
        bookmark, created = Bookmark.objects.get_or_create(user=request.user, blog=blog)
        if not created:
            bookmark.delete()
            messages.success(request, 'Post removed from your saved list.')
        else:
            messages.success(request, 'Post saved to your bookmarks.')
    else:
        bookmarks = _get_session_bookmarks(request)
        if blog.id in bookmarks:
            bookmarks.remove(blog.id)
            messages.success(request, 'Post removed from your saved list.')
        else:
            bookmarks.add(blog.id)
            messages.success(request, 'Post saved in this browser.')
        request.session['guest_bookmarks'] = list(bookmarks)
    return redirect(_get_redirect_target(request, f'{blog.get_absolute_url()}#reader-actions'))


def react_to_post(request, slug, reaction_type):
    blog = get_object_or_404(Blog, slug=slug)
    valid_reactions = {choice[0] for choice in PostReaction.REACTION_CHOICES}
    if reaction_type not in valid_reactions:
        raise Http404

    if request.user.is_authenticated:
        reaction, created = PostReaction.objects.get_or_create(
            user=request.user,
            blog=blog,
            reaction_type=reaction_type,
        )
        if not created:
            reaction.delete()
            messages.success(request, f'{reaction_type} reaction removed.')
            active = False
        else:
            messages.success(request, f'{reaction_type} reaction added.')
            active = True
    else:
        guest_token = _get_guest_reaction_token(request)
        reaction, created = PostReaction.objects.get_or_create(
            user=None,
            guest_token=guest_token,
            blog=blog,
            reaction_type=reaction_type,
        )
        if not created:
            reaction.delete()
            messages.success(request, f'{reaction_type} reaction removed.')
            active = False
        else:
            messages.success(request, f'{reaction_type} reaction added.')
            active = True

    updated_count = blog.reactions.filter(reaction_type=reaction_type).count()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse(
            {
                'ok': True,
                'reaction_type': reaction_type,
                'count': updated_count,
                'active': active,
            }
        )
    return redirect(_get_redirect_target(request, f'{blog.get_absolute_url()}#reader-actions'))


def report_post(request, slug):
    blog = get_object_or_404(Blog, slug=slug)
    if request.method == 'POST':
        reason = (request.POST.get('reason') or '').strip()
        details = (request.POST.get('details') or '').strip()
        if reason:
            report = ContentReport.objects.create(
                user=request.user if request.user.is_authenticated else None,
                blog=blog,
                reason=reason,
                details=details,
            )
            notify_managers(
                title='New content report',
                message=f'"{blog.title}" was reported for "{reason}".',
                link=reverse('reports'),
            )
            if report.user:
                Notification.objects.create(
                    user=report.user,
                    title='Report submitted',
                    message=f'We received your report for "{blog.title}".',
                    link=blog.get_absolute_url(),
                )
            messages.success(request, 'Thanks. Your report has been submitted.')
    return redirect(_get_redirect_target(request, f'{blog.get_absolute_url()}#reader-actions'))
