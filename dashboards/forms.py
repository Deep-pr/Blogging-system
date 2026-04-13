from django import forms
from blogs.models import Category, Blog
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Profile, Feedback


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ('category_name',)


class BlogPostForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user and not (
            user.is_superuser
            or user.is_staff
            or user.groups.filter(name='Manager').exists()
        ):
            self.fields['category'].queryset = Category.objects.filter(owner=user)

    class Meta:
        model = Blog
        fields = ('title', 'category', 'featured_image', 'short_description', 'blog_body', 'status', 'is_featured')


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=True)

    class Meta:
        model = Profile
        fields = ('profile_image', 'bio')
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user')
        super().__init__(*args, **kwargs)
        self.fields['first_name'].initial = self.user.first_name
        self.fields['last_name'].initial = self.user.last_name
        self.fields['email'].initial = self.user.email

    def clean_email(self):
        email = self.cleaned_data['email'].strip()
        current_email = (self.user.email or '').strip()

        if email.lower() == current_email.lower():
            return email

        if User.objects.exclude(pk=self.user.pk).filter(email__iexact=email).exists():
            raise forms.ValidationError('This email is already registered.')
        return email

    def save(self, commit=True):
        profile = super().save(commit=False)
        self.user.first_name = self.cleaned_data['first_name']
        self.user.last_name = self.cleaned_data['last_name']
        self.user.email = self.cleaned_data['email']
        if commit:
            self.user.save()
            profile.user = self.user
            profile.save()
        return profile


class AddUserForm(UserCreationForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        # Hide is_superuser from non-superusers
        if request and not request.user.is_superuser:
            self.fields.pop('is_superuser', None)
            self.fields.pop('user_permissions', None)


class EditUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        # Hide is_superuser from non-superusers
        if request and not request.user.is_superuser:
            self.fields.pop('is_superuser', None)
            self.fields.pop('user_permissions', None)


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ('name', 'email', 'feedback_type', 'subject', 'message', 'page_url')
        widgets = {
            'message': forms.Textarea(attrs={'rows': 5}),
            'page_url': forms.TextInput(attrs={'placeholder': 'Optional page URL'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and user.is_authenticated:
            self.fields['name'].initial = user.get_full_name().strip() or user.username
            self.fields['email'].initial = user.email
            self.fields['page_url'].initial = kwargs.get('initial', {}).get('page_url', '')


class FeedbackManageForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ('name', 'email', 'feedback_type', 'subject', 'message', 'page_url', 'status')
        widgets = {
            'message': forms.Textarea(attrs={'rows': 5}),
        }
