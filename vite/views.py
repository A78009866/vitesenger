from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from .forms import CustomUserCreationForm, PostForm, FriendRequestForm
from .models import Post, Like, Comment, SavedPost, CustomUser  # تم التعديل هنا
from django.http import JsonResponse
import cloudinary.uploader
from .forms import ProfileEditForm, PostEditForm  # إضافة الاستيراد
from .models import Notification

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
            
            # إضافة 10 نقاط للمستخدم عند إنشاء المنشور
            request.user.points += 10
            request.user.save()
            
            return redirect('home')
    else:
        form = PostForm()
    return render(request, 'social/create_post.html', {'form': form})

@login_required
def saved_posts(request):
    saved_posts = SavedPost.objects.filter(user=request.user).select_related('post').order_by('-saved_at')
    posts = [saved.post for saved in saved_posts]
    
    # إضافة حالة الإعجاب والحفظ لكل منشور
    for post in posts:
        post.is_liked = post.likes.filter(user=request.user).exists()
        post.is_saved = True  # جميع المنشورات هنا محفوظة بالضرورة
    
    return render(request, 'social/saved_posts.html', {'posts': posts})

# في دالة like_post
@login_required
def like_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    like, created = Like.objects.get_or_create(user=request.user, post=post)
    if created:
        # إرسال إشعار للمستخدم صاحب المنشور
        if request.user != post.user:
            Notification.objects.create(
                recipient=post.user,
                sender=request.user,
                notification_type='like',
                content=f"{request.user.username} أعجب بمنشورك",
                related_id=post.id
            )
    else:
        like.delete()
    return JsonResponse({
        'liked': created,
        'likes_count': post.likes.count(),
        'post_id': post_id
    })

# في دالة add_comment
def add_comment(request, post_id):
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            post = get_object_or_404(Post, id=post_id)
            comment = Comment.objects.create(user=request.user, post=post, content=content)
            
            # إرسال إشعار للمستخدم صاحب المنشور
            if request.user != post.user:
                Notification.objects.create(
                    recipient=post.user,
                    sender=request.user,
                    notification_type='comment',
                    content=f"{request.user.username} علق على منشورك",
                    related_id=post.id
                )
            
            return JsonResponse({
                'success': True,
                'username': request.user.username,
                'content': comment.content,
                'profile_picture': request.user.profile_picture.url if request.user.profile_picture else '/media/profile_pics/default_profile.png'
            })
    return JsonResponse({'success': False})

# في دالة send_friend_request
@login_required
def send_friend_request(request, username):
    receiver = get_object_or_404(CustomUser, username=username)
    if request.user != receiver and receiver not in request.user.friend_requests.all():
        request.user.friend_requests.add(receiver)
        # إرسال إشعار
        Notification.objects.create(
            recipient=receiver,
            sender=request.user,
            notification_type='friend_request',
            content=f"{request.user.username} أرسل لك طلب صداقة",
            related_id=request.user.id
        )
    return redirect('profile', username=username)

# في دالة accept_friend_request
@login_required
def accept_friend_request(request, username):
    sender = get_object_or_404(CustomUser, username=username)
    if sender in request.user.received_friend_requests.all():
        request.user.friends.add(sender)
        sender.friends.add(request.user)
        request.user.received_friend_requests.remove(sender)
        
        # إرسال إشعار للمستخدم الذي تم قبول طلبه
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
    user = get_object_or_404(CustomUser, username=username)
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
def qr_code_view(request, username):
    user = get_object_or_404(CustomUser, username=username)
    if not user.qr_code:
        user.generate_qr_code()
    return render(request, 'social/qr_code.html', {'profile_user': user})

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
    users = CustomUser.objects.filter(username__icontains=query) | CustomUser.objects.filter(full_name__icontains=query)
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
    user_to_block = get_object_or_404(CustomUser, username=username)
    
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
            user = form.save(commit=False)
            
            # Handle profile picture upload
            if 'profile_picture' in request.FILES:
                user.profile_picture = cloudinary.uploader.upload(request.FILES['profile_picture'])['url']
            elif 'profile_picture-clear' in request.POST:
                user.profile_picture = None
            
            # Handle cover photo upload
            if 'cover_photo' in request.FILES:
                user.cover_photo = cloudinary.uploader.upload(request.FILES['cover_photo'])['url']
            elif 'cover_photo-clear' in request.POST:
                user.cover_photo = None
            
            user.save()
            return redirect('profile', username=username)
    else:
        form = ProfileEditForm(instance=request.user)
    
    return render(request, 'social/edit_profile.html', {'form': form})

@login_required
def edit_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    
    if request.user != post.user:
        return redirect('home')
    
    if request.method == 'POST':
        form = PostEditForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            post = form.save(commit=False)
            
            # Handle file uploads to Cloudinary
            if 'image' in request.FILES:
                post.image = cloudinary.uploader.upload(request.FILES['image'])['url']
            if 'video' in request.FILES:
                post.video = cloudinary.uploader.upload(request.FILES['video'], resource_type="video")['url']
            
            post.save()
            return redirect('profile', username=request.user.username)
    else:
        form = PostEditForm(instance=post)
    
    return render(request, 'social/edit_post.html', {'form': form, 'post': post})

