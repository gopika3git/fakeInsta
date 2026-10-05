"""
Views for detector app.
All forms are handled via plain HTML POST (no forms.py).
Authentication is session-based using custom AdminUser / Police / RegisteredUser tables.
"""
import io
import hashlib #password encryption
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse, HttpResponseRedirect
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.urls import reverse

from .models import (
    AdminUser, Police, RegisteredUser, FakeIDRequest, Complaint, PredictionLog
)
from . import ml_utils


# ===========================================================
#                 HELPERS
# ===========================================================
def _hash(pw):
    return hashlib.sha256(pw.encode()).hexdigest()


def _admin_required(request):
    return request.session.get('role') == 'ADMIN'


def _police_required(request):
    return request.session.get('role') == 'POLICE'


def _user_required(request):
    return request.session.get('role') == 'USER'


def _bootstrap_admin():
    """Create default admin if missing."""
    if not AdminUser.objects.filter(username='admin').exists():
        AdminUser.objects.create(username='admin', password=_hash('password123'))


# ============================================================
#                 PUBLIC PAGES
# ============================================================
def index(request):
    _bootstrap_admin()
    return render(request, 'common/index.html')


def user_register(request):
    if request.method == 'POST':
        full_name = request.POST.get('full_name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        password = request.POST.get('password', '')
        confirm = request.POST.get('confirm', '')

        if not all([full_name, username, email, phone, password]):
            messages.error(request, "All fields except address are required.")
        elif password != confirm:
            messages.error(request, "Passwords do not match.")
        elif RegisteredUser.objects.filter(username=username).exists():
            messages.error(request, "Username already taken.")
        elif RegisteredUser.objects.filter(email=email).exists():
            messages.error(request, "Email already registered.")
        else:
            RegisteredUser.objects.create(
                full_name=full_name, username=username, email=email,
                phone=phone, address=address, password=_hash(password)
            )
            messages.success(request, "Registration successful. Please login.")
            return redirect('user_login')
    return render(request, 'common/register.html')


def user_login(request):
    if request.method == 'POST':
        u = request.POST.get('username', '').strip()
        p = request.POST.get('password', '')
        try:
            user = RegisteredUser.objects.get(username=u, password=_hash(p))
            request.session['role'] = 'USER'
            request.session['user_id'] = user.id
            request.session['user_name'] = user.full_name
            return redirect('user_home')
        except RegisteredUser.DoesNotExist:
            messages.error(request, "Invalid credentials.")
    return render(request, 'common/login.html', {'role': 'USER', 'title': 'Citizen Portal'})


def admin_login(request):
    _bootstrap_admin()
    if request.method == 'POST':
        u = request.POST.get('username', '').strip()
        p = request.POST.get('password', '')
        try:
            admin = AdminUser.objects.get(username=u, password=_hash(p))
            request.session['role'] = 'ADMIN'
            request.session['admin_id'] = admin.id
            request.session['user_name'] = admin.username
            return redirect('admin_home')
        except AdminUser.DoesNotExist:
            messages.error(request, "Invalid credentials.")
    return render(request, 'common/login.html', {'role': 'ADMIN', 'title': 'Administrator Access'})


def police_login(request):
    if request.method == 'POST':
        u = request.POST.get('username', '').strip()
        p = request.POST.get('password', '')
        try:
            officer = Police.objects.get(username=u, password=_hash(p), is_active=True)
            request.session['role'] = 'POLICE'
            request.session['police_id'] = officer.id
            request.session['user_name'] = officer.full_name
            request.session['badge_no'] = officer.badge_no
            return redirect('police_home')
        except Police.DoesNotExist:
            messages.error(request, "Invalid credentials or account inactive.")
    return render(request, 'common/login.html', {'role': 'POLICE', 'title': 'Officer Login'})


def logout_view(request):
    request.session.flush()
    return redirect('index')


# ============================================================
#                 ADMIN MODULE
# ============================================================
def admin_home(request):
    if not _admin_required(request):
        return redirect('admin_login')
    ctx = {
        'total_police': Police.objects.count(),
        'total_users': RegisteredUser.objects.count(),
        'total_requests': FakeIDRequest.objects.count(),
        'pending_requests': FakeIDRequest.objects.filter(status='PENDING').count(),
        'fake_count': FakeIDRequest.objects.filter(verdict='FAKE').count(),
        'real_count': FakeIDRequest.objects.filter(verdict='REAL').count(),
        'open_complaints': Complaint.objects.filter(status='OPEN').count(),
        'recent_requests': FakeIDRequest.objects.all()[:5],
    }
    return render(request, 'admin_panel/home.html', ctx)


def admin_add_police(request):
    if not _admin_required(request):
        return redirect('admin_login')
    if request.method == 'POST':
        data = {
            'full_name': request.POST.get('full_name', '').strip(),
            'badge_no': request.POST.get('badge_no', '').strip(),
            'station': request.POST.get('station', '').strip(),
            'rank': request.POST.get('rank', '').strip(),
            'phone': request.POST.get('phone', '').strip(),
            'email': request.POST.get('email', '').strip(),
            'username': request.POST.get('username', '').strip(),
        }
        password = request.POST.get('password', '')
        if not all([data['full_name'], data['badge_no'], data['station'],
                    data['phone'], data['email'], data['username'], password]):
            messages.error(request, "All fields except rank are required.")
        elif Police.objects.filter(username=data['username']).exists():
            messages.error(request, "Username already taken.")
        elif Police.objects.filter(badge_no=data['badge_no']).exists():
            messages.error(request, "Badge number already exists.")
        else:
            Police.objects.create(password=_hash(password), **data)
            messages.success(request, f"Officer {data['full_name']} added successfully.")
            return redirect('admin_view_police')
    return render(request, 'admin_panel/add_police.html')


def admin_view_police(request):
    if not _admin_required(request):
        return redirect('admin_login')
    officers = Police.objects.all()
    return render(request, 'admin_panel/view_police.html', {'officers': officers})


def admin_edit_police(request, pk):
    if not _admin_required(request):
        return redirect('admin_login')
    officer = get_object_or_404(Police, pk=pk)
    if request.method == 'POST':
        officer.full_name = request.POST.get('full_name', officer.full_name).strip()
        officer.badge_no = request.POST.get('badge_no', officer.badge_no).strip()
        officer.station = request.POST.get('station', officer.station).strip()
        officer.rank = request.POST.get('rank', officer.rank).strip()
        officer.phone = request.POST.get('phone', officer.phone).strip()
        officer.email = request.POST.get('email', officer.email).strip()
        officer.is_active = request.POST.get('is_active') == 'on'
        new_password = request.POST.get('password', '').strip()
        if new_password:
            officer.password = _hash(new_password)
        officer.save()
        messages.success(request, "Officer updated.")
        return redirect('admin_view_police')
    return render(request, 'admin_panel/edit_police.html', {'officer': officer})


def admin_delete_police(request, pk):
    if not _admin_required(request):
        return redirect('admin_login')
    officer = get_object_or_404(Police, pk=pk)
    officer.delete()
    messages.success(request, "Officer removed.")
    return redirect('admin_view_police')


def admin_requests(request):
    if not _admin_required(request):
        return redirect('admin_login')
    requests_qs = FakeIDRequest.objects.all().select_related('user', 'verified_by')
    return render(request, 'admin_panel/requests.html', {'requests': requests_qs})


def admin_analyze_request(request, pk):
    """Admin independently analyzes a request via Apify."""
    if not _admin_required(request):
        return redirect('admin_login')
    req = get_object_or_404(FakeIDRequest, pk=pk)
    result = None
    error = None
    try:
        verdict, prob, feats = ml_utils.predict_from_username(req.instagram_id)
        result = {'verdict': verdict, 'probability': prob, 'features': feats}
        PredictionLog.objects.create(
            source='API', actor_role='ADMIN',
            actor_name=request.session.get('user_name', 'admin'),
            instagram_id=req.instagram_id,
            verdict=verdict, fake_probability=prob,
            features={k: v for k, v in feats.items() if k != 'meta'},
        )
    except Exception as e:
        error = str(e)
    return render(request, 'admin_panel/analyze_request.html',
                  {'req': req, 'result': result, 'error': error})


def admin_complaints(request):
    if not _admin_required(request):
        return redirect('admin_login')
    complaints = Complaint.objects.all().select_related('user')
    return render(request, 'admin_panel/complaints.html', {'complaints': complaints})


def admin_complaint_reply(request, pk):
    if not _admin_required(request):
        return redirect('admin_login')
    complaint = get_object_or_404(Complaint, pk=pk)
    if request.method == 'POST':
        complaint.admin_reply = request.POST.get('reply', '').strip()
        complaint.status = request.POST.get('status', 'REVIEWED')
        complaint.save()
        messages.success(request, "Complaint updated.")
        return redirect('admin_complaints')
    return render(request, 'admin_panel/complaint_reply.html', {'c': complaint})


def admin_verify_id(request):
    """Admin manually enters Instagram ID and checks via Apify."""
    if not _admin_required(request):
        return redirect('admin_login')
    result = None
    error = None
    instagram_id = ''
    if request.method == 'POST':
        instagram_id = request.POST.get('instagram_id', '').strip().lstrip('@')
        if instagram_id:
            try:
                verdict, prob, feats = ml_utils.predict_from_username(instagram_id)
                result = {'verdict': verdict, 'probability': prob,
                          'features': feats, 'instagram_id': instagram_id}
                PredictionLog.objects.create(
                    source='API', actor_role='ADMIN',
                    actor_name=request.session.get('user_name', 'admin'),
                    instagram_id=instagram_id,
                    verdict=verdict, fake_probability=prob,
                    features={k: v for k, v in feats.items() if k != 'meta'},
                )
            except Exception as e:
                error = str(e)
    return render(request, 'admin_panel/verify_id.html',
                  {'result': result, 'error': error, 'instagram_id': instagram_id})


# ============================================================
#                 POLICE MODULE
# ============================================================
def police_home(request):
    if not _police_required(request):
        return redirect('police_login')
    pending = FakeIDRequest.objects.filter(status='PENDING').select_related('user')
    my_verifications = FakeIDRequest.objects.filter(
        verified_by_id=request.session['police_id']).count()
    return render(request, 'police_panel/home.html',
                  {'pending': pending, 'my_count': my_verifications})


def police_verify_id(request):
    """Officer manually checks an Instagram ID via Apify."""
    if not _police_required(request):
        return redirect('police_login')
    result = None
    error = None
    instagram_id = ''
    if request.method == 'POST':
        instagram_id = request.POST.get('instagram_id', '').strip().lstrip('@')
        if instagram_id:
            try:
                verdict, prob, feats = ml_utils.predict_from_username(instagram_id)
                result = {'verdict': verdict, 'probability': prob,
                          'features': feats, 'instagram_id': instagram_id}
                PredictionLog.objects.create(
                    source='API', actor_role='POLICE',
                    actor_name=request.session.get('user_name', ''),
                    instagram_id=instagram_id,
                    verdict=verdict, fake_probability=prob,
                    features={k: v for k, v in feats.items() if k != 'meta'},
                )
            except Exception as e:
                error = str(e)
    return render(request, 'police_panel/verify_id.html',
                  {'result': result, 'error': error, 'instagram_id': instagram_id})


def police_pending(request):
    if not _police_required(request):
        return redirect('police_login')
    pending = FakeIDRequest.objects.filter(status='PENDING').select_related('user')
    return render(request, 'police_panel/pending.html', {'pending': pending})


def police_analyze(request, pk):
    """Officer analyzes a citizen request and finalizes verdict."""
    if not _police_required(request):
        return redirect('police_login')
    req = get_object_or_404(FakeIDRequest, pk=pk)
    result = None
    error = None

    if request.method == 'POST':
        # Officer submits final decision
        action = request.POST.get('action')
        if action == 'finalize':
            req.verdict = request.POST.get('verdict', 'UNKNOWN')
            try:
                req.fake_probability = float(request.POST.get('fake_probability') or 0)
            except ValueError:
                req.fake_probability = 0
            req.officer_notes = request.POST.get('notes', '').strip()
            req.status = 'VERIFIED'
            req.verified_by_id = request.session['police_id']
            req.verified_at = timezone.now()
            req.save()
            messages.success(request, f"Case {req.case_no} closed - verdict: {req.verdict}")
            return redirect('police_home')

    # Run Apify analysis (GET or before finalize)
    try:
        verdict, prob, feats = ml_utils.predict_from_username(req.instagram_id)
        result = {'verdict': verdict, 'probability': prob, 'features': feats}
        if not req.raw_features:
            req.raw_features = {k: v for k, v in feats.items() if k != 'meta'}
            req.save()
    except Exception as e:
        error = str(e)

    return render(request, 'police_panel/analyze.html',
                  {'req': req, 'result': result, 'error': error})


def police_report_pdf(request, pk):
    """Generate PDF case report using ReportLab."""
    if not _police_required(request):
        return redirect('police_login')
    req = get_object_or_404(FakeIDRequest, pk=pk)
    return _generate_pdf(req)


def _generate_pdf(req):
    """Build a professional case-report PDF."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import cm
        from reportlab.lib.colors import HexColor
    except ImportError:
        return HttpResponse("ReportLab not installed. Run: pip install reportlab",
                            content_type='text/plain')

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4

    AMBER = HexColor('#f59e0b')
    SLATE = HexColor('#1a2332')
    RED = HexColor('#dc2626')
    GREEN = HexColor('#10b981')

    # Header band
    c.setFillColor(SLATE)
    c.rect(0, h - 3 * cm, w, 3 * cm, fill=1, stroke=0)
    c.setFillColor(AMBER)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(2 * cm, h - 1.5 * cm, "CYBER INVESTIGATION DEPARTMENT")
    c.setFillColor(HexColor('#ffffff'))
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, h - 2.2 * cm, "Fake Instagram Account — Case Verification Report")
    c.setFillColor(AMBER)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(w - 2 * cm, h - 1.5 * cm, f"CASE NO: {req.case_no}")
    c.setFillColor(HexColor('#cbd5e1'))
    c.setFont("Helvetica", 9)
    c.drawRightString(w - 2 * cm, h - 2.2 * cm,
                      f"Generated: {timezone.now().strftime('%d %b %Y %H:%M')}")

    # Body
    y = h - 4 * cm
    c.setFillColor(SLATE)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(2 * cm, y, "CASE DETAILS")
    c.setStrokeColor(AMBER)
    c.setLineWidth(1.5)
    c.line(2 * cm, y - 4, w - 2 * cm, y - 4)

    y -= 1 * cm
    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor('#000000'))

    rows = [
        ("Case No", req.case_no),
        ("Filed By", f"{req.user.full_name} (@{req.user.username})"),
        ("Email / Phone", f"{req.user.email}  /  {req.user.phone}"),
        ("Filed On", req.created_at.strftime('%d %b %Y, %H:%M')),
        ("Instagram ID", f"@{req.instagram_id}"),
        ("Reason Reported", req.reason or "(not specified)"),
        ("Status", req.status),
    ]
    for label, val in rows:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(2 * cm, y, f"{label}:")
        c.setFont("Helvetica", 10)
        c.drawString(6 * cm, y, str(val)[:80])
        y -= 0.65 * cm

    # Verdict box
    y -= 0.5 * cm
    c.setFillColor(SLATE)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(2 * cm, y, "INVESTIGATION VERDICT")
    c.line(2 * cm, y - 4, w - 2 * cm, y - 4)
    y -= 1.2 * cm

    verdict_color = RED if req.verdict == 'FAKE' else (GREEN if req.verdict == 'REAL' else SLATE)
    c.setFillColor(verdict_color)
    c.rect(2 * cm, y - 1.8 * cm, w - 4 * cm, 1.8 * cm, fill=1, stroke=0)
    c.setFillColor(HexColor('#ffffff'))
    c.setFont("Helvetica-Bold", 22)
    c.drawString(2.5 * cm, y - 1.1 * cm, f"VERDICT:  {req.verdict}")
    c.setFont("Helvetica", 11)
    if req.fake_probability is not None:
        c.drawString(2.5 * cm, y - 1.55 * cm,
                     f"Fake-probability score: {req.fake_probability * 100:.1f}%   "
                     f"(XGBoost classifier)")
    y -= 2.5 * cm

    # Features table
    if req.raw_features:
        c.setFillColor(SLATE)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(2 * cm, y, "EXTRACTED FEATURES (EVIDENCE)")
        c.line(2 * cm, y - 4, w - 2 * cm, y - 4)
        y -= 0.8 * cm
        c.setFont("Helvetica", 9)
        c.setFillColor(HexColor('#000000'))
        items = list(req.raw_features.items())
        for i, (k, v) in enumerate(items):
            col = i % 2
            row = i // 2
            x = 2 * cm if col == 0 else 10.5 * cm
            yy = y - row * 0.55 * cm
            if yy < 5 * cm:
                break
            display_v = f"{v:.4f}" if isinstance(v, float) else str(v)
            c.drawString(x, yy, f"• {k}: {display_v}")

    # Officer block
    c.setFillColor(SLATE)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(2 * cm, 5 * cm, "VERIFYING OFFICER")
    c.line(2 * cm, 5 * cm - 4, w - 2 * cm, 5 * cm - 4)

    c.setFont("Helvetica", 10)
    c.setFillColor(HexColor('#000000'))
    if req.verified_by:
        off = req.verified_by
        c.drawString(2 * cm, 4.2 * cm, f"Name: {off.full_name}")
        c.drawString(2 * cm, 3.7 * cm, f"Badge No: {off.badge_no}")
        c.drawString(2 * cm, 3.2 * cm, f"Station: {off.station}")
        c.drawString(2 * cm, 2.7 * cm,
                     f"Verified On: {req.verified_at.strftime('%d %b %Y, %H:%M') if req.verified_at else '—'}")
    else:
        c.drawString(2 * cm, 4.2 * cm, "Pending officer assignment")

    if req.officer_notes:
        c.setFont("Helvetica-Bold", 10)
        c.drawString(11 * cm, 4.2 * cm, "Officer Notes:")
        c.setFont("Helvetica", 9)
        notes = req.officer_notes[:300]
        # naive wrap
        words = notes.split()
        line = ""
        line_y = 3.7 * cm
        for word in words:
            if len(line) + len(word) > 50:
                c.drawString(11 * cm, line_y, line)
                line_y -= 0.4 * cm
                line = word + " "
                if line_y < 1.5 * cm:
                    break
            else:
                line += word + " "
        if line and line_y >= 1.5 * cm:
            c.drawString(11 * cm, line_y, line)

    # Footer
    c.setFillColor(SLATE)
    c.rect(0, 0, w, 1.2 * cm, fill=1, stroke=0)
    c.setFillColor(AMBER)
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(2 * cm, 0.4 * cm,
                 "This is a computer-generated report. Verified using XGBoost ML model.")
    c.drawRightString(w - 2 * cm, 0.4 * cm, f"Page 1 of 1")

    c.showPage()
    c.save()
    pdf = buf.getvalue()
    buf.close()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="report_{req.case_no}.pdf"'
    return response


# ============================================================
#                 USER MODULE
# ============================================================
def user_home(request):
    """User home with manual 11-feature prediction form."""
    if not _user_required(request):
        return redirect('user_login')
    result = None
    error = None
    submitted = {}

    if request.method == 'POST':
        try:
            submitted = {
                'profile_pic': request.POST.get('profile_pic', '0'),
                'nums_length_username': request.POST.get('nums_length_username', '0'),
                'fullname_words': request.POST.get('fullname_words', '0'),
                'nums_length_fullname': request.POST.get('nums_length_fullname', '0'),
                'name_equals_username': request.POST.get('name_equals_username', '0'),
                'description_length': request.POST.get('description_length', '0'),
                'external_url': request.POST.get('external_url', '0'),
                'private': request.POST.get('private', '0'),
                'posts': request.POST.get('posts', '0'),
                'followers': request.POST.get('followers', '0'),
                'follows': request.POST.get('follows', '0'),
            }
            verdict, prob, feats = ml_utils.predict_from_form(submitted)
            result = {'verdict': verdict, 'probability': prob}
            PredictionLog.objects.create(
                source='FORM', actor_role='USER',
                actor_name=request.session.get('user_name', ''),
                verdict=verdict, fake_probability=prob,
                features=feats,
            )
        except Exception as e:
            error = f"Prediction failed: {str(e)}"

    return render(request, 'user_panel/home.html',
                  {'result': result, 'error': error, 'submitted': submitted})


def user_post_id(request):
    """User submits an Instagram ID for police verification."""
    if not _user_required(request):
        return redirect('user_login')
    if request.method == 'POST':
        instagram_id = request.POST.get('instagram_id', '').strip().lstrip('@')
        reason = request.POST.get('reason', '').strip()
        if not instagram_id:
            messages.error(request, "Instagram ID is required.")
        else:
            FakeIDRequest.objects.create(
                user_id=request.session['user_id'],
                instagram_id=instagram_id,
                reason=reason,
            )
            messages.success(request, "Request submitted to police for verification.")
            return redirect('user_my_requests')
    return render(request, 'user_panel/post_id.html')


def user_my_requests(request):
    if not _user_required(request):
        return redirect('user_login')
    qs = FakeIDRequest.objects.filter(user_id=request.session['user_id']) \
                              .select_related('verified_by')
    return render(request, 'user_panel/my_requests.html', {'requests': qs})


def user_download_result(request, pk):
    """User downloads PDF report once case is verified."""
    if not _user_required(request):
        return redirect('user_login')
    req = get_object_or_404(FakeIDRequest, pk=pk, user_id=request.session['user_id'])
    if req.status != 'VERIFIED':
        messages.warning(request, "Report not available — case still under investigation.")
        return redirect('user_my_requests')
    return _generate_pdf(req)


def user_complaint(request):
    if not _user_required(request):
        return redirect('user_login')
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        if not subject or not message:
            messages.error(request, "Subject and message are required.")
        else:
            Complaint.objects.create(
                user_id=request.session['user_id'],
                subject=subject, message=message,
            )
            messages.success(request, "Complaint submitted to administrator.")
            return redirect('user_my_complaints')
    return render(request, 'user_panel/complaint.html')


def user_my_complaints(request):
    if not _user_required(request):
        return redirect('user_login')
    qs = Complaint.objects.filter(user_id=request.session['user_id'])
    return render(request, 'user_panel/my_complaints.html', {'complaints': qs})
