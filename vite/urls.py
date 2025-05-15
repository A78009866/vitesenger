from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from .views import logout_view
from .views import get_new_messages

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='social/login.html'), name='login'),
    path('post/create/', views.create_post, name='create_post'),
    path('post/<int:post_id>/edit/', views.edit_post, name='edit_post'),
    path('post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    path('post/<int:post_id>/like/', views.like_post, name='like_post'),
    path('post/<int:post_id>/comment/', views.add_comment, name='add_comment'),
    path('profile/<str:username>/', views.profile, name='profile'),
    path('profile/<str:username>/edit/', views.edit_profile, name='edit_profile'),
    path('friends/', views.friends, name='friends'),
    path('friend_request/<str:username>/', views.send_friend_request, name='send_friend_request'),
    path('accept_request/<str:username>/', views.accept_friend_request, name='accept_friend_request'),
    path('reject_request/<str:username>/', views.reject_friend_request, name='reject_friend_request'),
    path('search/', views.search_users, name='search_users'),
    path('block_user/<str:username>/', views.block_user, name='block_user'),
    path('unblock_user/<str:username>/', views.unblock_user, name='unblock_user'),
    path('logout/', logout_view, name='logout_view'),
    path('saved/', views.saved_posts, name='saved_posts'),
    path('messages/update/<int:chat_id>/', views.update_chat, name='update_chat'),
    path('messages/', views.messages_list, name='messages_list'),
    path('messages/<int:chat_id>/', views.chat_detail, name='chat_detail'),
    path('messages/new/<str:username>/', views.new_chat, name='new_chat'),
    path('messages/send/<int:chat_id>/', views.send_message, name='send_message'),
    path('chat/<int:chat_id>/get_new_messages/', get_new_messages, name='get_new_messages'),

]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)