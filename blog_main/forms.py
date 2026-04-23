from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


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
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user
