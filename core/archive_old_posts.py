from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import Post, PostArchiveLog
from core.archive_utils import five_months_ago


class Command(BaseCommand):

    help = 'Automatically archive posts older than five months.'

    def handle(self, *args, **options):

        cutoff_date = five_months_ago()

        old_posts = Post.objects.filter(
            status='active',
            created_at__date__lte=cutoff_date
        )

        archived_count = 0

        for post in old_posts:

            post.status = 'archived'
            post.archived_at = timezone.now()

            post.save(
                update_fields=['status', 'archived_at']
            )

            PostArchiveLog.objects.create(
                post=post,
                action='archived',
                performed_by=None
            )

            archived_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully archived {archived_count} posts.'
            )
        )