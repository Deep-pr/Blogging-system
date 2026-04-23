from django import forms
from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template import loader
from django.urls import reverse

from blogs.models import PendingRegistration


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        help_text='Required. Enter a valid email address.'
    )
    profile_image = forms.ImageField(
        required=False,
        help_text='Optional. Upload a profile photo.'
    )

    class Meta:
        model = User
        fields = ('email', 'username', 'first_name', 'last_name', 'profile_image', 'password1', 'password2')

    field_order = ('email', 'username', 'first_name', 'last_name', 'profile_image', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(self.field_order)
        self.fields['email'].widget.attrs.update({
            'autofocus': True,
            'autocomplete': 'email',
        })
        self.fields['username'].widget.attrs.update({
            'autocomplete': 'username',
        })

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user


class FutureFluxPasswordResetForm(PasswordResetForm):
    def send_mail(
        self,
        subject_template_name,
        email_template_name,
        context,
        from_email,
        to_email,
        html_email_template_name=None,
    ):
        subject = loader.render_to_string(subject_template_name, context)
        subject = ''.join(subject.splitlines())
        body = loader.render_to_string(email_template_name, context)

        email_message = EmailMultiAlternatives(subject, body, from_email, [to_email])
        if html_email_template_name is not None:
            html_email = loader.render_to_string(html_email_template_name, context)
            email_message.attach_alternative(html_email, 'text/html')

        email_message.send(fail_silently=False)

    def save(
        self,
        domain_override=None,
        subject_template_name='registration/password_reset_subject.txt',
        email_template_name='registration/password_reset_email.txt',
        use_https=False,
        token_generator=default_token_generator,
        from_email=None,
        request=None,
        html_email_template_name=None,
        extra_email_context=None,
    ):
        email = self.cleaned_data['email']
        active_users = list(self.get_users(email))

        super().save(
            domain_override=domain_override,
            subject_template_name=subject_template_name,
            email_template_name=email_template_name,
            use_https=use_https,
            token_generator=token_generator,
            from_email=from_email,
            request=request,
            html_email_template_name=html_email_template_name,
            extra_email_context=extra_email_context,
        )

        if active_users:
            return

        pending_registration = PendingRegistration.objects.filter(
            email__iexact=email,
            verified_user__isnull=True,
        ).first()
        if not pending_registration or request is None:
            return

        if pending_registration.is_expired():
            pending_registration.refresh_token()

        verify_url = request.build_absolute_uri(
            reverse('verify_email', kwargs={'token': str(pending_registration.token)})
        )
        send_mail(
            subject='Verify your FutureFlux email',
            message=(
                f'Hi {pending_registration.username},\n\n'
                'You started creating a FutureFlux account, but your email is not verified yet.\n'
                'Use the link below to verify your email and activate your account:\n\n'
                f'{verify_url}\n\n'
                'This link expires in 24 hours.\n\n'
                'If you did not request this, you can ignore this email.'
            ),
            from_email=from_email or settings.DEFAULT_FROM_EMAIL,
            recipient_list=[pending_registration.email],
            fail_silently=False,
        )
