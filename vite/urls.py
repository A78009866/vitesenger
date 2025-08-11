from django.urls import path
from . import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from .views import logout_view

urlpatterns = [
    path('', views.chat_list, name='home'),
    path('register/', views.register, name='register'),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path("chat/<str:username>/", views.chat_view, name="chat"),
    path("send-message/", views.send_message, name="send_message"),
    path("chat/<str:username>/get-messages/", views.get_messages, name="get_messages"),
    path('chat/list/<str:username>/', views.chat_list, name='chat_list'),
    ]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)