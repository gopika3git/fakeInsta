from django.contrib import admin
# Custom admin/police/user authentication is handled in views.py — Django admin not used.
from .models import *

admin.site.register(AdminUser)
admin.site.register(Police)
admin.site.register(RegisteredUser)
admin.site.register(FakeIDRequest)
admin.site.register(Complaint)
admin.site.register(PredictionLog)