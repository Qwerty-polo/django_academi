from io import BytesIO
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def isolate_cache_and_media(settings, tmp_path):
    # Tests must not share throttle counters or write to real uploaded media.
    settings.MEDIA_ROOT = tmp_path / 'media'
    settings.MEDIA_ROOT.mkdir()
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def course_data():
    def make():
        stream = BytesIO()
        Image.new('RGB', (2, 2)).save(stream, format='PNG')
        return {'slug': 'created', 'title': 'Created', 'desc': 'Description',
                'image': SimpleUploadedFile('course.png', stream.getvalue(), content_type='image/png')}
    return make

