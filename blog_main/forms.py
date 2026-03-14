from django.contrib.auth.models import User

from django.contrib.auth.forms import UserCreationForm


class RegisterForm(UserCreationForm):
    
    class Meta:
        model = User
        fields = ('email','username', 'password1', 'password2')

    # def save(self, commit=True):
    #     user = super().save(commit=False)
    #     user.email = self.cleaned_data['email']
    #     if commit:
    #         user.save()
    #     return user
    
    
    