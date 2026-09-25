from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
from django.db import transaction
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView
from django.core.paginator import Paginator

from django.utils.decorators import method_decorator
from DjangoStore.rate_limits import ratelimit, increment_counter, CACHE_ERRORS

from .forms import AddCourseForm, CommentForm
from .models import Course, Lesson, Comment

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
        try:
            ctx['views_count'] = increment_counter(f'course_views_{course.pk}', timeout=None)
        except CACHE_ERRORS:
            ctx['views_count'] = None
        ctx['has_access'] = course.can_access(self.request.user)
        ctx['title'] = course.title
        ctx['lessons'] = course.lessons.order_by('number', 'pk') if ctx['has_access'] else course.lessons.none()
        return ctx

@method_decorator(ratelimit(key='user_or_ip', rate='2/s', method='POST'), name='dispatch')
class LessonDetailPage(DetailView):
    model = Lesson
    template_name = 'courses/lesson-detail.html'

    def get_object(self, queryset=None):
        return get_object_or_404(
            Lesson.objects.select_related('course'),
            course__slug=self.kwargs['slug'],
            slug=self.kwargs['lesson_slug']
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        lesson = self.object

        # 1. YouTube video code
        parsed_video = urlsplit(lesson.video)
        video_code = parse_qs(parsed_video.query).get('v', [None])[0]
        ctx['video_code'] = video_code or parsed_video.path.rstrip('/').rsplit('/', 1)[-1]

        has_access = lesson.course.can_access(self.request.user)
        ctx['has_access'] = has_access
        all_comments = lesson.comments.select_related('user').order_by('-created_at', '-pk') if has_access else lesson.comments.none()
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

        if not lesson.course.can_access(request.user):
            raise PermissionDenied('You do not have access to this lesson.')

        form = CommentForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # PostgreSQL serializes submissions for this user across lessons.
                # SQLite development mode has no row-level locks.
                User.objects.select_for_update().get(pk=request.user.pk)
                recent_comment = Comment.objects.filter(
                    user=request.user,
                    created_at__gte=timezone.now() - timedelta(seconds=60),
                ).exists()
                if recent_comment:
                    messages.error(request, 'You send too much comments. Wait 1 minute.')
                    return redirect(lesson.get_absolute_url())
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
        return self.request.user.is_superuser or getattr(getattr(self.request.user, 'profile', None), 'is_author', False)

    def handle_no_permission(self):
        messages.error(self.request, 'У вас немає прав для створення курсу.')
        return redirect('home')

    # Цей метод залишаємо, він прив'яже цього адміна як автора курсу
    def form_valid(self, form):
        form.instance.author = self.request.user
        with transaction.atomic():
            response = super().form_valid(form)
            transaction.on_commit(
                lambda title=self.object.title: send_new_course_email.delay(title), robust=True
            )
        return response
