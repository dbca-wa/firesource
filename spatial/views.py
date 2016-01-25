'''
Spatial output views. Try to keep all of the attributes returned inside
the model being queried for performance.::

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

import os
import json
import requests
import tempfile
import subprocess
import time
import calendar
import shutil
from datetime import datetime

from geopy import distance

from django import http
from django.core.cache import cache
from django.conf import settings
from django.shortcuts import render_to_response
from django.contrib.auth.decorators import login_required

from messaging.models import JSONEncoder
from spatial.models import Map, Layer, RasterLayer
from spatial.remote_devices import remote_devices, remote_history
from spatial.utils import logger_setup

GDAL_TRANSLATE = os.path.join(settings.GDAL_APPS, "gdal_translate")

def context(request):
    return {"site_name": "Spatial Support System",
            "errors": [],
            "messages": [],
            "user": request.user}

# sizes in mm: x, y
document_sizes = {
    "inkscape_a3_portrait": (272, 352),
    "inkscape_a3_landscape": (391, 232)
}


@login_required
def standardmap(request):
    getparams = json.dumps(request.GET, cls=JSONEncoder)
    orderedloc = os.path.join(settings.STATIC_ROOT, "layerorder.json")
    orderedstuff = json.loads(open(orderedloc).read())
    try:
        viewfilters = orderedstuff["views"]
        trackingfilters = orderedstuff["tracking"]
        layerfilters = orderedstuff["layerfilters"]
    except (TypeError, KeyError):
        pass
    return render_to_response('spatial/map.html', locals())


def json_to_shp(jsondata, shapefilename, srs="EPSG:4283"):
    tempjson = tempfile.NamedTemporaryFile(suffix=".json")
    tempjson.file.write(jsondata)
    tempjson.file.flush()
    workdir = tempfile.mkdtemp()
    cwd = os.getcwd()
    os.chdir(workdir)
    subprocess.call('ogr2ogr -a_srs "{2}" -f "ESRI Shapefile" {0}.shp {1}'.format(shapefilename, tempjson.name, srs), shell=True)
    subprocess.call('zip {0}.zip {0}.shp {0}.shx {0}.dbf {0}.prj'.format(shapefilename), shell=True)
    shapedata = open(shapefilename + ".zip").read()
    tempjson.file.close()
    os.chdir(cwd)
    subprocess.call('rm -r ' + workdir, shell=True)
    return shapedata


def get_layer(layerid):
    layer = RasterLayer.objects.get(effective_to=None, layer_id=layerid)
    return layer


@login_required
def map_list(request, fmt="html"):
    cntxt = context(request)
    spatialmaps = Map.objects.filter(created_by=1)
    if fmt == "html":
        user = request.user
        cntxt.update(locals())
        return render_to_response("spatial/map_list.html", cntxt)
    spatialmaps = spatialmaps.filter(effective_to=None).order_by("created_by", "name")
    jsonmaps = []
    for m in spatialmaps:
        jsonmaps.append(m.as_json(user=request.user))
    if fmt == "json":
        return http.HttpResponse(json.dumps(jsonmaps, cls=JSONEncoder), "application/json")
    if fmt == "dict":
        return jsonmaps


@login_required
def layer_list(request, fmt="json", asobject=False):
    '''
    create layer dictionaries for openlayers
    WMS one should contain the code to create the layer itself
    vector one should contain the code and url to retrieve features via geojson/wfs and sld file reference
    '''
    cachekey = "layercache01" + fmt
    if not settings.DEBUG and isinstance(cache.get(cachekey), dict):
        response = http.HttpResponse(**cache.get(cachekey))
        response["Cache-Control"] = "max-age=600, public"
        return response
    orderedloc = os.path.join(settings.STATIC_ROOT, "layerorder.json")
    try:
        orderedlayers = json.loads(open(orderedloc).read())["layers"]
    except:
        # so we know to use old layer ordering methods later
        retro = True
    else:
        retro = False
    cntxt = context(request)
    layers = []
    if retro:
        # Vector layers outside of editable rasters should be deprecated soon
        if asobject:
            # return the list of layers as a python object if asobject (for layer organisation)
            for layer_type in ["point", "line", "polygon", "overlay", "imagery"]: #nice ordering
                layers += list(RasterLayer.objects.filter(effective_to=None, modified_by=1, layer_type=layer_type).order_by("name"))
        else:
            # don't add users layers if returning objects, just list system order
            for layer_type in ["point", "line", "polygon", "overlay", "imagery"]: #nice ordering
                layers += list(RasterLayer.objects.filter(effective_to=None, created_by=request.user, layer_type=layer_type).order_by("-date_created").exclude(layer_id__contains=request.user.username + "_resource_tracking"))
            for layer_type in ["point", "line", "polygon", "overlay", "imagery"]: #nice ordering
                layers += list(RasterLayer.objects.filter(effective_to=None, modified_by=1, layer_type=layer_type).exclude(created_by=request.user).order_by("name"))
    else:
        dictlayers = {"point": [], "line": [], "polygon": [], "overlay": [], "imagery": []}
        for lyr in orderedlayers:
        # ordered layers from file
            layer = False
            try:
                layer = RasterLayer.objects.get(layer_id=lyr, effective_to = None)
            except:
                pass
            if layer:
                dictlayers[layer.metadata_type].append(layer)
        for layer_type in ["point", "line", "polygon", "overlay", "imagery"]: #nice ordering
            layers += dictlayers[layer_type]
            layers += list(RasterLayer.objects.filter(effective_to = None, modified_by = 1, layer_type = layer_type).exclude(layer_id__in = orderedlayers).order_by("name"))
    if asobject:
        return layers
    trackingLayers = [{
                "tags": "resource, tracking, week, symbols, default",
                "style": "resource_tracking_symbols",
                "style_history": "",
                "cluster": 12,
                "filters": None,
                "query": "resource_tracking_week",
                "unique": "deviceid",
                "id": "resource_tracking_week_symbols_overlay",
                "legend": "//static.dpaw.wa.gov.au/static/firesource/static/source/legends/resource_tracking_week_symbols_overlay.png",
                "shown": True,
                "name": "Resource Tracking - Symbols Overlay",
                "details":
            {
                "updated": "Live",
                "renderer": "layerdetails",
                "legend_width": 600,
                "tags": [
                        "resource",
                        "tracking",
                        "week",
                        "symbols"
                    ]
                },
                "type": "vectoroverlay"
            }, {
                "tags": "resource, tracking, week, default",
                "style": "resource_tracking",
                "style_history": "vector_history",
                "cluster": 12,
                "filters":
                {
                    "Comms Bus": "symbol:device_comms_bus",
                    "Heavy Duty": "symbol:device_heavy_duty",
                    "Dozer": "symbol:device_dozer",
                    "Gang Truck": "symbol:device_gang_truck",
                    "Aviation": "group:aviation"
                },
                "query": "resource_tracking_week",
                "unique": "deviceid",
                "id": "resource_tracking_week_base",
                "legend": "//static.dpaw.wa.gov.au/static/firesource/static/source/legends/resource_tracking_week_base.png",
                "shown": True,
                "name": "Resource Tracking",
                "details":
                {
                    "updated": "Live",
                    "positionalaccuracy": "Unknown",
                    "description": "Resource tracking data showing points within the last week",
                    "tags": [
                            "resource",
                            "tracking",
                            "week"
                        ],
                        "custodian": "DPAW",
                        "legend_width": 400,
                        "source": "DPAW",
                        "renderer": "layerdetails"
                    },
                    "type": "vector"
            }]
    if fmt == "html":
        cntxt.update({
            "columns": Layer.COLUMNS,
            "layers":layers,
            "user": request.user })
        response = render_to_response('spatial/layers.html', cntxt)
        cache.set(cachekey, {"content":response.content}, 600)
        return response
    elif fmt == "json":
        result = json.dumps({
                "layers": trackingLayers + [layer.as_json() for layer in layers],
                "maps": map_list(request, fmt="dict")
            }, cls=JSONEncoder)
        mimetype = 'application/json'
    response = http.HttpResponse(result, content_type=mimetype)
    response["Cache-Control"] = "max-age=600, public"
    cache.set(cachekey, {"content":response.content, "mimetype":mimetype}, 600)
    return response

def query_vector_layer(request, layerid, mimetype='application/json'):
    if request.method == "POST":
        postdict = json.loads(request.body)
        content = remote_history(request,postdict)
        response = http.HttpResponse(content, content_type=mimetype)
        return response
    else:
        cachekey = "remote_devices_json"
        if cache.get(cachekey):
            response = http.HttpResponse(cache.get(cachekey), content_type=mimetype)
            response["Cache-Control"] = "max-age=60, public"
            return response
        content = remote_devices(request)
        cache.set(cachekey, content, 60)
        response = http.HttpResponse(content, content_type=mimetype)
        response["Cache-Control"] = "max-age=60, public"
        return response


def centerscale_topoly2(center, scale, docsize):
    '''
    Takes a document size and center and scale, and generates a bounding box
    for that scale and document size as a polygon in Well Known Text
    '''
    # find projection
    # project center & calculate bounds
    pcenter = center.transform(srid, clone=True)
    width = docsize[0] / 1000 * scale
    height = docsize[1] / 1000 * scale
    xvals = pcenter.buffer(width, quadsegs=1)[0].x
    yvals = pcenter.buffer(height, quadsegs=1)[0].y
    poly = Polygon(zip(xvals, yvals))
    poly.set_srid(srid)
    poly.transform(4283) # back to gda94
    return poly.wkt

    return "POLYGON (({0.longitude} {0.latitude}, {1.longitude} {0.latitude}, {1.longitude} {1.latitude}, {0.longitude} {1.latitude}, {0.longitude} {0.latitude}))".format(topleft, bottomright)
def centerscale_topoly(center, scale, docsize):
    '''
    Takes a document size and center and scale, and generates a bounding box
    for that scale and document size as a polygon in Well Known Text
    '''
    # calculate bounds from center and set them according to template
    if not isinstance(center, distance.Point):
        try:
            center = distance.Point(longitude=center.x,latitude=center.y)
        except:
            center = distance.Point(center)
    width = distance.distance(meters = docsize[0] / 1000 * scale)
    midleft = (width * 0.5).destination(center, 270)
    topleft = distance.Point(longitude=midleft.longitude, latitude = center.latitude + (midleft.longitude - center.longitude) * (docsize[1]/docsize[0]))
    bottomright = distance.Point(longitude=center.longitude + (center.longitude - midleft.longitude), latitude = center.latitude - (topleft.latitude - center.latitude))
    return "POLYGON (({0.longitude} {0.latitude}, {1.longitude} {0.latitude}, {1.longitude} {1.latitude}, {0.longitude} {1.latitude}, {0.longitude} {0.latitude}))".format(topleft, bottomright)

#@task
def tile_wms(layer, extent, docsize, dpi, workdir, wmsauth):
    '''
    takes a layer and generates a tiled wms of that layer in the current dir for the
    specified extent and template size
    '''
    logger = logger_setup('tile_wms')
    logger.info('Called with: {0}'.format((layer, extent, docsize, dpi, workdir)))
    if layer.transparent:
        layerimage, outputformat = layer.layer_id + ".png", "PNG"
    else:
        layerimage, outputformat = layer.layer_id + ".jpg", "JPEG"
    sizex = docsize[0] / 25.4 * dpi
    sizey = sizex * (extent[3] - extent[1]) / (extent[2] - extent[0])
    layerurl = "http:" + layer.url.replace("gwc/service/wms", "ows")
    logger.info('layerurl: {0}'.format(layerurl))
    gdaltile = render_to_response('spatial/gdalwms.xml', locals())
    logger.info('gdaltile:')
    logger.info(gdaltile.content)
    with open(layer.layer_id + ".xml", "w") as gdalfile:
        gdalfile.write(gdaltile.content)
    subprocess.check_call("gdal_translate -q -of {0} {1}.xml {2} && convert {2} -transparent white {2}".format(outputformat, layer.layer_id, layerimage), shell=True)
    logger.info("layerimage creation successful: {0}".format(layerimage))
    return layerimage


@login_required
def print(request, dpi=200, fmt="pdf"):
    '''
    If post create/end a map in database
    If get print latest map for workdir specified
    '''
    cachekey = "print.{}?{}".format(fmt, request.META["QUERY_STRING"])
    cacheddata = cache.get(cachekey)
    if cacheddata:
        content, mimetype, filename = cacheddata
        response = http.HttpResponse(content, content_type=mimetype)
        response["Content-Disposition"] = 'inline; filename="{}"'.format(filename)
        return response
    logger = logger_setup('print')
    try:
        spatial_state = json.loads(request.GET["ss"])
    except:
        return http.HttpResponse(subprocess.check_output([GDAL_TRANSLATE, "--version"]))
    cwd = os.getcwd()
    spatialmap = Map(name=request.GET["name"], created_by=request.user, modified_by=request.user)
    spatialmap.layers = spatial_state["layers"]
    spatialmap.center = "POINT ({0} {1})".format(*spatial_state["center"]["coordinates"])
    spatialmap.scale = int(spatial_state["scale"])
    spatialmap.workdir = spatialmap.created_by.email + "-sssprint-" + spatialmap.date_created.strftime("%Y%m%d_%H%M")
    spatialmap.template = "inkscape_a3_landscape"
    workdir = os.path.join("/run/shm", spatialmap.workdir)
    logger.info("Workdir: {0}".format(workdir))
    # take lock for current folder/map
    try:
        os.makedirs(workdir)
        os.chdir(workdir)
        logger.info('Taking a lock in the workdir')
    except:
        return http.HttpResponse("Busy, please try later")
    docsize = document_sizes[spatialmap.template]
    spatialmap.bounds = centerscale_topoly(spatialmap.center, spatialmap.scale, docsize)
    # find out projection for printing eastings/northings
    srid = False
    if spatialmap.center.x > 108 and spatialmap.center.x <= 114: srid = 28349
    elif spatialmap.center.x > 114 and spatialmap.center.x <= 120: srid = 28350
    elif spatialmap.center.x > 120 and spatialmap.center.x <= 126: srid = 28351
    elif spatialmap.center.x > 126 and spatialmap.center.x <= 132: srid = 28352
    elif spatialmap.center.x > 132 and spatialmap.center.x <= 138: srid = 28353
    elif spatialmap.center.x > 138 and spatialmap.center.x <= 144: srid = 28354
    elif spatialmap.center.x > 144 and spatialmap.center.x <= 150: srid = 28355
    elif spatialmap.center.x > 150 and spatialmap.center.x <= 156: srid = 28356
    class bnds: pass
    bnds.xmin, bnds.ymin = round(spatialmap.bounds.extent[0], 5), round(spatialmap.bounds.extent[1], 5)
    bnds.xmid, bnds.ymid = round(spatialmap.center.x, 5), round(spatialmap.center.y, 5)
    bnds.xmax, bnds.ymax = round(spatialmap.bounds.extent[2], 5), round(spatialmap.bounds.extent[3], 5)
    # pbnds is projected bounds
    if srid:
        class pbnds: pass
        from django.contrib.gis.geos.point import Point
        pbnds.xmin, pbnds.ymin = Point(bnds.xmin, bnds.ymin, srid=4283).transform(srid, clone=True)
        pbnds.xmid, pbnds.ymid = Point(bnds.xmid, bnds.ymid, srid=4283).transform(srid, clone=True)
        pbnds.xmax, pbnds.ymax = Point(bnds.xmax, bnds.ymax, srid=4283).transform(srid, clone=True)
        pbnds.xmin, pbnds.ymin = int(round(pbnds.xmin, 0)), int(round(pbnds.ymin, 0))
        pbnds.xmid, pbnds.ymid = int(round(pbnds.xmid, 0)), int(round(pbnds.ymid, 0))
        pbnds.xmax, pbnds.ymax = int(round(pbnds.xmax, 0)), int(round(pbnds.ymax, 0))
    # calculate this from scalebars/km given scalebar is 0.2m
    scalebar_kms = round(spatialmap.scale / 5000, 2)
    # this should asjust for users local time not servers local time. Users offset should be set automatically on map load by browsers offset.
    spatialmap_datetime = datetime.fromtimestamp(time.mktime(time.localtime(calendar.timegm(spatialmap.date_created.timetuple())))).strftime("%a, %d %b %Y %H:%M")
    # Well this is needlessly complex:
    #compositepng, compositejpg, compositepdf, zipped = [(n+".png",n+".jpg",n+".pdf",n+".zip") for n in [spatialmap.map_id + spatialmap.date_created.strftime("_%Y%m%d_%H%M")]][0]
    composite = spatialmap.map_id + spatialmap.date_created.strftime("_%Y%m%d_%H%M")
    compositepng = "{0}.png".format(composite)
    compositejpg = "{0}.jpg".format(composite)
    compositepdf = "{0}.pdf".format(composite)
    # grab user shared_id for login
    wmsauth = "{}:{}".format(request.META["HTTP_REMOTE_USER"], request.META["HTTP_X_SHARED_ID"])
    logger.info("Starting to iterate through layers: {0}".format(spatialmap.layers))
    for index, lyr in enumerate(spatialmap.layers):
        logger.info("Layer: {0}".format(lyr))
        if not RasterLayer.objects.filter(url__startswith="//kmi.dpaw.wa.gov.au/", layer_id=lyr["layer_id"]).order_by("-effective_from").exists():
            if lyr["layer_id"].startswith("resource_tracking_week_base"):
                lyr["layer_id"] = "resource_tracking_printable"
            else:
                continue
        layer = RasterLayer.objects.filter(layer_id=lyr["layer_id"]).order_by("-effective_from")[0]
        logger.info("Layer {0} is a raster layer, call tile_wms".format(layer))
        try:
            lyr["location"] = tile_wms(layer=layer, extent=spatialmap.bounds.extent, docsize=docsize, dpi=dpi, workdir=workdir, wmsauth=wmsauth)
        except Exception as e:
            os.chdir(cwd)
            return http.HttpResponse("<h2>Layer <u>{0}</u> failed to render, try zooming in or disabling this layer and printing again.</h2>workdir: <pre>{1}</pre><br>error: <pre>{2}</pre>".format(layer.name, workdir, e))
    finalpng = "inkscape_" + compositepng
    finaljpg = "inkscape_" + compositejpg
    finalsvg = finaljpg.replace(".jpg", ".svg")
    finalpdf = "inkscape_" + compositepdf
    with open(finalsvg, "w") as inkscapesvg:
        inkscapesvg.write(render_to_response('spatial/{0}.svg'.format(spatialmap.template), locals()).content)
    if fmt == "pdf":
        subprocess.check_call("inkscape {0} --export-dpi={2} --export-pdf={1}".format(finalsvg, finalpdf, dpi), shell=True)
        content = open(finalpdf).read()
        mimetype = "application/pdf"
        filename = spatialmap.name + ".pdf"
    elif fmt == "jpg":
        subprocess.check_call("inkscape {0} --export-dpi={2} --export-png={1} && convert {1} -quality 100% {3}".format(finalsvg, finalpng, dpi, finaljpg), shell=True)
        content = open(finaljpg).read()
        mimetype = "image/jpg"
        filename = spatialmap.name + ".jpg"
    cache.set(cachekey, (content, mimetype, filename), 600)
    response = http.HttpResponse(content, content_type=mimetype)
    response["Content-Disposition"] = 'inline; filename="{}"'.format(filename)
    logger.info('Freeing the workdir lock')
    os.chdir(cwd)
    shutil.rmtree(workdir)
    return response

