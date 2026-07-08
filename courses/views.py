from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
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
        ctx = super(CourseDetailPage, self).get_context_data(**kwargs)
        course = Course.objects.filter(slug=self.kwargs['slug']).first()
        ctx['title'] = course
        ctx['lessons'] = Lesson.objects.filter(course=course).order_by('number')

        return ctx

class LessonDetailPage(DetailView):
    model = Course
    template_name = 'courses/lesson-detail.html'


    def get_context_data(self, **kwargs):
        ctx = super(LessonDetailPage, self).get_context_data(**kwargs)
        course = Course.objects.filter(slug=self.kwargs['slug']).first()
        lesson = Lesson.objects.filter(slug=self.kwargs['lesson_slug']).first()

        lesson.video = lesson.video.split('=')[1]

        ctx['title'] = lesson
        ctx['lesson'] = lesson

        if lesson:
            ctx['comments']=lesson.comment_set.all().order_by('-id')

        ctx['comment_form'] = CommentForm()

        return ctx

    def post(self, request, *args, **kwargs):
        form = CommentForm(request.POST)
        current_lesson = Lesson.objects.filter(slug=self.kwargs['lesson_slug']).first()

        if form.is_valid() and current_lesson:
            comment = form.save(commit=False)

            comment.user = request.user
            comment.lesson = current_lesson

            comment.save()

            return redirect(current_lesson.get_absolute_url())
        else:
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
