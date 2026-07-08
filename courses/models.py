from django.contrib.auth.models import User
from django.db import models
from django.urls import reverse


class Course(models.Model):
    #slug, title, desc, image
    slug = models.SlugField('Unique name of course',unique=True)
    title = models.CharField('Name of course',max_length=100)
    desc = models.TextField('Description of course')
    image = models.ImageField('Image', default='default.png',upload_to='courses_images')
    is_free = models.BooleanField('Free',default=True)

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse('course-detail', kwargs={'slug':self.slug})

class Lesson(models.Model):
    #slug, title, desc, course, number, video_url
    slug = models.SlugField('Unique name of lesson',unique=True)
    title = models.CharField('Name of lesson',max_length=100)
    desc = models.TextField('Description of lesson')
    course = models.ForeignKey(Course,on_delete=models.CASCADE, verbose_name='which course?')
    number = models.IntegerField('Lesson number')
    video = models.CharField('Video',max_length=100)

    def get_absolute_url(self):
        return reverse('lesson-detail', kwargs={
            'slug': self.course.slug,
            'lesson_slug': self.slug
        })

    def __str__(self):
        return self.title
    #
    # def get_absolute_url(self):
    #     return reverse('lesson-detail', kwargs={'slug':self.course.slug, 'lesson_slug':self.slug})

class Comment(models.Model):
    text = models.TextField('Comment', max_length=200)
    user = models.ForeignKey(User,on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lesson,on_delete=models.CASCADE)
