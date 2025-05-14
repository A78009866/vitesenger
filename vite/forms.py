from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Post

class CustomUserCreationForm(UserCreationForm):
    full_name = forms.CharField(max_length=100, required=True)
    profile_picture = forms.ImageField(required=False)
    
    class Meta:
        model = CustomUser
        fields = ('username', 'full_name', 'email', 'password1', 'password2', 'profile_picture')

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ('content', 'image', 'video')
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'placeholder': "What's on your mind?"}),
        }

class FriendRequestForm(forms.Form):
    username = forms.CharField(max_length=150)