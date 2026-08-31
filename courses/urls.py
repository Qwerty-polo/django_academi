from django.urls import path
from . import views

urlpatterns = [
    path('', views.HomePageView.as_view(), name='home'),
    path('add-course/', views.AddCourseView.as_view(), name='add-course'),

    path('tariffs/', views.tarrifsPage, name='tarrifs'),

    path('course/<slug>',views.CourseDetailPage.as_view(), name='course-detail'),
    path('course/<slug>/<lesson_slug>', views.LessonDetailPage.as_view(), name='lesson-detail'),

]
