# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('spatial', '0002_layer_legend'),
    ]

    operations = [
        migrations.AlterField(
            model_name='layer',
            name='legend',
            field=models.CharField(default='//static.dpaw.wa.gov.au/static/firesource/static/source/legends/toy_story_3_rex_1600x1200.jpg', max_length=320),
        ),
    ]
