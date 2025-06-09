# views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from .forms import CustomUserCreationForm, PostForm, FriendRequestForm, ProfileEditForm, PostEditForm, ReelForm
from .models import Post, Like, Comment, SavedPost, CustomUser, Notification, Message, Reel, ReelLike, ReelComment
from django.http import JsonResponse, Http404, HttpResponseForbidden
import cloudinary.uploader
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.views.decorators.http import require_POST
from django.db import models as django_models
import json
from django.utils import timezone
import pytz
from django.utils.html import strip_tags, escape
from django.contrib.auth import get_user_model
from datetime import timedelta

User = get_user_model()


@login_required
@require_POST
def update_user_activity(request):
    request.user.last_active = timezone.now()
    request.user.save(update_fields=['last_active'])
    return JsonResponse({'status': 'success'})


@login_required
def create_post(request):
    if request.method == 'POST':
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user
            if 'image' in request.FILES:
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
                related_id=post.id
            )
    else:
        like.delete()
    return JsonResponse({
        'liked': created,
        'likes_count': post.likes.count(),
        'post_id': post_id
    })

@login_required
def add_comment(request, post_id):
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if not content:
            return JsonResponse({'success': False, 'error': 'التعليق لا يمكن أن يكون فارغًا.'})
        
        post = get_object_or_404(Post, id=post_id)
        comment = Comment.objects.create(user=request.user, post=post, content=content)
        
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
    return JsonResponse({'success': False, 'error': 'طلب غير صالح.'})


@login_required
def home(request):
    blocked_users = request.user.blocked_users.all()
    posts = Post.objects.exclude(user__in=blocked_users).order_by('-created_at')
    for post in posts:
        post.is_liked = post.likes.filter(user=request.user).exists()
        post.is_saved = SavedPost.objects.filter(user=request.user, post=post).exists()
    
    home_reels = Reel.objects.select_related('user').order_by('?')[:10]

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
        'home_reels': home_reels,
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
    user_profile = get_object_or_404(CustomUser, username=username)
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
    user_friends = request.user.friends.all()
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
    users_results = CustomUser.objects.filter(username__icontains=query) | CustomUser.objects.filter(full_name__icontains=query)
    return render(request, 'social/search_results.html', {'users': users_results, 'query': query})

