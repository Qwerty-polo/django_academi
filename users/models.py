from django.db import models
from django.contrib.auth.models import User
from PIL import Image

TYPE_ACCOUNT = (
    ('full', 'full mode'),
    ('free', 'free mode'),
)

GENDER_CHOICES = (
    ('male', 'Man'),
    ('female', 'Woman'),
)


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    img = models.ImageField('User Photo', default='default.png', upload_to='user_images')
    account_type = models.CharField('Account Type', choices=TYPE_ACCOUNT, max_length=30, default='free')
    gender = models.CharField('Sex', max_length=10, choices=GENDER_CHOICES, blank=True)
    email_consent = models.BooleanField('Agree to receive emails', default=True)

    is_author = models.BooleanField('Can create courses', default=False)

    class Meta:
        verbose_name = 'Профіль'
        verbose_name_plural = 'Профілі'

    def __str__(self):
        return f'Профіль користувача {self.user.username}'

    @property
    def is_vip(self):
        return self.account_type == 'full'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)


        try:
            image = Image.open(self.img.path)
            if image.height > 256 or image.width > 256:
                resize = (256, 256)
                image.thumbnail(resize)
                image.save(self.img.path)
        except Exception:
            pass