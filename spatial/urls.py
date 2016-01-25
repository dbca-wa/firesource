from django.conf.urls import patterns, include, url

urlpatterns = patterns('spatial.views',
    url(r'^/layers$', 'layer_list'),
    url(r'^/layers\.(?P<fmt>\w+)$', 'layer_list'),
    url(r'^/query_vector/(?P<layerid>\w+)\.json$', 'query_vector_layer'),
    url(r'^/maps$', 'map_list'),
    url(r'^/print\.(?P<fmt>\w+)$', 'print'),
    url(r'^/maps\.(?P<fmt>\w+)$', 'map_list'),
)
