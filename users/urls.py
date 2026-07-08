from django.contrib.auth.views import PasswordResetConfirmView
from django.urls import path
from . import views as userViews
from django.contrib.auth import views as authViews


urlpatterns = [
    path('reg/',userViews.register, name= 'reg'),
    path('profile/',userViews.profile, name= 'profile'),
    path('', authViews.LoginView.as_view(template_name='users/user.html'), name = 'user'),
    path('exit/', userViews.custom_logout, name='exit'),
    path('pass-reset/', authViews.PasswordResetView.as_view(template_name='users/pass_reset.html'), name='pass-reset'),
    path('password-reset_confirm/<uidb64>/<token>/', PasswordResetConfirmView.as_view(template_name='users/password_reset_confirm.html'), name='password_reset_confirm'),
    path('password-reset_done/',
         authViews.PasswordResetDoneView.as_view(template_name='users/password_reset_done.html'),
         name='password_reset_done'),
path('password-reset_complete/',
         authViews.PasswordResetCompleteView.as_view(template_name='users/password_reset_complete.html'),
         name='password_reset_complete'),


]


