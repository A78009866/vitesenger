from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login as auth_login
from .forms import CustomUserCreationForm, PostForm, FriendRequestForm, ProfileEditForm, PostEditForm, ReelForm
from .models import Post, Like, Comment, SavedPost, CustomUser, Notification, Message, Reel, ReelLike, ReelComment, Story, StoryLike
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
from django.db.models import F, Exists, OuterRef
import google.generativeai as genai
from django import forms
import random
from django.views.decorators.cache import cache_page


User = get_user_model()

@login_required
def chat_list(request, username=None):
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
            
            last_message_content = "لا توجد رسائل"
            if last_message:
                if last_message.content:
                    last_message_content = strip_tags(last_message.content)
                elif last_message.image:
                    last_message_content = "📷 صورة"
                elif last_message.video:
                    last_message_content = "🎥 فيديو"

            user_data.append({
                'user': user_item,
                'last_message': last_message_content,
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

@cache_page(60 * 1)  # التخزين المؤقت للصفحة لمدة دقيقة واحدة

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

# views.py (تعديل دالة send_message)
@login_required
@require_POST
def send_message(request):
    receiver_username = request.POST.get("receiver")
    if not receiver_username:
        return JsonResponse({"error": "المستلم غير محدد."}, status=400)

    receiver = get_object_or_404(CustomUser, username=receiver_username)

    if receiver not in request.user.friends.all():
        return JsonResponse({"error": "لا يمكنك إرسال رسائل إلى شخص ليس صديقك."}, status=403)

    content = request.POST.get("content", "").strip()
    image_file = request.FILES.get('image')
    video_file = request.FILES.get('video')
    voice_file = request.FILES.get('voice_note')
    reply_to_id = request.POST.get("reply_to")  # الحصول على معرف الرسالة المردود عليها

    if not content and not image_file and not video_file and not voice_file:
        return JsonResponse({"error": "لا يمكن إرسال رسالة فارغة"}, status=400)

    # الحصول على الرسالة المردود عليها إذا وجدت
    reply_to_message = None
    if reply_to_id:
        try:
            reply_to_message = Message.objects.get(id=reply_to_id, 
                                                 sender__in=[request.user, receiver],
                                                 receiver__in=[request.user, receiver])
        except Message.DoesNotExist:
            pass

    message = Message(
        sender=request.user,
        receiver=receiver,
        content=content,
        is_system_message=False,
        reply_to=reply_to_message  # تعيين الرسالة المردود عليها
    )

    if image_file:
        message.image = image_file

    if video_file:
        message.video = video_file
    
    if voice_file:
        message.voice_note = voice_file

    message.save()
    
    response_data = {
        "id": message.id,
        "sender": message.sender.username,
        "receiver": receiver.username,
        "content": message.content,
        "image_url": message.image.url if message.image else None,
        "video_url": message.video.url if message.video else None,
        "voice_note_url": message.voice_note.url if message.voice_note else None,
        "timestamp": message.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
        "is_read": message.is_read,
        "seen_at": None,
        "is_system_message": message.is_system_message,
        "reply_to": None
    }

    # إضافة بيانات الرسالة المردود عليها إذا وجدت
    if reply_to_message:
        response_data["reply_to"] = {
            "id": reply_to_message.id,
            "sender": reply_to_message.sender.username,
            "content": reply_to_message.content,
            "image_url": reply_to_message.image.url if reply_to_message.image else None,
            "video_url": reply_to_message.video.url if reply_to_message.video else None,
            "voice_note_url": reply_to_message.voice_note.url if reply_to_message.voice_note else None,
        }

    return JsonResponse(response_data)

# views.py (تعديل دالة get_messages)
@login_required
def get_messages(request, username):
    other_user = get_object_or_404(CustomUser, username=username)
    if other_user not in request.user.friends.all():
        return JsonResponse({"error": "لا يمكنك عرض الرسائل مع شخص ليس صديقك."}, status=403)
        
    messages_qs = Message.objects.filter(
        (django_models.Q(sender=request.user, receiver=other_user) |
         django_models.Q(sender=other_user, receiver=request.user))
    ).select_related('reply_to').order_by("timestamp")

    Message.objects.filter(sender=other_user, receiver=request.user, is_read=False).update(is_read=True, seen_at=timezone.now())

    return JsonResponse([
        {
            "id": msg.id,
            "sender": msg.sender.username,
            "receiver": msg.receiver.username,
            "content": msg.content,
            "image_url": msg.image.url if msg.image else None,
            "video_url": msg.video.url if msg.video else None,
            "voice_note_url": msg.voice_note.url if msg.voice_note else None,
            "timestamp": msg.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            "is_read": msg.is_read,
            "seen_at": msg.seen_at.strftime("%Y-%m-%d %H:%M:%S") if msg.seen_at else None,
            "is_system_message": msg.is_system_message,
            "reply_to": {
                "id": msg.reply_to.id,
                "sender": msg.reply_to.sender.username,
                "content": msg.reply_to.content,
                "image_url": msg.reply_to.image.url if msg.reply_to.image else None,
                "video_url": msg.reply_to.video.url if msg.reply_to.video else None,
                "voice_note_url": msg.reply_to.voice_note.url if msg.reply_to.voice_note else None,
            } if msg.reply_to else None
        }
        for msg in messages_qs
    ], safe=False)