# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from .forms import CustomUserCreationForm, PostForm, FriendRequestForm # Removed ProfileEditForm if not used elsewhere, check usage
from .models import Post, Like, Comment, SavedPost, CustomUser, Notification, Message # Removed Story
from django.http import JsonResponse, Http404 # Added Http404
import cloudinary.uploader
from .forms import ProfileEditForm, PostEditForm
# from .models import Notification # Already imported

from django.contrib.auth import authenticate, login, logout # login was already imported as auth_login
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.http import require_POST
from django.db import models as django_models #renamed to avoid conflict if any
import json
from django.utils import timezone # Keep if used by other parts
import pytz # Keep if used by other parts
from django.utils.html import strip_tags # Keep
from django.contrib.auth import get_user_model # Keep

User = get_user_model()


@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user
            if 'image' in request.FILES:
                # Ensure Cloudinary is configured to return URLs directly or adjust accordingly
                upload_result = cloudinary.uploader.upload(request.FILES['image'])
                post.image = upload_result.get('secure_url', upload_result.get('url'))
            if 'video' in request.FILES:
                upload_result = cloudinary.uploader.upload(request.FILES['video'], resource_type="video")
                post.video = upload_result.get('secure_url', upload_result.get('url'))
            post.save()
            request.user.points += 10
            request.user.save()
            return redirect('home')
    else:
        form = PostForm()
    return render(request, 'social/create_post.html', {'form': form})

# Removed saved_posts view
# @login_required
# def saved_posts(request):
#     saved_posts_qs = SavedPost.objects.filter(user=request.user).select_related('post').order_by('-saved_at')
#     posts = [saved.post for saved in saved_posts_qs]
#     for post in posts:
#         post.is_liked = post.likes.filter(user=request.user).exists()
#         post.is_saved = True # This logic is removed
#     return render(request, 'social/saved_posts.html', {'posts': posts})


@login_required
def like_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    like, created = Like.objects.get_or_create(user=request.user, post=post)
    if created:
        if request.user != post.user:
            Notification.objects.create(
                recipient=post.user,
                sender=request.user,
                notification_type='like',
                content=f"{request.user.username} أعجب بمنشورك",
                related_id=post.id # This is the post_id
            )
    else:
        like.delete()
    return JsonResponse({
        'liked': created,
        'likes_count': post.likes.count(),
        'post_id': post_id
    })

@login_required # Ensure add_comment requires login if it's not already
def add_comment(request, post_id):
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if not content: # Basic validation
            return JsonResponse({'success': False, 'error': 'التعليق لا يمكن أن يكون فارغًا.'})
        
        post = get_object_or_404(Post, id=post_id)
        comment = Comment.objects.create(user=request.user, post=post, content=content)
        
        if request.user != post.user:
            Notification.objects.create(
                recipient=post.user,
                sender=request.user,
                notification_type='comment',
                content=f"{request.user.username} علق على منشورك",
                related_id=post.id # This is the post_id
            )
        return JsonResponse({
            'success': True,
            'username': request.user.username,
            'content': comment.content,
            'profile_picture': request.user.profile_picture.url if request.user.profile_picture else '/media/profile_pics/default_profile.png'
        })
    return JsonResponse({'success': False, 'error': 'طلب غير صالح.'})


# ... (other views remain largely the same, except for 'home' view)

@login_required
def home(request):
    blocked_users = request.user.blocked_users.all()
    posts = Post.objects.exclude(user__in=blocked_users).order_by('-created_at')
    for post in posts:
        post.is_liked = post.likes.filter(user=request.user).exists()
        post.is_saved = SavedPost.objects.filter(user=request.user, post=post).exists()
    
    unread_messages_count = Message.objects.filter(
        receiver=request.user,
        is_read=False
    ).count()
    
    unread_notifications_count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    context = {
        'posts': posts,
        'unread_messages_count': unread_messages_count,
        'unread_count': unread_notifications_count,
    }
    return render(request, 'social/home.html', context)


