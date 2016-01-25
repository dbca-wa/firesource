# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spatial', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='layer',
            name='legend',
            field=models.CharField(max_length=320, null=True, blank=True),
        ),
    ]