@login_required
def delete_post(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    
    if request.user != post.user:
        return redirect('home')
    
    if request.method == 'POST':
        # خصم 10 نقاط مع التحقق من عدم وجود نقاط سالبة
        request.user.points = max(0, request.user.points - 10)
        request.user.save()
        
        post.delete()
        return redirect('profile', username=request.user.username)
    
    return render(request, 'social/confirm_delete.html', {'post': post})

from .models import Message
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import json

@login_required
def chat_view(request, username):
    other_user = get_object_or_404(User, username=username)
    
    # تحديث جميع الرسائل كمقروءة ومشاهدة عند فتح المحادثة
    unread_messages = Message.objects.filter(
        sender=other_user,
        receiver=request.user,
        is_read=False
    )
    
    for msg in unread_messages:
        msg.mark_as_seen()  # استخدام الدالة الجديدة لتحديث الحقلين
    
    messages = Message.objects.filter(
        sender__in=[request.user, other_user], 
        receiver__in=[request.user, other_user]
    ).order_by("timestamp")

    return render(request, "chat.html", {
        "messages": messages, 
        "other_user": other_user
    })

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Message, CustomUser
import json
from django.db import models

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
        
        # إرسال إشعار للمستلم
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
    """جلب الرسائل بين المستخدم الحالي والمستخدم الآخر"""
    other_user = get_object_or_404(CustomUser, username=username)
    
    messages = Message.objects.filter(
        (models.Q(sender=request.user, receiver=other_user) | 
         models.Q(sender=other_user, receiver=request.user))
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
        for msg in messages
    ], safe=False)

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib.auth import get_user_model
import datetime
from django.utils import timezone
import pytz  # أضف هذا الاستيراد
from django.utils.html import strip_tags
from django.http import Http404

User = get_user_model()

@login_required
def chat_list(request, username):
    try:
        current_user = request.user
        # جلب جميع المستخدمين ما عدا الحالي
        users = User.objects.exclude(id=current_user.id)
        
        query = request.GET.get('q', '')
        if query:
            users = users.filter(username__icontains=strip_tags(query))

        user_data = []
        for user in users:
            # جلب آخر رسالة مرسلة
            last_sent = Message.objects.filter(
                sender=current_user,
                receiver=user
            ).order_by('-timestamp').first()
            
            # جلب آخر رسالة مستلمة
            last_received = Message.objects.filter(
                sender=user,
                receiver=current_user
            ).order_by('-timestamp').first()

            # تحديد آخر رسالة بين الطرفين
            last_message = None
            if last_sent and last_received:
                last_message = last_sent if last_sent.timestamp > last_received.timestamp else last_received
            else:
                last_message = last_sent or last_received

            # تحديد إذا كانت هناك رسائل جديدة
            is_new = False
            if last_message and last_message.receiver == current_user and not last_message.is_read:
                is_new = True
                last_message.is_read = True
                last_message.save()

            user_data.append({
                'user': user,
                'last_message': strip_tags(last_message.content) if last_message else "لا توجد رسائل",
                'last_time': last_message.timestamp if last_message else None,
                'is_new': is_new
            })

        # ترتيب المحادثات حسب وقت آخر رسالة (الأحدث أولاً)
        user_data.sort(key=lambda x: x['last_time'] or timezone.datetime.min.replace(tzinfo=pytz.UTC), reverse=True)
        
        return render(request, 'chat_list.html', {
            'all_users': user_data,
            'current_user': current_user
        })

    except Exception as e:
        raise Http404(f"حدث خطأ: {str(e)}")

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib.auth import get_user_model

User = get_user_model()

@login_required
def chat(request, username):
    # جلب المستخدم الذي تريد المحادثة معه
    other_user = get_object_or_404(User, username=username)
    
    context = {
        'other_user': other_user,
    }
    return render(request, 'chat.html', context)
from django.shortcuts import render

def splash(request):
    return render(request, 'splash.html')

@login_required
def notifications(request):
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()
    
    # تحديث الإشعارات كمقروءة عند فتح الصفحة
    if request.method == 'GET':
        notifications.update(is_read=True)
    
    return render(request, 'social/notifications.html', {
        'notifications': notifications,
        'unread_count': unread_count
    })

@login_required
def mark_notification_as_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.is_read = True
    notification.save()
    return JsonResponse({'success': True})

@login_required
def get_unread_notifications_count(request):
    count = Notification.objects.filter(recipient=request.user, is_read=False).count()
    return JsonResponse({'count': count})


@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)
    
    # التحقق من أن المستخدم هو صاحب التعليق أو صاحب المنشور
    if request.user != comment.user and request.user != comment.post.user:
        return JsonResponse({'success': False, 'error': 'غير مسموح لك بحذف هذا التعليق'}, status=403)
    
    if request.method == 'POST':
        post_id = comment.post.id
        comment.delete()
        return JsonResponse({'success': True, 'post_id': post_id})
    
    return JsonResponse({'success': False, 'error': 'طريقة غير مسموحة'}, status=405)