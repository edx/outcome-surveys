# Generated by Django 3.2.22 on 2023-10-31 16:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('outcome_surveys', '0005_auto_20230220_0433'),
    ]

    operations = [
        migrations.AlterField(
            model_name='learnercourseevent',
            name='event_type',
            field=models.CharField(choices=[('edx.course.learner.passed.first_time', 'edx.course.learner.passed.first_time'), ('edx.course.learner.achieved.learning.time.achieved', 'edx.course.learner.achieved.learning.time.achieved')], default='edx.course.learner.passed.first_time', max_length=255),
        ),
    ]
