from django.db import migrations

def fix_duplicates(apps, schema_editor):
    CustomUser = apps.get_model('myapp', 'CustomUser')
    
    # For each duplicate email, keep the first user and modify others
    from collections import Counter
    emails = CustomUser.objects.values_list('email', flat=True)
    duplicate_emails = [email for email, count in Counter(emails).items() if count > 1]
    
    for email in duplicate_emails:
        users = CustomUser.objects.filter(email=email).order_by('id')
        keeper = users.first()
        for i, duplicate in enumerate(users[1:], 1):
            duplicate.email = f"{email.split('@')[0]}+dup{i}@{email.split('@')[1]}"
            duplicate.save()

class Migration(migrations.Migration):
    dependencies = [
        ('myapp', '0020_remove_customuser_name_alter_customuser_username'),
    ]

    operations = [
        migrations.RunPython(fix_duplicates),
    ]