from blogs.models import Blog, EmailVerificationToken, NewsletterSubscription, PendingRegistration, PostReaction
from django.shortcuts import render, redirect
from about.models import About
from .forms import FutureFluxPasswordResetForm, RegisterForm
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import auth, messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.models import User
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse, reverse_lazy
from django.http import JsonResponse
from django.http import HttpResponse
from django.utils import timezone
from dashboards.models import Notification, Profile
from dashboards.services import create_user_notification, notify_managers
from dashboards.forms import FeedbackForm
from django.db.models import Count, Q
from blogs.services import publish_scheduled_posts
from urllib.parse import urlencode


def _mark_first_login_if_needed(request, user):
    if user and user.last_login is None:
        request.session['first_login'] = True


def _send_verification_email(request, *, username, email, token):
    verify_url = request.build_absolute_uri(
        reverse('verify_email', kwargs={'token': str(token)})
    )
    send_mail(
        subject='Verify your Django Blog email',
        message=(
            f'Hi {username},\n\n'
            f'Click the link below to verify your email address:\n\n'
            f'{verify_url}\n\n'
            f'This link expires in 24 hours.\n\n'
            f'If you did not create this account, please ignore this email.'
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


def _create_user_from_pending(pending_registration):
    if pending_registration.verified_user:
        return pending_registration.verified_user

    user = User(
        username=pending_registration.username,
        email=pending_registration.email,
        first_name=pending_registration.first_name,
        last_name=pending_registration.last_name,
        is_active=True,
    )
    user.password = pending_registration.password
    user.save()

    profile, _ = Profile.objects.get_or_create(user=user)
    if pending_registration.profile_image:
        profile.profile_image = pending_registration.profile_image
        profile.save(update_fields=['profile_image'])

    pending_registration.verified_user = user
    pending_registration.verified_at = timezone.now()
    pending_registration.save(update_fields=['verified_user', 'verified_at'])
    return user


def _build_resend_verification_url(*, email='', user_id=None, return_to=''):
    query = {}
    if email:
        query['email'] = email
    if user_id:
        query['user_id'] = user_id
    if return_to:
        query['return_to'] = return_to

    base_url = reverse('resend_verification')
    if not query:
        return base_url
    return f'{base_url}?{urlencode(query)}'


class FutureFluxPasswordResetView(auth_views.PasswordResetView):
    form_class = FutureFluxPasswordResetForm
    template_name = 'registration/password_reset_form.html'
    email_template_name = 'registration/password_reset_email.txt'
    subject_template_name = 'registration/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')
    from_email = settings.DEFAULT_FROM_EMAIL

    def form_valid(self, form):
        try:
            return super().form_valid(form)
        except Exception:
            form.add_error(
                None,
                'We could not send the recovery email right now. Please try again in a moment.',
            )
            return self.form_invalid(form)


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
        username = (request.POST.get('username') or '').strip()
        email = (request.POST.get('email') or '').strip()

        if username:
            User.objects.filter(username=username, is_active=False).delete()
            PendingRegistration.objects.filter(username=username).delete()
        if email:
            User.objects.filter(email__iexact=email, is_active=False).delete()
            PendingRegistration.objects.filter(email__iexact=email).delete()

        form = RegisterForm(request.POST, request.FILES)
        if form.is_valid():
            pending_registration = PendingRegistration.objects.create(
                email=form.cleaned_data['email'],
                username=form.cleaned_data['username'],
                first_name=form.cleaned_data.get('first_name', ''),
                last_name=form.cleaned_data.get('last_name', ''),
                password=make_password(form.cleaned_data['password1']),
                profile_image=form.cleaned_data.get('profile_image'),
            )
            _send_verification_email(
                request,
                username=pending_registration.username,
                email=pending_registration.email,
                token=pending_registration.token,
            )

            # ── Redirect to waiting page ─────────────────────────────────────
            return redirect('verify_wait', user_id=pending_registration.id)
    else:
        form = RegisterForm()

    return render(request, 'register.html', {'form': form})


# ── Waiting for verification page ─────────────────────────────
def verify_wait(request, user_id):
    pending_registration = PendingRegistration.objects.filter(id=user_id).first()
    if pending_registration:
        return render(request, 'verify_wait.html', {
            'email': pending_registration.email,
            'user_id': user_id,
        })

    user = User.objects.filter(id=user_id).first()
    if not user:
        return redirect('register')
    return render(request, 'verify_wait.html', {
        'email': user.email,
        'user_id': user_id,
    })


# ── Polling endpoint — called by JS every 3 seconds ───────────
def check_verification(request, user_id):
    pending_registration = PendingRegistration.objects.filter(id=user_id).first()
    if pending_registration:
        if pending_registration.verified_user:
            user = pending_registration.verified_user
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            _mark_first_login_if_needed(request, user)
            auth.login(request, user)
            return JsonResponse({'verified': True, 'redirect': reverse('dashboard')})
        return JsonResponse({'verified': False})

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
    pending_registration = PendingRegistration.objects.filter(token=token).first()
    if pending_registration:
        if pending_registration.verified_user:
            messages.info(request, 'Your email is already verified. Please sign in.')
            return redirect('login')

        if pending_registration.is_expired():
            messages.error(request, 'This link has expired. Request a new one below.')
            return redirect(
                _build_resend_verification_url(
                    email=pending_registration.email,
                    user_id=pending_registration.id,
                    return_to='verify_wait',
                )
            )

        username_taken = User.objects.filter(username=pending_registration.username).exists()
        email_taken = User.objects.filter(email__iexact=pending_registration.email).exists()
        if username_taken or email_taken:
            messages.error(request, 'This account is already registered. Please sign in.')
            return redirect('login')

        _create_user_from_pending(pending_registration)
        return render(request, 'verify_success.html')

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
        return redirect(
            _build_resend_verification_url(
                email=token_obj.user.email,
                user_id=token_obj.user.id,
                return_to='verify_wait',
            )
        )

    # ── Activate the account ─────────────────────────────────
    token_obj.is_verified = True
    token_obj.save()
    user           = token_obj.user
    user.is_active = True
    user.save()

    return render(request, 'verify_success.html')


# ── Resend verification ────────────────────────────────────────
def resend_verification(request):
    initial_email = (
        request.GET.get('email')
        or request.POST.get('email')
        or ''
    ).strip()
    user_id = (
        request.GET.get('user_id')
        or request.POST.get('user_id')
        or ''
    ).strip()
    return_to = (
        request.GET.get('return_to')
        or request.POST.get('return_to')
        or ''
    ).strip()

    if request.method == 'POST':
        email = initial_email
        redirect_url = reverse('login')
        pending_registration = PendingRegistration.objects.filter(
            email__iexact=email,
            verified_user__isnull=True,
        ).first()

        if pending_registration:
            if pending_registration.is_expired():
                pending_registration.refresh_token()
            _send_verification_email(
                request,
                username=pending_registration.username,
                email=pending_registration.email,
                token=pending_registration.token,
            )
            if return_to == 'verify_wait':
                redirect_url = reverse('verify_wait', args=[pending_registration.id])
        else:
            try:
                user = User.objects.get(email__iexact=email, is_active=False)
                token_obj, created = EmailVerificationToken.objects.get_or_create(user=user)
                if not created and token_obj.is_expired():
                    token_obj.delete()
                    token_obj = EmailVerificationToken.objects.create(user=user)
                _send_verification_email(
                    request,
                    username=user.username,
                    email=user.email,
                    token=token_obj.token,
                )
                if return_to == 'verify_wait':
                    redirect_target_id = user.id
                    if user_id.isdigit():
                        redirect_target_id = int(user_id)
                    redirect_url = reverse('verify_wait', args=[redirect_target_id])
            except User.DoesNotExist:
                pass  # show generic message to avoid email enumeration
        messages.success(
            request,
            'If that email is registered and unverified, we sent a new verification link.'
        )
        return redirect(redirect_url)

    return render(
        request,
        'resend_verification.html',
        {
            'initial_email': initial_email,
            'user_id': user_id,
            'return_to': return_to,
        },
    )


# ── Login ──────────────────────────────────────────────────────
def login(request):
    unverified = False
    resend_email = ''
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')

        # Check if the account exists but is not yet verified
        pending_registration = PendingRegistration.objects.filter(
            username=username,
            verified_user__isnull=True,
        ).first()
        unverified_user = User.objects.filter(username=username, is_active=False).first()
        pending_matches = pending_registration and check_password(password, pending_registration.password)
        legacy_matches = unverified_user and unverified_user.check_password(password)

        if pending_matches or legacy_matches:
            # Account exists but email not verified — show banner, don't log in
            unverified = True
            resend_email = pending_registration.email if pending_matches else unverified_user.email
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

    return render(
        request,
        'login.html',
        {
            'form': form,
            'unverified': unverified,
            'resend_email': resend_email,
        },
    )


# ── Logout ─────────────────────────────────────────────────────
def logout(request):
    auth.logout(request)
    return redirect('home')
