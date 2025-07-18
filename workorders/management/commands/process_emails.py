"""
Django management command to process emails and create tickets.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from workorders.email_service import process_all_email_accounts
from workorders.models import EmailAccount


class Command(BaseCommand):
    help = 'Process emails from configured email accounts and create tickets'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account',
            type=str,
            help='Process emails for a specific email account (by name)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without actually creating tickets',
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS(f'Starting email processing at {timezone.now()}')
        )

        if options['account']:
            # Process specific account
            try:
                account = EmailAccount.objects.get(name=options['account'])
                if not account.is_active:
                    self.stdout.write(
                        self.style.WARNING(f'Account "{account.name}" is not active')
                    )
                    return

                self.stdout.write(f'Processing emails for account: {account.name}')
                
                if options['dry_run']:
                    self.stdout.write(
                        self.style.WARNING('DRY RUN MODE - No tickets will be created')
                    )
                    # TODO: Implement dry run mode
                    return

                from workorders.email_service import EmailProcessor
                processor = EmailProcessor(account)
                result = processor.process_emails()
                processor.disconnect()
                
                self.display_results({account.name: result})
                
            except EmailAccount.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'Email account "{options["account"]}" not found')
                )
                return
        else:
            # Process all active accounts
            if options['dry_run']:
                self.stdout.write(
                    self.style.WARNING('DRY RUN MODE - No tickets will be created')
                )
                # TODO: Implement dry run mode
                return

            self.stdout.write('Processing emails for all active accounts...')
            results = process_all_email_accounts()
            self.display_results(results)

        self.stdout.write(
            self.style.SUCCESS(f'Email processing completed at {timezone.now()}')
        )

    def display_results(self, results):
        """Display processing results"""
        total_processed = 0
        total_created = 0
        total_duplicates = 0
        total_errors = 0

        for account_name, result in results.items():
            if 'error' in result:
                self.stdout.write(
                    self.style.ERROR(f'{account_name}: {result["error"]}')
                )
                continue

            self.stdout.write(
                self.style.SUCCESS(f'{account_name}:')
            )
            self.stdout.write(f'  Processed: {result["processed"]}')
            self.stdout.write(f'  Created: {result["created"]}')
            self.stdout.write(f'  Duplicates: {result["duplicates"]}')
            self.stdout.write(f'  Errors: {result["errors"]}')

            total_processed += result['processed']
            total_created += result['created']
            total_duplicates += result['duplicates']
            total_errors += result['errors']

        if len(results) > 1:
            self.stdout.write(
                self.style.SUCCESS('\nSummary:')
            )
            self.stdout.write(f'  Total Processed: {total_processed}')
            self.stdout.write(f'  Total Created: {total_created}')
            self.stdout.write(f'  Total Duplicates: {total_duplicates}')
            self.stdout.write(f'  Total Errors: {total_errors}')
