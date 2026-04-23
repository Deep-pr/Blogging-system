from blogs.models import Blog, EmailVerificationToken, NewsletterSubscription, PostReaction
from django.shortcuts import render, redirect
from about.models import About
from .forms import RegisterForm
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import auth, messages
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.http import JsonResponse
from django.http import HttpResponse
from dashboards.models import Notification, Profile
from dashboards.services import create_user_notification, notify_managers
from dashboards.forms import FeedbackForm
from django.db.models import Count, Q
from blogs.services import publish_scheduled_posts


def _mark_first_login_if_needed(request, user):
    if user and user.last_login is None:
        request.session['first_login'] = True


def home(request):
    publish_scheduled_posts()
    published_posts = (
        Blog.objects.filter(status='Published')
        .select_related('author', 'category')
        .annotate(
            like_count=Count(
                'reactions',
                filter=Q(reactions__reaction_type=PostReaction.LIKE),
                distinct=True,
            )
        )
    )
    spotlight_post = published_posts.order_by('-like_count', '-published_at', '-updated_at').first()

    featured_posts = published_posts.filter(is_featured=True)
    posts = published_posts.filter(is_featured=False)

    if spotlight_post:
        featured_posts = featured_posts.exclude(id=spotlight_post.id)
        posts = posts.exclude(id=spotlight_post.id)

    featured_posts = featured_posts.order_by('-published_at', '-updated_at')
    posts = posts.order_by('-published_at', '-updated_at')

    try:
        about = About.objects.get()
    except Exception:
        about = None
    context = {
        'about': about,
        'spotlight_post': spotlight_post,
        'featured_posts': featured_posts,
        'posts': posts,
        'page_title': 'FutureFlux | Stories Worth Reading',
        'meta_description': 'Discover thoughtful stories, practical ideas, and fresh perspectives across technology, business, design, and culture.',
    }
    return render(request, 'home.html', context)


def feedback(request):
    initial = {}
    if request.META.get('HTTP_REFERER'):
        initial['page_url'] = request.META.get('HTTP_REFERER')

    if request.method == 'POST':
        form = FeedbackForm(request.POST, user=request.user if request.user.is_authenticated else None, initial=initial)
        if form.is_valid():
            feedback_entry = form.save(commit=False)
            if request.user.is_authenticated:
                feedback_entry.user = request.user
            feedback_entry.save()
            notify_managers(
                title='New feedback submitted',
                message=f'"{feedback_entry.subject}" was submitted for review.',
                link=reverse('dashboard_feedback'),
            )
            if request.user.is_authenticated:
                create_user_notification(
                    user=request.user,
                    title='Feedback received',
                    message='Your feedback has been submitted and is waiting for review.',
                    link='/feedback/',
                    preference_name='notify_feedback_updates',
                )
            messages.success(request, 'Thanks for the feedback. We received it and will review it soon.')
            return redirect('feedback')
    else:
        form = FeedbackForm(user=request.user if request.user.is_authenticated else None, initial=initial)

    context = {'form': form}
    return render(request, 'feedback.html', context)


def newsletter_subscribe(request):
    if request.method == 'POST':
        email = (request.POST.get('email') or '').strip()
        if email:
            subscription, created = NewsletterSubscription.objects.get_or_create(
                email=email,
                defaults={'user': request.user if request.user.is_authenticated else None},
            )
            if not created and not subscription.is_active:
                subscription.is_active = True
                subscription.user = request.user if request.user.is_authenticated else subscription.user
                subscription.save(update_fields=['is_active', 'user'])
            messages.success(request, 'You are subscribed to the newsletter now.')
    return redirect(request.META.get('HTTP_REFERER', 'home'))


def sitemap_xml(request):
    publish_scheduled_posts()
    published_posts = Blog.objects.filter(status='Published').select_related('category')
    response_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    base = request.build_absolute_uri('/').rstrip('/')
    response_parts.append(f'<url><loc>{base}/</loc></url>')

    category_ids = set()
    for post in published_posts:
        category_ids.add(post.category_id)
        slug = post.slug
        response_parts.append(f'<url><loc>{base}/blogs/{slug}/</loc></url>')

    for category_id in category_ids:
        response_parts.append(f'<url><loc>{base}/category/{category_id}/</loc></url>')

    response_parts.append('</urlset>')
    return HttpResponse(''.join(response_parts), content_type='application/xml')


