from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from DjangoStore import settings


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('courses.urls')),

    path('user/', include('users.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)