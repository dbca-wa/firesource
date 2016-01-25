# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime
import messaging.models
import django.contrib.gis.db.models.fields
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Layer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_created', messaging.models.AutoCreatedField(default=datetime.datetime.utcnow, editable=False, db_index=True)),
                ('date_modified', messaging.models.AutoLastModifiedField(default=datetime.datetime.utcnow, editable=False, db_index=True)),
                ('effective_from', models.DateTimeField(db_index=True)),
                ('effective_to', models.DateTimeField(db_index=True, null=True, blank=True)),
                ('layer_id', models.CharField(max_length=320)),
                ('name', models.CharField(max_length=320)),
                ('details', messaging.models.JSONField()),
                ('shown', models.BooleanField(default=False)),
                ('immutable', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='Map',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('date_created', messaging.models.AutoCreatedField(default=datetime.datetime.utcnow, editable=False, db_index=True)),
                ('date_modified', messaging.models.AutoLastModifiedField(default=datetime.datetime.utcnow, editable=False, db_index=True)),
                ('effective_from', models.DateTimeField(db_index=True)),
                ('effective_to', models.DateTimeField(db_index=True, null=True, blank=True)),
                ('map_id', models.CharField(max_length=320)),
                ('name', models.CharField(max_length=320)),
                ('layers', messaging.models.JSONField()),
                ('bounds', django.contrib.gis.db.models.fields.PolygonField(srid=4283, null=True, editable=False, blank=True)),
                ('center', django.contrib.gis.db.models.fields.PointField(default='POINT (0 0)', srid=4283, editable=False)),
                ('zoom', models.FloatField(default=0)),
                ('scale', models.IntegerField(default=50000)),
                ('immutable', models.BooleanField(default=True)),
                ('workdir', models.CharField(max_length=320, null=True, blank=True)),
                ('completed_files', messaging.models.JSONField(null=True, blank=True)),
                ('map_type', models.CharField(default='map', max_length=16, choices=[('map', 'map'), ('theme', 'theme')])),
                ('template', models.CharField(max_length=64, null=True, blank=True)),
                ('tags', models.TextField(null=True, blank=True)),
                ('created_by', models.ForeignKey(related_name='spatial_map_created', default=1, to=settings.AUTH_USER_MODEL)),
                ('modified_by', models.ForeignKey(related_name='spatial_map_modified', default=1, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='RasterLayer',
            fields=[
                ('layer_ptr', models.OneToOneField(parent_link=True, auto_created=True, primary_key=True, serialize=False, to='spatial.Layer')),
                ('layer_type', models.CharField(max_length=16, choices=[('point', 'point'), ('line', 'line'), ('polygon', 'polygon'), ('overlay', 'overlay'), ('imagery', 'imagery')])),
                ('layers', models.CharField(max_length=320)),
                ('url', models.CharField(max_length=640)),
                ('transition_effect', models.CharField(default='resize', max_length=16, null=True, choices=[('resize', 'resize'), (None, None)])),
                ('tiled', models.BooleanField(default=True)),
                ('transparent', models.BooleanField(default=True)),
            ],
            options={
                'abstract': False,
            },
            bases=('spatial.layer',),
        ),
        migrations.AddField(
            model_name='layer',
            name='created_by',
            field=models.ForeignKey(related_name='spatial_layer_created', default=1, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='layer',
            name='modified_by',
            field=models.ForeignKey(related_name='spatial_layer_modified', default=1, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(
            name='map',
            unique_together=set([('effective_to', 'map_id'), ('effective_from', 'map_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='layer',
            unique_together=set([('effective_from', 'layer_id'), ('effective_to', 'layer_id')]),
        ),
    ]
