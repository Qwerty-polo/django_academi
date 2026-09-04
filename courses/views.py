from datetime import timedelta
from django.utils import timezone

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import TemplateView, ListView, DetailView, CreateView
from django.core.paginator import Paginator

from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from .forms import AddCourseForm, CommentForm
from .models import Course, Lesson, Comment
from django.core.cache import cache

from .tasks import send_new_course_email

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

    def get_queryset(self):
        return super().get_queryset().select_related('author')

class CourseDetailPage(DetailView):
    model = Course
    template_name = 'courses/course-detail.html'


    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        course = self.object
        # 1. Формуємо унікальний ключ для конкретного курсу (наприклад: 'course_views_5')
        redis_key = f'course_views_{course.id}'

        # 2. Дістаємо поточну цифру. Якщо курсу в Redis ще немає, беремо 0
        views = cache.get(redis_key, 0)

        # 3. Додаємо +1 перегляд
        views += 1

        # 4. Зберігаємо оновлену цифру назад у пам'ять (timeout=None означає зберігати вічно)
        cache.set(redis_key, views, timeout=None)

        # 5. Передаємо цифру в шаблон
        ctx['views_count'] = views
        # -----------------------

        ctx['title'] = course.title
        ctx['lessons'] = course.lessons.all()
        return ctx

@method_decorator(ratelimit(key='ip', rate='2/s', method='POST', block=True), name='dispatch')
class LessonDetailPage(DetailView):
    model = Lesson
    template_name = 'courses/lesson-detail.html'

    def get_object(self, queryset=None):
        return get_object_or_404(
            Lesson,
            course__slug=self.kwargs['slug'],
            slug=self.kwargs['lesson_slug']
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        lesson = self.object

        # 1. YouTube video code
        video_code = lesson.video
        if '=' in video_code:
            video_code = video_code.split('=')[-1]
        elif '/' in video_code:
            video_code = video_code.split('/')[-1]
        ctx['video_code'] = video_code

        # 2. Перевірка доступу
        has_access = False
        if lesson.course.is_free:
            has_access = True
        elif self.request.user.is_authenticated and hasattr(self.request.user, 'profile') and self.request.user.profile.is_vip:
            has_access = True
        ctx['has_access'] = has_access

        # 3. Пагінація коментарів
        all_comments = lesson.comments.select_related('user').all()
        paginator = Paginator(all_comments, 3)
        page_number = self.request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        ctx['comments'] = page_obj
        ctx['page_obj'] = page_obj

        # 4. Форма коментарів
        if 'comment_form' not in ctx:
            ctx['comment_form'] = CommentForm()

        return ctx

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()

        if not request.user.is_authenticated:
            return redirect('user')

        lesson = self.object

        # --- АНТИСПАМ: перевіряємо останній коментар користувача за останні 60 секунд ---
        one_minute_ago = timezone.now() - timedelta(seconds=60)
        recent_comment = Comment.objects.filter(
            user=request.user,
            created_at__gte=one_minute_ago
        ).first()

        if recent_comment:
            messages.error(request, 'You send too much comments. Wait 1 minute.')
            return redirect(lesson.get_absolute_url())

        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.user = request.user
            comment.lesson = lesson
            comment.save()
            return redirect(lesson.get_absolute_url())

        context = self.get_context_data(comment_form=form)
        return self.render_to_response(context)


class AddCourseView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Course
    form_class = AddCourseForm
    template_name = 'courses/add-course.html'
    success_url = reverse_lazy('home')

    # ДОДАЄМО перевірку доступу
    def test_func(self):
        # Дозволяємо, якщо юзер має галочку is_author АБО якщо це головний адмін (superuser)
        return self.request.user.profile.is_author or self.request.user.is_superuser

    def handle_no_permission(self):
        messages.error(self.request, 'У вас немає прав для створення курсу.')
        return redirect('home')

    # Цей метод залишаємо, він прив'яже цього адміна як автора курсу
    def form_valid(self, form):
        form.instance.author = self.request.user
        # Викликаємо фонову задачу! Відправляємо назву курсу.
        # Метод .delay() миттєво відправляє таску в Redis і код йде далі
        send_new_course_email.delay(form.instance.title)

        return super().form_valid(form)

