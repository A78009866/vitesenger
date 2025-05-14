from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.timezone import now
from cloudinary.models import CloudinaryField
from django.utils import timezone

class User(AbstractUser):
    # إضافة حقول جديدة لملف المستخدم
    full_name = models.CharField(max_length=100, blank=True)
    profile_picture = CloudinaryField('image', blank=True, null=True, default='profile_pics/default_profile.png')
    bio = models.TextField(blank=True)
    friends = models.ManyToManyField('self', symmetrical=False, blank=True)
    friend_requests = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='received_friend_requests')
    blocked_users = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='blocked_by')  # إضافة جديدة
    def __str__(self):
        return f"@{self.username}"


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_messages")
    content = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    seen_at = models.DateTimeField(null=True, blank=True)  # إضافة هذا الحقل الجديد
    
    def __str__(self):
        return f"من {self.sender} إلى {self.receiver}: {self.content[:30]}"
    
    def mark_as_seen(self):
        if not self.is_read:
            self.is_read = True
            self.seen_at = timezone.now()
            self.save()

class Chat(models.Model):
    participants = models.ManyToManyField(User, related_name='chats')  # related_name='chats'
    created_at = models.DateTimeField(auto_now_add=True)
    last_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Chat {self.id}"

class Post(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
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
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')

    def __str__(self):
        return f"{self.user.username} likes {self.post.id}"

class Comment(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username}: {self.content[:20]}"

class SavedPost(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_posts')
    post = models.ForeignKey(Post, on_delete=models.CASCADE)
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'post')

    def __str__(self):
        return f"{self.user.username} saved {self.post.id}"