@login_required
def send_friend_request(request, username):
    receiver = get_object_or_404(CustomUser, username=username)
    if request.user != receiver and receiver not in request.user.friend_requests.all():
        request.user.friend_requests.add(receiver)
        Notification.objects.create(
            recipient=receiver,
            sender=request.user,
            notification_type='friend_request',
            content=f"{request.user.username} أرسل لك طلب صداقة",
            related_id=request.user.id
        )
    return redirect('profile', username=username)

@login_required
def accept_friend_request(request, username):
    sender = get_object_or_404(CustomUser, username=username)
    if sender in request.user.received_friend_requests.all():
        request.user.friends.add(sender)
        sender.friends.add(request.user)
        request.user.received_friend_requests.remove(sender)
        Notification.objects.create(
            recipient=sender,
            sender=request.user,
            notification_type='friend_accept',
            content=f"{request.user.username} قبل طلب صداقتك",
            related_id=request.user.id
        )
    return redirect('friends')

@login_required
def reject_friend_request(request, username):
    sender = get_object_or_404(CustomUser, username=username)
    if sender in request.user.received_friend_requests.all():
        request.user.received_friend_requests.remove(sender)
    return redirect('friends')

@login_required
def profile(request, username):
    user_profile = get_object_or_404(CustomUser, username=username) # Renamed to user_profile to avoid conflict with User model
    posts = user_profile.posts.all().order_by('-created_at')
    is_friend = user_profile in request.user.friends.all()
    has_sent_request = user_profile in request.user.friend_requests.all()
    has_received_request = request.user in user_profile.friend_requests.all()
    context = {
        'profile_user': user_profile,
        'posts': posts,
        'is_friend': is_friend,
        'has_sent_request': has_sent_request,
        'has_received_request': has_received_request,
    }
    return render(request, 'social/profile.html', context)

@login_required
def qr_code_view(request, username):
    user_profile = get_object_or_404(CustomUser, username=username)
    if not user_profile.qr_code:
        user_profile.generate_qr_code()
    return render(request, 'social/qr_code.html', {'profile_user': user_profile})

@login_required
def friends(request):
    user_friends = request.user.friends.all() # Renamed to avoid conflict
    received_requests = request.user.received_friend_requests.all()
    sent_requests = request.user.friend_requests.all()
    context = {
        'friends': user_friends,
        'received_requests': received_requests,
        'sent_requests': sent_requests,
    }
    return render(request, 'social/friends.html', context)

@login_required
def search_users(request):
    query = request.GET.get('q', '')
    users_results = CustomUser.objects.filter(username__icontains=query) | CustomUser.objects.filter(full_name__icontains=query) # Renamed
    return render(request, 'social/search_results.html', {'users': users_results, 'query': query})

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user_obj = form.save(commit=False) # Renamed
            if 'profile_picture' in request.FILES:
                user_obj.profile_picture = cloudinary.uploader.upload(request.FILES['profile_picture'])['url']
            user_obj.save()
            auth_login(request, user_obj)
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'social/register.html', {'form': form})

def login_view(request): # Already defined
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user_auth = authenticate(username=username, password=password) # Renamed
            if user_auth is not None:
                auth_login(request, user_auth) # Use auth_login consistently
                return redirect('home')
            else:
                messages.error(request, "اسم المستخدم أو كلمة المرور غير صحيحة")
        else:
            messages.error(request, "يرجى تصحيح الأخطاء في النموذج")
    else:
        form = AuthenticationForm()
    return render(request, 'social/login.html', {'form': form})

@require_POST
def logout_view(request): # Already defined
    logout(request)
    return redirect('login')

@login_required
def block_user(request, username):
    user_to_block = get_object_or_404(CustomUser, username=username)
    if request.user == user_to_block:
        return redirect('profile', username=username)
    request.user.blocked_users.add(user_to_block)
    request.user.friend_requests.remove(user_to_block)
    user_to_block.friend_requests.remove(request.user)
    request.user.friends.remove(user_to_block)
    user_to_block.friends.remove(request.user)
    return redirect('profile', username=username)

