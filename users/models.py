from django.db import models
from django.contrib.auth.models import User
from PIL import Image
TYPE_ACCOUNT = (
    ('full','full mode'),
    ('free', 'free mode'),

)

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    img = models.ImageField('user photo', default = 'default.png', upload_to='user_images')
    account_type = models.CharField(choices=TYPE_ACCOUNT, max_length=30, default='free')

    GENDER_CHOICES = (
        ('male', 'man'),
        ('female', 'women'),
    )
    gender = models.CharField('sex', max_length=10, choices=GENDER_CHOICES, blank=True)
    email_consent = models.BooleanField('agree on get an email',default=True)


    def __str__(self):
        return f'Профайл юзера {self.user.username}'

    def save(self, *args, **kwargs):
        super().save()

        image = Image.open(self.img.path)

        if image.height > 256 or image.width > 256:
            resize = (256, 256)
            image.thumbnail(resize)
            image.save(self.img.path)

    class Meta:
        verbose_name='Профайл'
        verbose_name_plural = 'Профайли'
