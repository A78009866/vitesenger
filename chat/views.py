from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from .forms import CustomUserCreationForm, PostForm, FriendRequestForm
from .models import Post, Like, Comment, SavedPost, User
from django.http import JsonResponse
import cloudinary.uploader

@login_required
def home(request):
    posts = Post.objects.all().order_by('-created_at')
    # إضافة حالة الإعجاب لكل منشور
    for post in posts:
        post.is_liked = post.likes.filter(user=request.user).exists()  # تم التعديل هنا
    return render(request, 'social/home.html', {'posts': posts})
    
@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user
            
            # Handle file uploads to Cloudinary
            if 'image' in request.FILES:
                post.image = cloudinary.uploader.upload(request.FILES['image'])['url']
            if 'video' in request.FILES:
                post.video = cloudinary.uploader.upload(request.FILES['video'], resource_type="video")['url']
            
            post.save()
            return redirect('home')
    else:
        form = PostForm()
    return render(request, 'social/create_post.html', {'form': form})

@login_required
def like_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    like, created = Like.objects.get_or_create(user=request.user, post=post)
    if not created:
        like.delete()
    return JsonResponse({
        'liked': created,  # تم التعديل هنا من 'is_liked' إلى 'liked'
        'likes_count': post.likes.count(),
        'post_id': post_id
    })

@login_required
def add_comment(request, post_id):
    if request.method == 'POST':
        post = get_object_or_404(Post, id=post_id)
        content = request.POST.get('content')
        if content:
            Comment.objects.create(user=request.user, post=post, content=content)
            return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def save_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    saved_post, created = SavedPost.objects.get_or_create(user=request.user, post=post)
    if not created:
        saved_post.delete()
    return JsonResponse({'is_saved': created})

@login_required
def send_friend_request(request, username):
    receiver = get_object_or_404(User, username=username)
    if request.user != receiver and receiver not in request.user.friend_requests.all():
        request.user.friend_requests.add(receiver)
    return redirect('profile', username=username)

@login_required
def accept_friend_request(request, username):
    sender = get_object_or_404(User, username=username)
    if sender in request.user.received_friend_requests.all():
        request.user.friends.add(sender)
        sender.friends.add(request.user)
        request.user.received_friend_requests.remove(sender)
    return redirect('friends')

@login_required
def reject_friend_request(request, username):
    sender = get_object_or_404(User, username=username)
    if sender in request.user.received_friend_requests.all():
        request.user.received_friend_requests.remove(sender)
    return redirect('friends')

@login_required
def profile(request, username):
    user = get_object_or_404(User, username=username)
    posts = user.posts.all().order_by('-created_at')
    is_friend = user in request.user.friends.all()
    has_sent_request = user in request.user.friend_requests.all()
    has_received_request = request.user in user.friend_requests.all()
    
    context = {
        'profile_user': user,
        'posts': posts,
        'is_friend': is_friend,
        'has_sent_request': has_sent_request,
        'has_received_request': has_received_request,
    }
    return render(request, 'social/profile.html', context)

@login_required
def friends(request):
    friends = request.user.friends.all()
    received_requests = request.user.received_friend_requests.all()
    sent_requests = request.user.friend_requests.all()
    
    context = {
        'friends': friends,
        'received_requests': received_requests,
        'sent_requests': sent_requests,
    }
    return render(request, 'social/friends.html', context)

@login_required
def search_users(request):
    query = request.GET.get('q', '')
    users = User.objects.filter(username__icontains=query) | User.objects.filter(full_name__icontains=query)
    return render(request, 'social/search_results.html', {'users': users, 'query': query})

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            
            # Handle profile picture upload to Cloudinary
            if 'profile_picture' in request.FILES:
                user.profile_picture = cloudinary.uploader.upload(request.FILES['profile_picture'])['url']
            
            user.save()
            auth_login(request, user)
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'social/register.html', {'form': form})

from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('home')  # غيّر هذا إذا أردت توجيهاً مختلفاً
            else:
                messages.error(request, "اسم المستخدم أو كلمة المرور غير صحيحة")
        else:
            messages.error(request, "يرجى تصحيح الأخطاء في النموذج")
    else:
        form = AuthenticationForm()
    
    return render(request, 'social/login.html', {'form': form})
