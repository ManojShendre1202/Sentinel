from django.contrib import admin

from .models import AgentRun, Application, JobListing, RecruiterEmail, ScheduleConfig, Shortlist, SiteAccount


@admin.register(ScheduleConfig)
class ScheduleConfigAdmin(admin.ModelAdmin):
    """Singleton admin page — the weekly-discovery on/off switch.
    Not yet wired to run_discovery.py (structure only)."""
    list_display = ('weekly_discovery_enabled', 'last_run_at', 'last_run_status')

    def has_add_permission(self, request):
        return not ScheduleConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    """Read-only run log — what the agent actually did, per run."""
    list_display = ('graph', 'trigger', 'started_at', 'finished_at')
    list_filter = ('graph', 'trigger')
    readonly_fields = [f.name for f in AgentRun._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(JobListing)
class JobListingAdmin(admin.ModelAdmin):
    list_display = ('title', 'company', 'source', 'location', 'remote', 'discovered_at')
    list_filter = ('source', 'remote')
    search_fields = ('title', 'company')


@admin.register(Shortlist)
class ShortlistAdmin(admin.ModelAdmin):
    list_display = ('job', 'status', 'match_score', 'decided_at')
    list_filter = ('status',)


admin.site.register(Application)
admin.site.register(SiteAccount)
admin.site.register(RecruiterEmail)
