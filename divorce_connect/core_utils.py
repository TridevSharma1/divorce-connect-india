from django.core.exceptions import ValidationError
from PIL import Image
import os


def validate_profile_picture(image_file):
    """
    Validate profile picture upload:
    - Max file size: 5MB
    - Allowed formats: JPG, PNG
    - Min dimensions: 200x200px
    """
    if not image_file:
        return

    file_size = image_file.size
    max_file_size = 5 * 1024 * 1024

    if file_size > max_file_size:
        raise ValidationError(f'Image file size must not exceed 5MB. Current size: {file_size / (1024*1024):.2f}MB')

    file_ext = os.path.splitext(image_file.name)[1].lower()
    allowed_extensions = ['.jpg', '.jpeg', '.png']

    if file_ext not in allowed_extensions:
        raise ValidationError('Only JPG and PNG formats are allowed.')

    try:
        img = Image.open(image_file)
        img.verify()
        image_file.seek(0)

        width, height = img.size
        if width < 200 or height < 200:
            raise ValidationError('Image dimensions must be at least 200x200 pixels.')

    except Exception as e:
        raise ValidationError(f'Invalid image file: {str(e)}')
