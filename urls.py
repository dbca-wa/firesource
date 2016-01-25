from django.conf.urls import patterns, include, url
from django.contrib.gis import admin
from django.views.generic.base import RedirectView

urlpatterns = patterns('',
    url(r'^$', 'spatial.views.standardmap'),
    url(r'^apps/sss', 'spatial.views.standardmap'),
    url(r'^apps/spatial', include('spatial.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^logout', RedirectView.as_view(url='/admin/logout'), name='logout'),
)