@login_required
def unblock_user(request, username):
    user_to_unblock = get_object_or_404(CustomUser, username=username)
    request.user.blocked_users.remove(user_to_unblock)
    return redirect('profile', username=username)

@login_required
def edit_profile(request, username):
    if request.user.username != username:
        return redirect('profile', username=username)
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            user_instance = form.save(commit=False) # Renamed
            if 'profile_picture' in request.FILES:
                user_instance.profile_picture = cloudinary.uploader.upload(request.FILES['profile_picture'])['url']
            elif 'profile_picture-clear' in request.POST:
                user_instance.profile_picture = None
            if 'cover_photo' in request.FILES:
                user_instance.cover_photo = cloudinary.uploader.upload(request.FILES['cover_photo'])['url']
            elif 'cover_photo-clear' in request.POST:
                user_instance.cover_photo = None
            user_instance.save()
            return redirect('profile', username=username)
    else:
        form = ProfileEditForm(instance=request.user)
    return render(request, 'social/edit_profile.html', {'form': form})

@login_required
def edit_post(request, post_id):
    post_instance = get_object_or_404(Post, id=post_id) # Renamed
    if request.user != post_instance.user:
        return redirect('home')
    if request.method == 'POST':
        form = PostEditForm(request.POST, request.FILES, instance=post_instance)
        if form.is_valid():
            post_to_edit = form.save(commit=False) # Renamed
            if 'image' in request.FILES:
                post_to_edit.image = cloudinary.uploader.upload(request.FILES['image'])['url']
            if 'video' in request.FILES:
                post_to_edit.video = cloudinary.uploader.upload(request.FILES['video'], resource_type="video")['url']
            post_to_edit.save()
            return redirect('profile', username=request.user.username)
    else:
        form = PostEditForm(instance=post_instance)
    return render(request, 'social/edit_post.html', {'form': form, 'post': post_instance})

@login_required
def delete_post(request, post_id):
    post_to_delete = get_object_or_404(Post, id=post_id) # Renamed
    if request.user != post_to_delete.user:
        return redirect('home')
    if request.method == 'POST':
        request.user.points = max(0, request.user.points - 10)
        request.user.save()
        post_to_delete.delete()
        return redirect('profile', username=request.user.username)
    return render(request, 'social/confirm_delete.html', {'post': post_to_delete})

@login_required
def chat_view(request, username):
    other_user = get_object_or_404(User, username=username)
    unread_messages = Message.objects.filter(
        sender=other_user,
        receiver=request.user,
        is_read=False
    )
    for msg in unread_messages:
        msg.mark_as_seen()
    messages_qs = Message.objects.filter( # Renamed
        sender__in=[request.user, other_user],
        receiver__in=[request.user, other_user]
    ).order_by("timestamp")
    return render(request, "chat.html", { # Ensure this template name is correct
        "messages": messages_qs,
        "other_user": other_user
    })

@login_required
def send_message(request):
    if request.method == "POST":
        data = json.loads(request.body)
        receiver = get_object_or_404(CustomUser, username=data["receiver"])
        content = data["content"].strip()
        if not content:
            return JsonResponse({"error": "لا يمكن إرسال رسالة فارغة"}, status=400)
        message = Message.objects.create(
            sender=request.user,
            receiver=receiver,
            content=content,
            is_read=False,
            seen_at=None
        )
        Notification.objects.create(
            recipient=receiver,
            sender=request.user,
            notification_type='message',
            content=content
        )
        return JsonResponse({
            "id": message.id,
            "sender": message.sender.username,
            "receiver": receiver.username,
            "content": message.content,
            "timestamp": message.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "is_read": message.is_read,
            "seen_at": None
        })