# ── Registration ───────────────────────────────────────────────
def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST, request.FILES)
        if form.is_valid():
            username = form.cleaned_data['username']
            email    = form.cleaned_data['email']

            # ── Delete any old UNVERIFIED accounts with same username or email ──
            # This allows someone who never verified to re-register cleanly
            User.objects.filter(username=username, is_active=False).delete()
            User.objects.filter(email=email,    is_active=False).delete()

            # ── Create new inactive user ─────────────────────────────────────
            user = form.save(commit=False)
            user.is_active = False   # stays inactive until email verified
            user.save()

            profile, _ = Profile.objects.get_or_create(user=user)
            if form.cleaned_data.get('profile_image'):
                profile.profile_image = form.cleaned_data['profile_image']
                profile.save()

            # ── Create token and send verification email ─────────────────────
            token_obj = EmailVerificationToken.objects.create(user=user)
            _send_verification_email(request, user, token_obj.token)

            # ── Redirect to waiting page ─────────────────────────────────────
            return redirect('verify_wait', user_id=user.id)
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})


def _send_verification_email(request, user, token):
    verify_url = request.build_absolute_uri(
        reverse('verify_email', kwargs={'token': str(token)})
    )
    send_mail(
        subject='Verify your Django Blog email',
        message=(
            f'Hi {user.username},\n\n'
            f'Click the link below to verify your email address:\n\n'
            f'{verify_url}\n\n'
            f'This link expires in 24 hours.\n\n'
            f'If you did not create this account, please ignore this email.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


# ── Waiting for verification page ─────────────────────────────
def verify_wait(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return redirect('register')
    return render(request, 'verify_wait.html', {
        'email': user.email,
        'user_id': user_id,
    })


# ── Polling endpoint — called by JS every 3 seconds ───────────
def check_verification(request, user_id):
    try:
        user      = User.objects.get(id=user_id)
        token_obj = EmailVerificationToken.objects.get(user=user)
        if token_obj.is_verified:
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            _mark_first_login_if_needed(request, user)
            auth.login(request, user)
            return JsonResponse({'verified': True, 'redirect': reverse('dashboard')})
        return JsonResponse({'verified': False})
    except (User.DoesNotExist, EmailVerificationToken.DoesNotExist):
        return JsonResponse({'verified': False})


# ── Email verification endpoint ────────────────────────────────
def verify_email(request, token):
    try:
        token_obj = EmailVerificationToken.objects.get(token=token)
    except EmailVerificationToken.DoesNotExist:
        messages.error(request, 'Invalid or already-used verification link.')
        return redirect('login')

    if token_obj.is_verified:
        messages.info(request, 'Your email is already verified. Please sign in.')
        return redirect('login')

    if token_obj.is_expired():
        messages.error(request, 'This link has expired. Request a new one below.')
        return redirect('resend_verification')

    # ── Activate the account ─────────────────────────────────
    token_obj.is_verified = True
    token_obj.save()
    user           = token_obj.user
    user.is_active = True
    user.save()

    return render(request, 'verify_success.html')


# ── Resend verification ────────────────────────────────────────
def resend_verification(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        try:
            user = User.objects.get(email=email, is_active=False)
            token_obj, created = EmailVerificationToken.objects.get_or_create(user=user)
            if not created and token_obj.is_expired():
                token_obj.delete()
                token_obj = EmailVerificationToken.objects.create(user=user)
            _send_verification_email(request, user, token_obj.token)
        except User.DoesNotExist:
            pass  # show generic message to avoid email enumeration
        messages.success(
            request,
            'If that email is registered and unverified, we sent a new verification link.'
        )
        return redirect('login')

    return render(request, 'resend_verification.html')


# ── Login ──────────────────────────────────────────────────────
def login(request):
    unverified = False
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # Check if the account exists but is not yet verified
        unverified_user = User.objects.filter(username=username, is_active=False).first()
        if unverified_user and unverified_user.check_password(password):
            # Account exists but email not verified — show banner, don't log in
            unverified = True
            form = AuthenticationForm()
        else:
            form = AuthenticationForm(request, data=request.POST)
            if form.is_valid():
                user = auth.authenticate(
                    request,
                    username=username,
                    password=password,
                )
                if user is not None:
                    _mark_first_login_if_needed(request, user)
                    auth.login(request, user)
                    return redirect('dashboard')

    else:
        form = AuthenticationForm()

    return render(request, 'login.html', {'form': form, 'unverified': unverified})


# ── Logout ─────────────────────────────────────────────────────
def logout(request):
    auth.logout(request)
    return redirect('home')
