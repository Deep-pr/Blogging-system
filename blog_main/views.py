from blogs.models import Blog, Category, EmailVerificationToken
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


def home(request):
    featured_posts = Blog.objects.filter(is_featured=True, status='Published').order_by('updated_at')
    posts = Blog.objects.filter(is_featured=False, status='Published')
    try:
        about = About.objects.get()
    except:
        about = None
    context = {
        'about': about,
        'featured_posts': featured_posts,
        'posts': posts,
    }
    return render(request, 'home.html', context)


# ── Registration ───────────────────────────────────────────────
def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            token_obj = EmailVerificationToken.objects.create(user=user)
            _send_verification_email(request, user, token_obj.token)
            # ── redirect to waiting page instead of login ──
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
            f'Click the link below to verify your email:\n\n'
            f'{verify_url}\n\n'
            f'This link expires in 24 hours.\n\n'
            f'If you did not create this account, ignore this email.'
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
    return render(request, 'verify_wait.html', {'email': user.email, 'user_id': user_id})


# ── Polling endpoint — called by JS every 3 seconds ───────────
def check_verification(request, user_id):
    try:
        user = User.objects.get(id=user_id)
        token_obj = EmailVerificationToken.objects.get(user=user)
        if token_obj.is_verified:
            # Auto login and return success
            user.backend = 'django.contrib.auth.backends.ModelBackend'
            request.session['first_login'] = True
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

    # Activate the account
    token_obj.is_verified = True
    token_obj.save()
    user = token_obj.user
    user.is_active = True
    user.save()

    # Show verified success page — JS on waiting page will catch this via polling
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
            pass
        messages.success(request, 'If that email is registered and unverified, we sent a new link.')
        return redirect('login')
    return render(request, 'resend_verification.html')


# ── Login ──────────────────────────────────────────────────────
def login(request):
    unverified = False
    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = User.objects.filter(username=username).first()
        if user and user.check_password(password) and not user.is_active:
            unverified = True
            form = AuthenticationForm()
        else:
            form = AuthenticationForm(request, data=request.POST)
            if form.is_valid():
                user = auth.authenticate(username=username, password=password)
                if user is not None:
                    auth.login(request, user)
                    return redirect('dashboard')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form, 'unverified': unverified})


# ── Logout ─────────────────────────────────────────────────────
def logout(request):
    auth.logout(request)
    return redirect('home')