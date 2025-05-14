from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from .views import logout_view

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='social/login.html'), name='login'),
    path('post/create/', views.create_post, name='create_post'),
    path('post/<int:post_id>/like/', views.like_post, name='like_post'),
    path('post/<int:post_id>/comment/', views.add_comment, name='add_comment'),
    path('post/<int:post_id>/save/', views.save_post, name='save_post'),
    path('profile/<str:username>/', views.profile, name='profile'),
    path('friends/', views.friends, name='friends'),
    path('friend_request/<str:username>/', views.send_friend_request, name='send_friend_request'),
    path('accept_request/<str:username>/', views.accept_friend_request, name='accept_friend_request'),
    path('reject_request/<str:username>/', views.reject_friend_request, name='reject_friend_request'),
    path('search/', views.search_users, name='search_users'),
    path('block_user/<str:username>/', views.block_user, name='block_user'),
    path('unblock_user/<str:username>/', views.unblock_user, name='unblock_user'),
    path('logout/', logout_view, name='logout_view'),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)