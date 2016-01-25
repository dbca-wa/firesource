from __future__ import print_function
import logging
import logging.handlers
import os
import subprocess
import urllib
from spatial.models import RasterLayer


def logger_setup(name):
    # Set up logging in a standardised way.                                                            
    logger = logging.getLogger(name)                                                                   
    logger.setLevel(logging.DEBUG)                                                                     
    fh = logging.handlers.RotatingFileHandler(                                                         
        '/tmp/{0}.log'.format(name), maxBytes=20*1024*1024, backupCount=5)                              
    fh.setLevel(logging.DEBUG)                                                                         
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')              
    fh.setFormatter(formatter)                                                                         
    logger.addHandler(fh)                                                                              
    return logger


def ge_wms_rasterlayers(current=True):
    '''
    A convenience function to return a queryset of RasterLayer objects that are
    GoldenEye WMS layers.
    Assumes that the API endpoint for GoldenEye won't change. 
    '''
    rasters = RasterLayer.objects.filter(url__startswith='http://ge.dec.wa.gov.au')
    if current:
        rasters = rasters.filter(effective_to__isnull=True)
    return rasters


def ge_import_legends(rasters=None):
    '''
    A utility function to import legend images from the GoldenEye WMS layers.
    Optionally pass in a queryset of RasterLayers for which to import legends images,
    or the function defaults to using all "current" GE rasters.
    '''
    d = {'REQUEST': 'GetLegendGraphic', 'VERSION': '1.1.0', 'FORMAT': 'image/png', 'width': '20', 'height': '20', 'STRICT': 'false'}
    legends_dir = '/var/www/firesource_static/source/legends'
    if not rasters:
        rasters = ge_wms_rasterlayers()
    print('Import WMS legend images.')
    for r in rasters:
        print(r.name)
        d['style'] = r.layer_id
        url = '{0}&{1}'.format(r.url, urllib.urlencode(d))
        print('Downloading legend from {0}'.format(url))
        png = os.path.join(legends_dir, '{0}.png'.format(r.layer_id))
        urllib.urlretrieve(url, png)
        print('Saved to {0}'.format(png))
    print('Completed.')


def make_ge_legends(ge_import=True):
    '''
    A utility function to (optionally) import legend images for GoldenEye WMS layers,
    and then run the make script to create standard sized PNGs in the correct directory.
    Note that this function does not add files to the repo.
    '''
    if ge_import:
        ge_import_legends()
    print('Running make script.')
    os.chdir('/var/www/firesource_static')
    subprocess.call('python make.py source build', shell=True)
    print('Completed.')
