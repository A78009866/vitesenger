# models.py
import cloudinary
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.timezone import now # Keep if used by other models
from cloudinary.models import CloudinaryField
from django.utils import timezone # Keep if used by other models
import qrcode
from io import BytesIO
from django.core.files import File
# import os # Remove if not used elsewhere
# from datetime import timedelta # Remove if Story was the only user

class CustomUser(AbstractUser):
    is_verified = models.BooleanField(default=False)
    full_name = models.CharField(max_length=100, blank=True)
    profile_picture = CloudinaryField('image', blank=True, null=True, default='profile_pics/default_profile.png')
    cover_photo = CloudinaryField('image', blank=True, null=True, default='cover_photos/default_cover.jpg')
    bio = models.TextField(blank=True)
    friends = models.ManyToManyField('self', symmetrical=False, blank=True)
    friend_requests = models.ManyToManyField('self', symmetrical=False, blank=True,
                                           related_name='received_friend_requests')
    blocked_users = models.ManyToManyField('self', symmetrical=False, blank=True,
                                         related_name='blocked_by')
    points = models.IntegerField(default=0)
    qr_code = CloudinaryField('image', blank=True, null=True)

    def __str__(self):
        return f"@{self.username}"

    @property
    def has_blue_badge(self):
        return self.is_verified or self.friends.count() > 10

    def generate_qr_code(self):
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )

        # تأكد من تحديث هذا الرابط ليعكس نطاقك الفعلي
        profile_url = f"https://yourdomain.com/profile/{self.username}"
        qr.add_data(profile_url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format="PNG")

        result = cloudinary.uploader.upload(
            buffer.getvalue(),
            folder="qr_codes",
            public_id=f"user_{self.id}_qr",
            overwrite=True
        )

        self.qr_code = result['secure_url']
        self.save(update_fields=['qr_code']) # Specify fields to avoid recursion if needed

        return self.qr_code

    def save(self, *args, **kwargs):
        # Check if it's a new user and qr_code is not set
        is_new = not self.pk
        super().save(*args, **kwargs) # Save first to get an ID
        if is_new and not self.qr_code:
            self.generate_qr_code()
        # To prevent recursion if generate_qr_code calls save again without update_fields
        elif 'update_fields' not in kwargs and self.pk and not self.qr_code:
              # This case might indicate a user exists but QR code was removed/missing
              # and needs regeneration. Handle carefully based on desired logic.
              pass # Or self.generate_qr_code() if needed, ensuring it won't loop.


class Message(models.Model):
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="sent_messages")
    receiver = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="received_messages")
    content = models.TextField(default="")
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    seen_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"من {self.sender} إلى {self.receiver}: {self.content[:30]}"

    def mark_as_seen(self):
        if not self.is_read:
            self.is_read = True
            self.seen_at = timezone.now()
            self.save()

class Chat(models.Model):
    participants = models.ManyToManyField(CustomUser, related_name='chats')
    created_at = models.DateTimeField(auto_now_add=True)
    last_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Chat {self.id}"

class Post(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField()
    image = CloudinaryField('image', blank=True, null=True)
    video = CloudinaryField('video', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Post by {self.user.username}"

class Like(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')

    def __str__(self):
        return f"{self.user.username} likes {self.post.id}"

class Comment(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}: {self.content[:20]}"

class SavedPost(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='saved_posts')
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')

    def __str__(self):
        return f"{self.user.username} saved {self.post.id}"

class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('message', 'رسالة جديدة'),
        ('like', 'إعجاب'),
        ('comment', 'تعليق'),
        ('friend_request', 'طلب صداقة'),
        ('friend_accept', 'قبول الصداقة'),
    )

    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES)
    content = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    related_id = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_notification_type_display()} لـ {self.recipient.username}"

# Removed Story model and its related imports like 'random' and 'timedelta' if they were exclusive to it.
# Ensure 'User' from get_user_model is still defined if used by other parts, or remove the import:
# from django.contrib.auth import get_user_model
# User = get_user_model() # Remove if Story was the only model using it.