@login_required
def get_messages(request, username):
    other_user = get_object_or_404(CustomUser, username=username)
    messages_qs = Message.objects.filter( # Renamed
        (django_models.Q(sender=request.user, receiver=other_user) |
         django_models.Q(sender=other_user, receiver=request.user))
    ).order_by("timestamp")
    return JsonResponse([
        {
            "id": msg.id,
            "sender": msg.sender.username,
            "receiver": msg.receiver.username,
            "content": msg.content,
            "timestamp": msg.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "is_read": msg.is_read,
            "seen_at": msg.seen_at.strftime("%Y-%m-%d %H:%M:%S") if msg.seen_at else None
        }
        for msg in messages_qs
    ], safe=False)

@login_required
def chat_list(request, username): # The 'username' parameter seems unused here for chat_list
    try:
        current_user = request.user
        users = User.objects.exclude(id=current_user.id)
        query = request.GET.get('q', '')
        if query:
            users = users.filter(username__icontains=strip_tags(query))
        user_data = []
        for user_item in users: # Renamed user to user_item
            last_sent = Message.objects.filter(
                sender=current_user,
                receiver=user_item
            ).order_by('-timestamp').first()
            last_received = Message.objects.filter(
                sender=user_item,
                receiver=current_user
            ).order_by('-timestamp').first()
            last_message = None
            if last_sent and last_received:
                last_message = last_sent if last_sent.timestamp > last_received.timestamp else last_received
            else:
                last_message = last_sent or last_received
            is_new = False
            if last_message and last_message.receiver == current_user and not last_message.is_read:
                is_new = True
                # Mark as read here if opening chat list should mark them read
                # last_message.is_read = True
                # last_message.save()
            user_data.append({
                'user': user_item,
                'last_message': strip_tags(last_message.content) if last_message else "لا توجد رسائل",
                'last_time': last_message.timestamp if last_message else None,
                'is_new': is_new
            })
        user_data.sort(key=lambda x: x['last_time'] or timezone.datetime.min.replace(tzinfo=pytz.UTC), reverse=True)
        return render(request, 'chat_list.html', { # Ensure this template name is correct
            'all_users': user_data,
            'current_user': current_user
        })
    except Exception as e:
        raise Http404(f"حدث خطأ: {str(e)}")


@login_required
def chat(request, username): # This seems like a duplicate of chat_view or serves a different purpose?
    other_user = get_object_or_404(User, username=username)
    context = {
        'other_user': other_user,
    }
    return render(request, 'chat.html', context) # Ensure this template name is correct


def splash(request): # Ensure this template name is correct
    return render(request, 'splash.html')


@login_required
def notifications(request):
    # قم بتعليم جميع الإشعارات غير المقروءة للمستخدم الحالي كـ "مقروءة"
    # بمجرد دخوله إلى صفحة الإشعارات.
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True) #

    # ثم قم بجلب جميع إشعارات المستخدم (بما في ذلك التي تم تعليمها كمقروءة للتو) لعرضها.
    notifications_qs = Notification.objects.filter(recipient=request.user).order_by('-created_at') #
    
    return render(request, 'social/notifications.html', {
        'notifications': notifications_qs,
    })

@login_required
def mark_notification_as_read(request, notification_id):
    if request.method == 'POST':
        notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
        notification.is_read = True
        notification.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'status': 'error'}, status=400)

@login_required
def get_unread_notifications_count(request):
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'count': count})

@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    if request.user != comment.user and request.user != comment.post.user:
        return JsonResponse({'success': False, 'error': 'غير مسموح لك بحذف هذا التعليق'}, status=403)
    if request.method == 'POST':
        post_id = comment.post.id
        comment.delete()
        return JsonResponse({'success': True, 'post_id': post_id})
    return JsonResponse({'success': False, 'error': 'طريقة غير مسموحة'}, status=405)

def game_view(request): # Ensure this template name is correct
    return render(request, 'game.html')

