from django.urls import path, include
from . import views

app_name = 'authentication'

urlpatterns = [
    # Authentication modal views
    path('modal/', views.AuthModalView.as_view(), name='auth_modal'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('register/', views.RegisterView.as_view(), name='register'),
    path('guest/', views.GuestLoginView.as_view(), name='guest_login'),
    path('logout/', views.LogoutView.as_view(), name='logout'),
    
    # Profile management
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('convert-account/', views.ConvertGuestView.as_view(), name='convert_guest'),
]