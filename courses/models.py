from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse


class Course(models.Model):
    slug = models.SlugField('Unique name of course', unique=True)
    title = models.CharField('Name of course', max_length=100)
    desc = models.TextField('Description of course')
    image = models.ImageField('Image', default='default.png', upload_to='courses_images')
    is_free = models.BooleanField('Free', default=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('course-detail', kwargs={'slug': self.slug})


class Lesson(models.Model):
    slug = models.SlugField('Slug of lesson')
    title = models.CharField('Name of lesson', max_length=100)
    desc = models.TextField('Description of lesson')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, verbose_name='Which course?')
    number = models.IntegerField('Lesson number')
    video = models.URLField('Video URL', max_length=200)

    class Meta:
        ordering = ['number']
        unique_together = ('course', 'slug')

    def __str__(self):
        return f"{self.course.title} - {self.title}"

    def get_absolute_url(self):
        return reverse('lesson-detail', kwargs={
            'slug': self.course.slug,
            'lesson_slug': self.slug
        })


class Comment(models.Model):
    text = models.TextField('Comment', max_length=200)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE)
    created_at = models.DateTimeField('Created at', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']  

    def __str__(self):
        return f"Comment by {self.user.username} on {self.lesson.title}"