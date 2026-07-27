from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.template.defaulttags import comment
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, DetailView, CreateView

from .forms import AddCourseForm, CommentForm
from .models import Course, Lesson, Comment


def tarrifsPage(request):
    return render(request, 'courses/tarrifs.html', {'title': 'Price is here'})
class HomePageView(ListView):
    model = Course
    template_name = 'courses/home.html'
    context_object_name = 'courses'
    ordering = ['-id']

    def get_context_data(self, **kwargs):
        ctx = super(HomePageView, self).get_context_data(**kwargs)
        ctx['title'] = 'Home Page'
        return ctx

class CourseDetailPage(DetailView):
    model = Course
    template_name = 'courses/course-detail.html'


    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        course = get_object_or_404(Course, slug=self.kwargs['slug'])
        ctx['title'] = course.title
        ctx['lessons'] = course.lesson_set.all()
        return ctx

class LessonDetailPage(DetailView):
    model = Lesson
    template_name = 'courses/lesson-detail.html'

    def get_object(self, queryset=None):
        # Отримуємо конкретний урок за слагом курсу та слагом уроку
        return get_object_or_404(
            Lesson,
            course__slug=self.kwargs['slug'],
            slug=self.kwargs['lesson_slug']
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        lesson = self.get_object()

        # Безпечне витягування ID відео для YouTube
        video_code = lesson.video
        if '=' in video_code:
            video_code = video_code.split('=')[-1]
        elif '/' in video_code:
            video_code = video_code.split('/')[-1]

        ctx['title'] = lesson.title
        ctx['lesson'] = lesson
        ctx['video_code'] = video_code
        # Коментарі вже відсортовані за датою завдяки class Meta у Comment
        ctx['comments'] = lesson.comment_set.all()
        ctx['comment_form'] = CommentForm()
        return ctx

    def post(self, request, *args, **kwargs):
        # Якщо користувач не увійшов в акаунт — не дозволяємо коментувати
        if not request.user.is_authenticated:
            return redirect('login')

        lesson = self.get_object()
        form = CommentForm(request.POST)

        if form.is_valid():
            comment = form.save(commit=False)
            comment.user = request.user
            comment.lesson = lesson
            comment.save()
            return redirect(lesson.get_absolute_url())

        context = self.get_context_data(**kwargs)
        context['comment_form'] = form
        return self.render_to_response(context)





class AddCourseView(LoginRequiredMixin,CreateView):
    model = Course
    form_class = AddCourseForm
    template_name = 'courses/add-course.html'
    success_url = reverse_lazy('home')

# class LessonDetailPage(DetailView):
#     model = Lesson
#     template_name = 'courses/lesson-detail.html'
#
#     def get_context_data(self, **kwargs):
