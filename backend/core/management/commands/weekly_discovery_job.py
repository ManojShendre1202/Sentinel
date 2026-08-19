"""
WeeklyDiscoveryJob — entrypoint for Graph 1.

Cron on the OCI VM calls `python manage.py weekly_discovery_job` weekly.
Cron always fires; ScheduleConfig's toggle (Django admin) decides if it
actually runs. `--manual` bypasses the toggle for an on-demand run.
`--resume <run_id>` continues a previously failed AgentRun from its last
completed node (via the graph's checkpointer) instead of restarting from
fetch_jobs — avoids re-spending API credits already spent on that step.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from backend.core import gmail_notify
from backend.core.models import AgentRun, ScheduleConfig
from backend.graphs import discovery_graph


class Command(BaseCommand):
    help = "Run Graph 1: fetch -> normalize -> dedup -> score -> shortlist."

    def add_arguments(self, parser):
        parser.add_argument(
            "--manual",
            action="store_true",
            help="Run regardless of ScheduleConfig.weekly_discovery_enabled.",
        )
        parser.add_argument(
            "--resume",
            type=int,
            metavar="RUN_ID",
            help="Resume a previously failed AgentRun by id instead of starting fresh.",
        )

    def handle(self, *args, **options):
        manual = options["manual"]
        resume_id = options.get("resume")
        schedule = ScheduleConfig.get_solo()

        if resume_id:
            run = AgentRun.objects.get(pk=resume_id, graph="discovery")
        else:
            if not manual and not schedule.weekly_discovery_enabled:
                self.stdout.write("weekly_discovery_enabled is off, skipping.")
                return
            run = AgentRun.objects.create(graph="discovery", trigger="manual" if manual else "scheduled")

        try:
            state = discovery_graph.run(trigger=run.trigger, thread_id=str(run.pk), resume=bool(resume_id))
            run.stage_counts = state
        except Exception as exc:
            run.errors = [str(exc)]
            raise
        finally:
            run.finished_at = timezone.now()
            run.save()
            schedule.last_run_at = run.finished_at
            schedule.last_run_status = "error" if run.errors else "ok"
            schedule.save()

            if run.errors:
                try:
                    gmail_notify.send_failure_email(run)
                except Exception as notify_exc:
                    self.stderr.write(f"Failure email not sent: {notify_exc}")
