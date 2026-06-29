import os
import re

root_dir = r'd:/Software Setup/C/Django_Projects/PROJECT99/divorce-connect-india/divorce_connect'

def convert_syntax(content):
    # Remove {% load static %} and {% load something %}
    content = re.sub(r'{%\s*load\s+.*?%}', '', content)
    
    # Replace {% static 'path' %} with {{ url_for('static', path='path') }}
    content = re.sub(r'{%\s*static\s+[\'"](.*?)[\'"]\s*%}', r"{{ url_for('static', path='\1') }}", content)
    
    # Replace {% url 'name' arg1 ... %} with /name/
    content = re.sub(r'{%\s*url\s+[\'"](.*?)[\'"].*?%}', r"/\1/", content)
    
    # Replace {% csrf_token %} with nothing or a hidden input placeholder
    content = re.sub(r'{%\s*csrf_token\s*%}', '<input type="hidden" name="csrf_token" value="fastapi_mock_csrf">', content)
    
    # Replace {% block name %} with {% block name %} (Already compatible)
    # Replace {% extends 'name' %} with {% extends 'name' %} (Already compatible)
    # Replace {% if x %} with {% if x %} (Already compatible)
    # Replace {% for x in y %} with {% for x in y %} (Already compatible)
    
    return content

for root, dirs, files in os.walk(root_dir):
    if 'venv' in root or 'fastapi_app' in root:
        continue
    for file in files:
        if file.endswith('.html'):
            filepath = os.path.join(root, file)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                new_content = convert_syntax(content)
                
                if new_content != content:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    print(f"Updated: {filepath}")
            except Exception as e:
                print(f"Error processing {filepath}: {e}")
