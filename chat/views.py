from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from .forms import CustomUserCreationForm, PostForm, FriendRequestForm
from .models import Post, Like, Comment, SavedPost, User
from django.http import JsonResponse
import cloudinary.uploader

@login_required
def home(request):
    blocked_users = request.user.blocked_users.all()
    posts = Post.objects.exclude(user__in=blocked_users).order_by('-created_at')
    for post in posts:
        post.is_liked = post.likes.filter(user=request.user).exists()
        post.is_saved = SavedPost.objects.filter(user=request.user, post=post).exists()
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

from django.http import JsonResponse

def add_comment(request, post_id):
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            post = get_object_or_404(Post, id=post_id)
            comment = Comment.objects.create(user=request.user, post=post, content=content)
            return JsonResponse({
                'success': True,
                'username': request.user.username,
                'content': comment.content,
                'profile_picture': request.user.profile_picture.url if request.user.profile_picture else '/media/profile_pics/default_profile.png'
            })
    return JsonResponse({'success': False})

@login_required
def saved_posts(request):
    saved_posts = SavedPost.objects.filter(user=request.user).select_related('post').order_by('-saved_at')
    posts = [saved.post for saved in saved_posts]
    
    # إضافة حالة الإعجاب والحفظ لكل منشور
    for post in posts:
        post.is_liked = post.likes.filter(user=request.user).exists()
        post.is_saved = True  # جميع المنشورات هنا محفوظة بالضرورة
    
    return render(request, 'social/saved_posts.html', {'posts': posts})

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

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')  # غيّرها لاسم URL المناسب عندك

@login_required
def block_user(request, username):
    user_to_block = get_object_or_404(User, username=username)
    
    # لا يمكن للمستخدم حظر نفسه
    if request.user == user_to_block:
        return redirect('profile', username=username)
    
    # إضافة المستخدم إلى قائمة المحظورين
    request.user.blocked_users.add(user_to_block)
    
    # إزالة أي طلبات صداقة بين المستخدمين
    request.user.friend_requests.remove(user_to_block)
    user_to_block.friend_requests.remove(request.user)
    
    # إزالة أي صداقة موجودة
    request.user.friends.remove(user_to_block)
    user_to_block.friends.remove(request.user)
    
    return redirect('profile', username=username)

@login_required
def unblock_user(request, username):
    user_to_unblock = get_object_or_404(User, username=username)
    request.user.blocked_users.remove(user_to_unblock)
    return redirect('profile', username=username)