def register(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, request.FILES)
        if form.is_valid():
            user_obj = form.save(commit=False)
            if 'profile_picture' in request.FILES:
                user_obj.profile_picture = cloudinary.uploader.upload(request.FILES['profile_picture'])['url']
            user_obj.save()
            auth_login(request, user_obj)
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    return render(request, 'social/register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user_auth = authenticate(username=username, password=password)
            if user_auth is not None:
                auth_login(request, user_auth)
                return redirect('home')
            else:
                messages.error(request, "اسم المستخدم أو كلمة المرور غير صحيحة")
        else:
            messages.error(request, "يرجى تصحيح الأخطاء في النموذج")
    else:
        form = AuthenticationForm()
    return render(request, 'social/login.html', {'form': form})

@require_POST
def logout_view(request):
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
            user_instance = form.save(commit=False)
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
    post_instance = get_object_or_404(Post, id=post_id)
    if request.user != post_instance.user:
        return redirect('home')
    if request.method == 'POST':
        form = PostEditForm(request.POST, request.FILES, instance=post_instance)
        if form.is_valid():
            post_to_edit = form.save(commit=False)
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
    post_to_delete = get_object_or_404(Post, id=post_id)
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
    if other_user not in request.user.friends.all():
        messages.error(request, "لا يمكنك بدء محادثة مع شخص ليس صديقك.")
        return redirect('home')
        
    unread_messages = Message.objects.filter(
        sender=other_user,
        receiver=request.user,
        is_read=False
    )
    for msg in unread_messages:
        msg.mark_as_seen()
    messages_qs = Message.objects.filter(
        sender__in=[request.user, other_user],
        receiver__in=[request.user, other_user]
    ).order_by("timestamp")
    return render(request, "chat.html", {
        "messages": messages_qs,
        "other_user": other_user
    })

@login_required
def send_message(request):
    if request.method == "POST":
        data = json.loads(request.body)
        receiver = get_object_or_404(CustomUser, username=data["receiver"])

        if receiver not in request.user.friends.all():
            return JsonResponse({"error": "لا يمكنك إرسال رسائل إلى شخص ليس صديقك."}, status=403)

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
    if other_user not in request.user.friends.all():
        return JsonResponse({"error": "لا يمكنك عرض الرسائل مع شخص ليس صديقك."}, status=403)
        
    messages_qs = Message.objects.filter(
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
def chat_list(request, username):
    try:
        current_user = request.user
        friends = current_user.friends.all() 
        query = request.GET.get('q', '')
        if query:
            friends = friends.filter(username__icontains=strip_tags(query))
            
        user_data = []
        for user_item in friends: 
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
            user_data.append({
                'user': user_item,
                'last_message': strip_tags(last_message.content) if last_message else "لا توجد رسائل",
                'last_time': last_message.timestamp if last_message else None,
                'is_new': is_new
            })
        user_data.sort(key=lambda x: x['last_time'] or timezone.datetime.min.replace(tzinfo=pytz.UTC), reverse=True)
        return render(request, 'chat_list.html', {
            'all_users': user_data,
            'current_user': current_user
        })
    except Exception as e:
        raise Http404(f"حدث خطأ: {str(e)}")


@login_required
def chat(request, username):
    other_user = get_object_or_404(User, username=username)
    if other_user not in request.user.friends.all():
        messages.error(request, "لا يمكنك بدء محادثة مع شخص ليس صديقك.")
        return redirect('home')
        
    context = {
        'other_user': other_user,
    }
    return render(request, 'chat.html', context)


def splash(request):
    return render(request, 'splash.html')


@login_required
def notifications(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)
    notifications_qs = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    
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

def game_view(request):
    return render(request, 'game.html')

@login_required
def reels_feed(request):
    featured_reel_id = request.GET.get('show_reel')
    reels_list = []

    if featured_reel_id:
        try:
            featured_reel = Reel.objects.select_related('user').prefetch_related(
                'reel_likes', 'reel_comments__user'
            ).get(id=featured_reel_id)
            reels_list.append(featured_reel)

            other_reels = Reel.objects.exclude(id=featured_reel_id).select_related('user').prefetch_related(
                'reel_likes', 'reel_comments__user'
            ).order_by('?')
            reels_list.extend(list(other_reels))

        except Reel.DoesNotExist:
            featured_reel_id = None
    
    if not featured_reel_id:
        time_threshold = timezone.now() - timedelta(hours=5)
        new_reels = Reel.objects.filter(created_at__gte=time_threshold).select_related('user').prefetch_related(
            'reel_likes', 'reel_comments__user'
        ).order_by('-created_at')
        old_reels = Reel.objects.filter(created_at__lt=time_threshold).select_related('user').prefetch_related(
            'reel_likes', 'reel_comments__user'
        ).order_by('?')
        reels_list = list(new_reels) + list(old_reels)

    reels_data = []
    for reel in reels_list:
        is_liked_by_user = reel.reel_likes.filter(user=request.user).exists()
        comments_for_reel = reel.reel_comments.all().order_by('created_at')
        reels_data.append({
            'reel': reel,
            'is_liked_by_user': is_liked_by_user,
            'comments_list': comments_for_reel,
        })
        
    user_profile_pic_url = request.user.profile_picture.url if request.user.profile_picture else \
                           '/static/images/default_profile.png'

    context = {
        'reels_data': reels_data,
        'user_profile_pic_url': user_profile_pic_url,
    }
    return render(request, 'social/reels_feed.html', context)


@login_required
def upload_reel(request):
    if request.method == 'POST':
        form = ReelForm(request.POST, request.FILES)
        if form.is_valid():
            reel = form.save(commit=False)
            reel.user = request.user
            reel.save()
            messages.success(request, 'تم نشر الريل بنجاح!')
            return redirect('reels_feed')
        else:
            messages.error(request, 'حدث خطأ أثناء رفع الريل. يرجى التحقق من النموذج.')
    else:
        form = ReelForm()
    return render(request, 'social/upload_reel.html', {'form': form})


@login_required
@require_POST
def like_reel(request, reel_id):
    reel = get_object_or_404(Reel, id=reel_id)
    like, created = ReelLike.objects.get_or_create(user=request.user, reel=reel)

    if not created:
        like.delete()
        liked = False
    else:
        liked = True
        if request.user != reel.user:
            Notification.objects.create(
                recipient=reel.user,
                sender=request.user,
                notification_type='reel_like',
                content=f"أعجب {request.user.username} بالريل الخاص بك",
                related_id=reel.id
            )
    return JsonResponse({'liked': liked, 'likes_count': reel.likes_count})

@login_required
@require_POST
def add_reel_comment(request, reel_id):
    reel = get_object_or_404(Reel, id=reel_id)
    content = request.POST.get('content', '').strip()

    if not content:
        return JsonResponse({'success': False, 'error': 'التعليق لا يمكن أن يكون فارغًا.'}, status=400)

    comment = ReelComment.objects.create(user=request.user, reel=reel, content=content)
    
    if request.user != reel.user:
        Notification.objects.create(
            recipient=reel.user,
            sender=request.user,
            notification_type='reel_comment',
            content=f"علق {request.user.username} على الريل الخاص بك",
            related_id=reel.id
        )
    
    profile_picture_url = request.user.profile_picture.url if request.user.profile_picture else \
                          '/static/images/default_profile.png'

    return JsonResponse({
        'success': True,
        'comment': {
            'id': comment.id,
            'user': {
                'username': comment.user.username,
                'profile_picture_url': profile_picture_url
            },
            'content': escape(comment.content),
            'created_at': timezone.localtime(comment.created_at).strftime('%d %b, %Y %H:%M'),
            'timesince': timezone.now() - comment.created_at
        },
        'comments_count': reel.comments_count
    })


@login_required
@require_POST
def delete_reel(request, reel_id):
    reel = get_object_or_404(Reel, id=reel_id)

    if reel.user != request.user:
        return HttpResponseForbidden(json.dumps({'success': False, 'error': 'ليس لديك صلاحية لحذف هذا الريل.'}), content_type='application/json')
    
    try:
        if reel.video and hasattr(reel.video, 'public_id'):
            cloudinary.uploader.destroy(reel.video.public_id, resource_type="video")

        reel.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        print(f"Error deleting reel {reel_id}: {e}")
        return JsonResponse({'success': False, 'error': 'حدث خطأ أثناء محاولة حذف الريل.'}, status=500)

def reel_detail_view(request, reel_id):
    reel = get_object_or_404(Reel.objects.select_related('user').prefetch_related('reel_comments__user'), id=reel_id)

    is_liked_by_user = False
    if request.user.is_authenticated:
        is_liked_by_user = reel.reel_likes.filter(user=request.user).exists()

    comments_list = reel.reel_comments.all().order_by('-created_at')

    reel_data = {
        'reel': reel,
        'is_liked_by_user': is_liked_by_user,
        'comments_list': comments_list,
    }

    context = {
        'reel_data': reel_data,
    }
    return render(request, 'social/reel_detail.html', context)