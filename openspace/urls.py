from django.conf import settings
from django.contrib import admin
from django.views.decorators.csrf import csrf_exempt
from graphene_django.views import GraphQLView
from django.urls import path, include, re_path
from django.conf.urls.static import static
from django.http import JsonResponse
from django.views.static import serve


def health_check(request):
    return JsonResponse({'status': 'ok'})

# from myapp.views import verify_email

urlpatterns = [
    path('health/', health_check, name='health-check'),
    path('admin/', admin.site.urls),
    path('graphql/', csrf_exempt(GraphQLView.as_view(graphiql=settings.DEBUG))),
    # path('Api/', include('myapp.urls')),
    path('api/v1/', include('myapp.urls')),
    # path('api/v1/', include('myapprest.urls')),
    # path('verify-email/<uuid:token>/', verify_email, name='verify_email'),
]

# Uploaded media is stored on a Dockploy persistent volume. For larger
# deployments, move this to object storage or a dedicated media server.
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]
