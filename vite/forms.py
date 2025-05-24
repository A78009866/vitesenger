from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Post

class CustomUserCreationForm(UserCreationForm):
    full_name = forms.CharField(max_length=100, required=True)
    profile_picture = forms.ImageField(required=False)
    
    class Meta:
        model = CustomUser
        fields = ('username', 'full_name', 'email', 'password1', 'password2', 'profile_picture')

class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'full_name', 'email', 'profile_picture', 'cover_photo', 'bio')
        widgets = {
            'bio': forms.Textarea(attrs={'rows': 3}),
            'profile_picture': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'cover_photo': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['profile_picture'].required = False
        self.fields['cover_photo'].required = False

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ('content', 'image', 'video')
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3, 'placeholder': "What's on your mind?"}),
        }

class PostEditForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ('content', 'image', 'video')
        widgets = {
            'content': forms.Textarea(attrs={'rows': 3}),
        }

class FriendRequestForm(forms.Form):
    username = forms.CharField(max_length=150)