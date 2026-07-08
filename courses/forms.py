from django import forms
from .models import Course, Comment


class AddCourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['slug', 'title', 'desc','image']

        widgets = {
            'slug': forms.TextInput(attrs={
                'placeholder': 'URL (Example, android-basics)'
            }),
            'title': forms.TextInput(attrs={
                'placeholder': 'Name...'
            }),
            'desc': forms.Textarea(attrs={
                'placeholder': 'Description...'
            }),
            'image': forms.FileInput(),
        }
        labels = {
            'slug': 'Name of  URL:',
            'title': 'Name of course:',
            'description': 'Description of course:',
            'image': 'Image of course:',
        }
        help_texts = {
            'slug': 'Do not type: % # _',
        }

class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['text'] #'user', 'lesson']
        widgets = {
            'text': forms.Textarea(attrs={'placeholder': 'Type your comment...'}),
            'class': 'form-control',
            'rows': 3,
            # 'user': forms.HiddenInput(),
            # 'lesson': forms.HiddenInput(),
        }







