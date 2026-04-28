"""
Portal KYC views.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from django.views import View
from django.views.generic import ListView
from django.http import HttpResponseForbidden
from django.views.generic.base import RedirectView
from django.db import models

from portal.models import KYC
from portal.forms import KYCSubmitForm


class KYCListView(ListView):
    """View to list all KYC submissions"""
    model = KYC
    template_name = 'portal/kyc/list.html'
    context_object_name = 'kycs'
    paginate_by = 20

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        if not self.request.user.has_perm('portal.view_kyc'):
            messages.error(self.request, 'You do not have permission to view KYC submissions.')
            return redirect('/dashboard/')
        return super().dispatch(*args, **kwargs)

    def get_queryset(self):
        queryset = KYC.objects.select_related('user', 'verified_by').all()
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        document_type = self.request.GET.get('document_type')
        if document_type:
            queryset = queryset.filter(document_type=document_type)
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(user__username__icontains=search) |
                models.Q(document_number__icontains=search)
            )
        queryset = queryset.order_by('-created_at')
        for kyc in queryset:
            kyc.document_count = len(getattr(kyc, "document_file_keys", None) or kyc.document_files or [])
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_kycs'] = KYC.objects.count()
        context['pending_kycs'] = KYC.objects.filter(status='pending').count()
        context['submitted_kycs'] = KYC.objects.filter(status='submitted').count()
        context['approved_kycs'] = KYC.objects.filter(status='approved').count()
        context['rejected_kycs'] = KYC.objects.filter(status='rejected').count()
        context['status_choices'] = KYC.STATUS_CHOICES
        context['document_type_choices'] = KYC.DOCUMENT_TYPE_CHOICES
        return context

class KYCSubmitView(View):
    """KYC submission view"""
    template_name = 'portal/kyc/submit.html'
    success_url = '/dashboard/'

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get(self, request):
        form = KYCSubmitForm()
        return render(request, self.template_name, {'form': form})

    def post(self, request):
        form = KYCSubmitForm(request.POST, request.FILES)
        if form.is_valid():
            return self.form_valid(form)
        return render(request, self.template_name, {'form': form})

    def form_valid(self, form):
        kyc = KYC.objects.create(
            user=self.request.user,
            document_type=form.cleaned_data['document_type'],
            document_number=form.cleaned_data['document_number'],
            status='submitted'
        )
        files = self.request.FILES.getlist('document_files')
        if files:
            from portal.services.storage_service import StorageService
            storage = StorageService()
            document_urls = []
            document_keys = []
            for file in files:
                key = storage.build_kyc_document_key(
                    self.request.user.id,
                    form.cleaned_data['document_type'],
                    file.name
                )
                url = storage.upload_kyc_document(self.request.user.id, form.cleaned_data['document_type'], file)
                document_urls.append(url)
                document_keys.append(key)
            kyc.document_files = document_urls  # legacy compatibility
            kyc.document_file_keys = document_keys
            kyc.save(update_fields=['document_files', 'document_file_keys'])
        if hasattr(self.request.user, 'kyc_status'):
            self.request.user.kyc_status = 'submitted'
            self.request.user.save()
        messages.success(self.request, 'KYC submitted successfully! It will be reviewed soon.')
        return redirect(self.success_url)


class KYCDocumentAccessView(RedirectView):
    """Secure KYC document access via short-lived signed URL."""
    permanent = False

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_redirect_url(self, *args, **kwargs):
        kyc = get_object_or_404(KYC, id=kwargs["kyc_id"])
        if not self.request.user.has_perm("portal.view_kyc") and self.request.user.id != kyc.user_id:
            raise PermissionError("Forbidden")
        index = kwargs.get("file_index", 0)
        try:
            index = int(index)
        except (TypeError, ValueError):
            index = 0
        file_keys = kyc.document_file_keys or []
        if not file_keys:
            from portal.services.storage_service import StorageService
            storage = StorageService()
            file_keys = [storage.extract_s3_key(url) for url in (kyc.document_files or []) if ".amazonaws.com/" in url]
        if index < 0 or index >= len(file_keys):
            raise PermissionError("Document not available")
        from portal.services.storage_service import StorageService
        storage = StorageService()
        signed_url = storage.get_signed_url_for_key(file_keys[index], expiry_hours=1)
        if not signed_url:
            raise PermissionError("Document unavailable")
        return signed_url

    def get(self, request, *args, **kwargs):
        try:
            return super().get(request, *args, **kwargs)
        except PermissionError:
            return HttpResponseForbidden("You are not authorized to access this document.")
