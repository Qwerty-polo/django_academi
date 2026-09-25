from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST
from .forms import UserRegisterForm, ProfileImageForm, UserUpdateForm
from django.contrib import messages
from django.contrib.auth import logout

from DjangoStore.rate_limits import ratelimit

@ratelimit(key='ip', rate='2/s', method='POST')
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'user {username} was created')
            return redirect('home')
    else:
        form = UserRegisterForm()

    return render(request,
                  'users/registration.html',
                  {
                      'title': 'Сторінка реєстрації',
                      'form': form,
                   })

@require_POST
def custom_logout(request):
  logout(request)
  # Повідомлення тепер не потрібне, бо вся інформація буде на самій сторінці
  return render(request, 'users/exit.html')

@login_required
def profile(request):
    if request.method == 'POST':
        profileForm = ProfileImageForm(request.POST, request.FILES,instance=request.user.profile)
        updateUserForm = UserUpdateForm(request.POST, instance=request.user)

        if profileForm.is_valid() and updateUserForm.is_valid():
            profileForm.save()
            updateUserForm.save()
            messages.success(request, f'your profile was updated')
            return redirect('profile')

    else:
        profileForm = ProfileImageForm(instance=request.user.profile)
        updateUserForm = UserUpdateForm(instance=request.user)


    data = {
        'profileForm': profileForm,
        'updateUserForm': updateUserForm
    }

    return render(request, 'users/profile.html', data)