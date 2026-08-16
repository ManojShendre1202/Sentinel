from django.db import models


class JobListing(models.Model):
    """One row per unique job posting discovered by the agent, before any
    shortlisting decision is made. Dedup key is (source, external_id) —
    re-running discovery against the same source must not create duplicates."""
    SOURCE_CHOICES = [
        ('theirstack', 'TheirStack'),
        ('jobspipe', 'JobsPipe'),
        ('adzuna', 'Adzuna'),
    ]

    source        = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    external_id    = models.CharField(max_length=128)
    title          = models.CharField(max_length=255)
    company        = models.CharField(max_length=255)
    location       = models.CharField(max_length=255, blank=True, default='')
    remote         = models.BooleanField(default=False)
    url            = models.URLField(max_length=1000)
    description    = models.TextField(blank=True, default='')
    signals        = models.JSONField(default=dict, blank=True)
    raw_payload    = models.JSONField(default=dict, blank=True)
    discovered_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sentinel_job_listings'
        constraints = [
            models.UniqueConstraint(fields=['source', 'external_id'], name='unique_listing_per_source'),
        ]
        indexes = [
            models.Index(fields=['source', 'external_id']),
        ]


class Shortlist(models.Model):
    """The agent's decision on a listing: pursue it or not, and why.
    One-to-one with JobListing — re-evaluation overwrites the previous
    verdict in place rather than keeping history (single-user, no audit need)."""
    STATUS_CHOICES = [
        ('shortlisted', 'Shortlisted'),
        ('rejected', 'Rejected'),
        ('applied', 'Applied'),
    ]

    job              = models.OneToOneField(JobListing, on_delete=models.CASCADE, related_name='shortlist')
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES)
    match_score      = models.FloatField(null=True, blank=True)
    dimension_scores = models.JSONField(default=dict, blank=True)
    reasoning        = models.TextField(blank=True, default='')
    decided_at       = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'sentinel_shortlist'


class Application(models.Model):
    """One per shortlisted job going through the autofill flow — the table
    the browser extension actually polls and updates. Human-in-the-loop:
    the agent only ever produces 'pending_review' rows; the extension fills
    the DOM and the user submits themselves on the real page."""
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('pending_review', 'Pending Review'),
        ('pending_verification', 'Pending Verification'),
        ('submitted', 'Submitted'),
        ('skipped', 'Skipped'),
    ]

    shortlist        = models.OneToOneField(Shortlist, on_delete=models.CASCADE, related_name='application')
    status           = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    form_data        = models.JSONField(default=dict, blank=True)
    extension_notes  = models.TextField(blank=True, default='')
    site_account     = models.ForeignKey('SiteAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='applications')
    # Set only when status='pending_verification' — a scheduled check flips
    # the row to 'skipped' once this passes without the user completing
    # verification (e.g. a CAPTCHA or emailed OTP the agent can't solve itself).
    verification_expires_at  = models.DateTimeField(null=True, blank=True)
    reviewed_at      = models.DateTimeField(null=True, blank=True)
    submitted_at     = models.DateTimeField(null=True, blank=True)
    created_at       = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sentinel_applications'


class SiteAccount(models.Model):
    """One signup credential per ATS domain (Workday, iCIMS, etc.) that
    requires an account before applying. A unique generated password per
    domain — not one shared password everywhere — so a breach on one site
    doesn't expose credentials on every other site the agent signed up on.
    Same real email reused across domains is fine (it's the user's own)."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('pending_verification', 'Pending Verification'),
        ('failed', 'Failed'),
    ]

    domain            = models.CharField(max_length=255, unique=True)
    email              = models.EmailField()
    # Encrypted at rest before this lands here — plaintext storage of live
    # site credentials is not acceptable even for a single-user tool.
    password_encrypted = models.CharField(max_length=500)
    status             = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending_verification')
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sentinel_site_accounts'


class RecruiterEmail(models.Model):
    """Inbound recruiter messages detected via the Gmail API, plus the
    agent's drafted reply. Human reviews and sends — no auto-send."""
    STATUS_CHOICES = [
        ('detected', 'Detected'),
        ('drafted', 'Drafted'),
        ('reviewed', 'Reviewed'),
        ('sent', 'Sent'),
    ]

    gmail_thread_id   = models.CharField(max_length=128)
    gmail_message_id  = models.CharField(max_length=128, unique=True)
    sender            = models.CharField(max_length=255)
    subject           = models.CharField(max_length=500, blank=True, default='')
    body              = models.TextField(blank=True, default='')
    draft_reply       = models.TextField(blank=True, default='')
    status            = models.CharField(max_length=20, choices=STATUS_CHOICES, default='detected')
    detected_at       = models.DateTimeField(auto_now_add=True)
    sent_at           = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'sentinel_recruiter_emails'


class AgentRun(models.Model):
    """One row per pipeline execution — feeds the dashboard's 'what did the
    agent just do' view without re-querying every other table each time."""
    TRIGGER_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('manual', 'Manual'),
    ]
    GRAPH_CHOICES = [
        ('discovery', 'Graph 1 — Discovery & Shortlist'),
        ('application', 'Graph 2 — Per-Application Automation'),
        ('outcome', 'Graph 3 — Outcome Monitoring'),
    ]

    graph        = models.CharField(max_length=20, choices=GRAPH_CHOICES, default='discovery')
    trigger      = models.CharField(max_length=20, choices=TRIGGER_CHOICES, default='scheduled')
    started_at   = models.DateTimeField(auto_now_add=True)
    finished_at  = models.DateTimeField(null=True, blank=True)
    stage_counts = models.JSONField(default=dict, blank=True)
    errors       = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'sentinel_agent_runs'
        ordering = ['-started_at']


class ScheduleConfig(models.Model):
    """Singleton row (always pk=1) controlling whether the weekly discovery
    cron actually does anything. Cron always fires `run_discovery`; this
    toggle is the only thing that decides whether it runs for real — lets
    the agent be paused/resumed from the Django admin without touching
    crontab on the VM."""

    weekly_discovery_enabled = models.BooleanField(default=True)
    last_run_at              = models.DateTimeField(null=True, blank=True)
    last_run_status          = models.CharField(max_length=20, blank=True, default='')
    notes                    = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'sentinel_schedule_config'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get_solo(cls) -> "ScheduleConfig":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"ScheduleConfig(weekly_discovery_enabled={self.weekly_discovery_enabled})"
