'''
Spatial models::

    Copyright (C) 2009 Department of Environment & Conservation

    Authors:
     * Adon Metcalfe

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

from __future__ import division, print_function, unicode_literals, absolute_import
from datetime import datetime
import re
import os

from django.contrib.gis import geos, admin
from django.contrib.contenttypes.models import ContentType

from messaging.models import models, Audit, AuditManager, JSONField, json

class MapManager(AuditManager):
    '''
    Map manager (unique on map_id)
    '''
    def get_by_natural_key(self, effective_to, map_id):
        return self.get(effective_to = effective_to, map_id = map_id)

    def natural_key_set(self, effective_to, map_id):
        return self.filter(map_id = map_id)

class Map(Audit):
    '''
    layers is a list of {"layer_id": ,"opacity": }
    completed files is a list of file names
    '''
    map_id = models.CharField(max_length=320)
    name = models.CharField(max_length=320)
    layers = JSONField()
    bounds = models.PolygonField(srid = 4283, null=True, blank=True, editable=False)
    center = models.PointField(srid = 4283, default="POINT (0 0)", editable=False)
    zoom = models.FloatField(default=0)
    scale = models.IntegerField(default=50000)
    immutable = models.BooleanField(default=True)
    workdir = models.CharField(max_length=320, null=True, blank=True)
    completed_files = JSONField(null=True, blank=True)
    map_type = models.CharField(
        max_length=16, default="map",
        choices=(("map","map"), ("theme","theme")))
    template = models.CharField(max_length=64, null=True, blank=True)
    tags = models.TextField(null=True, blank=True)

    objects = MapManager()

    def get_outputs(self):
        data = []
        base = self.map_id + "_" + self.workdir.split("/")[-1]
        for filename in self.completed_files:
            fmt = os.path.splitext(filename)[1]
            if fmt != ".svg": data.append((base + fmt, fmt[1:]))
        return data
    outputs = property(get_outputs)

    def get_utc_string(self):
        return self.workdir.split("/")[-1]
    utc_string = property(get_utc_string)

    def get_print_layers(self):
        return filter(lambda layer: layer["layer_id"].find("_symbols_overlay") == -1, self.layers)
    print_layers = property(get_print_layers)

    def get_url(self):
        return "/apps/spatial/map/{0}_{1}".format(self.map_id, self.utc_string)
    url = property(get_url)

    def as_json(self, user=None):
        if user:
            immutable = self.immutable or (user != self.created_by)
        else:
            immutable = self.immutable
        return {
            "name":self.name,
            "layers":self.layers,
            "tags":self.tags,
            "immutable":immutable,
            "type":self.map_type,
            "center":json.loads(self.center.json),
            "scale":self.scale,
            "map_id":self.map_id,
            "url":self.url
        }

    def get_scaletext(self):
        if self.scale > 1000000:
            scale = "{0}M".format(round(self.scale / 1000000, 1))
        elif self.scale > 1000:
            scale = "{0}K".format(round(self.scale / 1000, 1))
        else:
            scale = self.scale
        return scale
    scaletext = property(get_scaletext)

    def natural_key(self):
        return [self.effective_to, self.map_id]

    class Meta:
        unique_together = (("effective_from", "map_id"),
            ("effective_to", "map_id"))

class MapAdmin(admin.GeoModelAdmin):
    search_fields = ['map_id', 'layers', 'name', 'template']
    list_display = ('map_id', 'name', 'created_by', 'template')

admin.site.register(Map, MapAdmin)


class LayerManager(AuditManager):
    '''
    Layer manager (unique on layer_id)
    '''
    def get_by_natural_key(self, effective_to, layer_id):
        return self.get(effective_to = effective_to, layer_id = layer_id)

    def natural_key_set(self, effective_to, layer_id):
        return self.filter(layer_id = layer_id)

class Layer(Audit):
    layer_id = models.CharField(max_length=320)
    name = models.CharField(max_length=320)
    legend = models.CharField(max_length=320, default="https://static.dpaw.wa.gov.au/static/firesource/static/source/legends/blank.png")
    details = JSONField()
    shown = models.BooleanField(default=False)
    immutable = models.BooleanField(default=True)

    objects = LayerManager()

    def get_layer_index(self):
        return '/apps/spatial/layer/{0}"'.format(self.layer_id)
    layer_index = property(get_layer_index)

    COLUMNS = ["name", "created_by", "modified_by", "effective_from"]
    def as_td(self):
        td_string = ""
        for column in self.COLUMNS:
            if column == "name":
                td_string += '<td><a href="{0}">{1}</a></td>'.format(self.layer_index, self.name)
            else:
                try:
                    td_string += "<td>{0}</td>".format(getattr(self, column))
                except Exception, e:
                    td_string += "<td>{0}</td>".format(e)
        return td_string

    def get_tags(self):
        if isinstance(self.details, dict) and self.details.has_key("tags"):
            tags = ', '.join(self.details["tags"])
        else:
            tags = ', '.join(self.layer_id.split('_'))
        if self.immutable:
            tags += ", default"
        return tags
    metadata_tags = property(get_tags)

    def get_type(self):
        try:
            return self.rasterlayer.layer_type
        except:
            return "point"
    metadata_type = property(get_type)

    def natural_key(self):
        return [self.effective_to, self.layer_id]

    class Meta:
        unique_together = (("effective_from", "layer_id"),
            ("effective_to", "layer_id"))

class RasterLayer(Layer):
    layer_type = models.CharField(
        max_length=16,
        choices=(
            ("point","point"),
            ("line","line"),
            ("polygon","polygon"),
            ("overlay","overlay"),
            ("imagery","imagery")))
    layers = models.CharField(max_length=320)
    url = models.CharField(max_length=640)
    transition_effect = models.CharField(
        max_length=16, null=True, default="resize",
        choices=(("resize","resize"), (None,None)))
    tiled = models.BooleanField(default=True)
    transparent = models.BooleanField(default=True)

    def get_info(self):
        return self.url + ' , ' + self.layers[:64]
    info = property(get_info)

    def as_json(self):
        return {
            "id": self.layer_id,
            "name": self.name,
            "details": self.details,
            "tags": self.metadata_tags,
            "type": self.layer_type,
            "url": self.url,
            "legend": self.legend,
            "layers": self.layers,
            "transition_effect": self.transition_effect,
            "tiled": self.tiled,
            "transparent": self.transparent,
            "shown": self.shown,
            "immutable": self.immutable
        }

    objects = LayerManager()

class RasterLayerAdmin(admin.ModelAdmin):
    search_fields = ['layer_id', 'name', 'url', 'layers', 'details']
    list_filter = ('layer_type', 'tiled', 'transparent', 'transition_effect', 'effective_from', 'effective_to')
    list_display = ('name', 'layer_type', 'tiled', 'transparent', 'transition_effect', 'info')
    list_editable = ('layer_type', 'tiled', 'transparent', 'transition_effect')

admin.site.register(RasterLayer, RasterLayerAdmin)
