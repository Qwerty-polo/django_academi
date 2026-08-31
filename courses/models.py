from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField('Created at', auto_now_add=True)
    updated_at = models.DateTimeField('Updated at', auto_now=True)

    class Meta:
        abstract = True # ВАЖЛИВО: Django не створюватиме окрему таблицю для цього класу

class Course(TimeStampedModel):
    slug = models.SlugField('Unique name of course', unique=True)
    title = models.CharField('Name of course', max_length=100)
    desc = models.TextField('Description of course')
    image = models.ImageField('Image', default='default.png', upload_to='courses_images')
    is_free = models.BooleanField('Free', default=True)

    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='courses',
                               verbose_name='Author')

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('course-detail', kwargs={'slug': self.slug})


class Lesson(TimeStampedModel):
    slug = models.SlugField('Slug of lesson')
    title = models.CharField('Name of lesson', max_length=100)
    desc = models.TextField('Description of lesson')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name='Which course?', related_name='lessons')
    number = models.IntegerField('Lesson number')
    video = models.URLField('Video URL', max_length=200)

    class Meta:
        ordering = ['number']
        constraints = [
            models.UniqueConstraint(fields=['course', 'slug'], name='unique_lesson_per_course')
        ]

    def __str__(self):
        return f"{self.course.title} - {self.title}"

    def get_absolute_url(self):
        return reverse('lesson-detail', kwargs={
            'slug': self.course.slug,
            'lesson_slug': self.slug
        })


class Comment(TimeStampedModel):
    text = models.TextField('Comment', max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='comments')

    class Meta:
        ordering = ['-created_at']  

    def __str__(self):
        return f"Comment by {self.user.username} on {self.lesson.title}"