import os
import re

nav_files = [
    'templates/includes/navbar_client.html',
    'templates/includes/navbar_lawyer.html',
    'templates/includes/navbar_admin.html',
]

for file_path in nav_files:
    if not os.path.exists(file_path):
        continue
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Strip out the Django block for notifications
    content = re.sub(r'\{% if notifications %\}.*?\{% endif %\}', '<!-- Notifications will load here via JS -->', content, flags=re.DOTALL)
    
    # Clean up single variables
    content = re.sub(r'\{\{.*?timesince.*?\}\}', '', content)
    content = re.sub(r'\{% if unread_notifications_count.*?%\}', '', content)
    content = re.sub(r'\{\{ unread_notifications_count \}\}', '0', content)
    content = re.sub(r'\{% endif %\}', '', content)
    
    # User Profile Names
    content = re.sub(r'\{\{ user\.first_name \}\}', '<span class="auth-user-name">Profile</span>', content)
    content = re.sub(r'\{\{ user\.get_full_name.*?\s*\}\}', '<span class="auth-user-name">Profile</span>', content)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

print("Done stripping Django tags from navbars")
