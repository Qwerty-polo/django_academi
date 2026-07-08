from cProfile import label
from importlib.metadata import requires

from django import  forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.db.models.fields import BooleanField

from .models import Profile

class UserRegisterForm(UserCreationForm):
    username = forms.CharField(
        label='input Login',
        required=True,
        help_text='dont input: % # _',
        widget=forms.TextInput(attrs={'placeholder': 'Username'})

    )
    email = forms.EmailField(
        label='input Email',
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Email'})

    )

    # some = forms.ModelChoiceField(queryset=User.objects.all())
    password1 = forms.CharField(
        label='input Password',
        required=True,
        help_text='password warning: dont type small password',
        widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    password2 = forms.CharField(
        label='confirm Password',
        required=True,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}))


    class Meta:
        model = User
        fields = ['username','email', 'password1', 'password2']


class UserUpdateForm(forms.ModelForm):
    username = forms.CharField(
        label='input Login',
        required=True,
        help_text='dont input: % # _',
        widget=forms.TextInput(attrs={'placeholder': 'Username'})

    )
    email = forms.EmailField(
        label='input Email',
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Email'})

    )

    class Meta:
        model = User
        fields = ['username', 'email']


class ProfileImageForm(forms.ModelForm):
    img = forms.ImageField(
        label='input Image',
        required=False,
        widget=forms.FileInput()
    )

    email_consent = forms.BooleanField(
        label = 'Згода на відправлення на почту',
        required = False
    )

    class Meta:
        model = Profile
        fields = ['img', 'gender', 'email_consent']

