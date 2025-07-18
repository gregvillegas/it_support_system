"""
Email service for processing emails and automatically creating tickets.
"""
import imaplib
import poplib
import email
import re
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parsedate_tz, mktime_tz
from django.contrib.auth.models import User
from django.utils import timezone as django_timezone
from django.core.mail import send_mail
from django.conf import settings
from django.template import Context, Template
from .models import EmailAccount, ProcessedEmail, WorkOrder, EmailTemplate


class EmailProcessor:
    """Process emails and create tickets"""
    
    def __init__(self, email_account):
        self.email_account = email_account
        self.connection = None
    
    def connect(self):
        """Connect to email server"""
        try:
            if self.email_account.protocol == 'imap':
                if self.email_account.use_ssl:
                    self.connection = imaplib.IMAP4_SSL(self.email_account.host, self.email_account.port)
                else:
                    self.connection = imaplib.IMAP4(self.email_account.host, self.email_account.port)
                self.connection.login(self.email_account.username, self.email_account.password)
                self.connection.select('INBOX')
            else:  # POP3
                if self.email_account.use_ssl:
                    self.connection = poplib.POP3_SSL(self.email_account.host, self.email_account.port)
                else:
                    self.connection = poplib.POP3(self.email_account.host, self.email_account.port)
                self.connection.user(self.email_account.username)
                self.connection.pass_(self.email_account.password)
            
            return True
        except Exception as e:
            print(f"Failed to connect to email server: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from email server"""
        if self.connection:
            try:
                if self.email_account.protocol == 'imap':
                    self.connection.close()
                    self.connection.logout()
                else:  # POP3
                    self.connection.quit()
            except:
                pass
            self.connection = None
    
    def fetch_emails(self, limit=50):
        """Fetch new emails from the server"""
        if not self.connection:
            if not self.connect():
                return []
        
        emails = []
        try:
            if self.email_account.protocol == 'imap':
                emails = self._fetch_imap_emails(limit)
            else:  # POP3
                emails = self._fetch_pop3_emails(limit)
        except Exception as e:
            print(f"Error fetching emails: {e}")
        
        return emails
    
    def _fetch_imap_emails(self, limit):
        """Fetch emails using IMAP"""
        # Search for unread emails
        status, messages = self.connection.search(None, 'UNSEEN')
        if status != 'OK':
            return []
        
        email_ids = messages[0].split()
        emails = []
        
        # Limit the number of emails processed
        for email_id in email_ids[-limit:]:
            try:
                status, msg_data = self.connection.fetch(email_id, '(RFC822)')
                if status == 'OK':
                    email_message = email.message_from_bytes(msg_data[0][1])
                    parsed_email = self._parse_email(email_message)
                    if parsed_email:
                        emails.append(parsed_email)
            except Exception as e:
                print(f"Error processing email {email_id}: {e}")
        
        return emails
    
    def _fetch_pop3_emails(self, limit):
        """Fetch emails using POP3"""
        # Get message count
        num_messages = len(self.connection.list()[1])
        emails = []
        
        # Process the last N messages
        start = max(1, num_messages - limit + 1)
        for i in range(start, num_messages + 1):
            try:
                # Get message
                server_msg = self.connection.retr(i)
                email_message = email.message_from_bytes(b'\n'.join(server_msg[1]))
                parsed_email = self._parse_email(email_message)
                if parsed_email:
                    emails.append(parsed_email)
            except Exception as e:
                print(f"Error processing email {i}: {e}")
        
        return emails
    
    def _parse_email(self, email_message):
        """Parse email message and extract relevant information"""
        try:
            # Extract basic information
            subject = self._decode_header(email_message['Subject'] or '')
            sender = self._decode_header(email_message['From'] or '')
            message_id = email_message['Message-ID'] or ''
            date_str = email_message['Date'] or ''
            
            # Parse date
            received_date = django_timezone.now()
            if date_str:
                try:
                    parsed_date = parsedate_tz(date_str)
                    if parsed_date:
                        timestamp = mktime_tz(parsed_date)
                        received_date = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                except:
                    pass
            
            # Extract email address and name from sender
            sender_email = ''
            sender_name = ''
            if sender:
                # Extract email using regex
                email_match = re.search(r'[\w\.-]+@[\w\.-]+', sender)
                if email_match:
                    sender_email = email_match.group(0)
                
                # Extract name (remove email part)
                name_match = re.search(r'^(.+?)\s*<', sender)
                if name_match:
                    sender_name = name_match.group(1).strip('"')
                elif not email_match:
                    sender_name = sender
            
            # Extract body
            body = self._extract_body(email_message)
            
            return {
                'message_id': message_id,
                'subject': subject,
                'sender_email': sender_email,
                'sender_name': sender_name,
                'received_date': received_date,
                'body': body,
                'raw_message': email_message
            }
        except Exception as e:
            print(f"Error parsing email: {e}")
            return None
    
    def _decode_header(self, header):
        """Decode email header"""
        if not header:
            return ''
        
        try:
            decoded_parts = decode_header(header)
            decoded_header = ''
            for part, encoding in decoded_parts:
                if isinstance(part, bytes):
                    if encoding:
                        decoded_header += part.decode(encoding)
                    else:
                        decoded_header += part.decode('utf-8', errors='ignore')
                else:
                    decoded_header += part
            return decoded_header
        except:
            return str(header)
    
    def _extract_body(self, email_message):
        """Extract email body text"""
        body = ''
        
        if email_message.is_multipart():
            for part in email_message.walk():
                if part.get_content_type() == 'text/plain':
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        body += payload.decode(charset, errors='ignore')
                elif part.get_content_type() == 'text/html' and not body:
                    # Fall back to HTML if no plain text
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or 'utf-8'
                        html_body = payload.decode(charset, errors='ignore')
                        # Simple HTML to text conversion
                        body = re.sub(r'<[^>]+>', '', html_body)
        else:
            payload = email_message.get_payload(decode=True)
            if payload:
                charset = email_message.get_content_charset() or 'utf-8'
                body = payload.decode(charset, errors='ignore')
        
        return body.strip()
    
    def process_emails(self):
        """Process emails and create tickets"""
        emails = self.fetch_emails()
        results = {
            'processed': 0,
            'created': 0,
            'duplicates': 0,
            'errors': 0
        }
        
        for email_data in emails:
            try:
                # Check if email already processed
                if ProcessedEmail.objects.filter(
                    email_account=self.email_account,
                    message_id=email_data['message_id']
                ).exists():
                    results['duplicates'] += 1
                    continue
                
                # Create work order from email
                work_order = self._create_work_order_from_email(email_data)
                
                # Record processed email
                processed_email = ProcessedEmail.objects.create(
                    email_account=self.email_account,
                    message_id=email_data['message_id'],
                    subject=email_data['subject'],
                    sender_email=email_data['sender_email'],
                    sender_name=email_data['sender_name'],
                    received_date=email_data['received_date'],
                    work_order=work_order,
                    processing_status='success' if work_order else 'failed'
                )
                
                if work_order:
                    results['created'] += 1
                    # Send confirmation email
                    self._send_confirmation_email(work_order, email_data['sender_email'])
                else:
                    results['errors'] += 1
                
                results['processed'] += 1
                
            except Exception as e:
                print(f"Error processing email {email_data.get('message_id', 'unknown')}: {e}")
                results['errors'] += 1
                
                # Record failed processing
                try:
                    ProcessedEmail.objects.create(
                        email_account=self.email_account,
                        message_id=email_data['message_id'],
                        subject=email_data['subject'],
                        sender_email=email_data['sender_email'],
                        sender_name=email_data['sender_name'],
                        received_date=email_data['received_date'],
                        processing_status='failed',
                        processing_notes=str(e)
                    )
                except:
                    pass
        
        # Update email account stats
        self.email_account.last_processed = django_timezone.now()
        self.email_account.processed_count += results['processed']
        self.email_account.save()
        
        return results
    
    def _create_work_order_from_email(self, email_data):
        """Create a work order from email data"""
        try:
            # Find or create user from email
            user = self._get_or_create_user_from_email(email_data)
            if not user:
                return None
            
            # Create work order
            work_order = WorkOrder.objects.create(
                title=email_data['subject'][:200],  # Limit to 200 chars
                description=email_data['body'],
                task_type=self.email_account.default_task_type,
                task_category=self.email_account.default_task_category,
                priority=self.email_account.default_priority,
                requester=user,
                assigned_to=self.email_account.auto_assign_to
            )
            
            return work_order
        except Exception as e:
            print(f"Error creating work order from email: {e}")
            return None
    
    def _get_or_create_user_from_email(self, email_data):
        """Get or create user from email address"""
        try:
            # Try to find existing user by email
            try:
                user = User.objects.get(email=email_data['sender_email'])
                return user
            except User.DoesNotExist:
                pass
            
            # Create new user
            # Generate username from email
            username = email_data['sender_email'].split('@')[0]
            counter = 1
            original_username = username
            
            while User.objects.filter(username=username).exists():
                username = f"{original_username}_{counter}"
                counter += 1
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email_data['sender_email'],
                first_name=email_data['sender_name'].split()[0] if email_data['sender_name'] else '',
                last_name=' '.join(email_data['sender_name'].split()[1:]) if email_data['sender_name'] and len(email_data['sender_name'].split()) > 1 else ''
            )
            
            return user
        except Exception as e:
            print(f"Error creating user from email: {e}")
            return None
    
    def _send_confirmation_email(self, work_order, sender_email):
        """Send confirmation email to the requester"""
        try:
            # Get email template
            template = EmailTemplate.objects.filter(
                template_type='ticket_created',
                is_active=True
            ).first()
            
            if not template:
                # Use default template
                subject = f"Ticket Created: {work_order.ticket_number}"
                body = f"""
Dear {work_order.requester.first_name or 'User'},

Your support ticket has been created successfully.

Ticket Number: {work_order.ticket_number}
Title: {work_order.title}
Status: {work_order.get_status_display()}
Priority: {work_order.get_priority_display()}

We will review your request and get back to you as soon as possible.

Thank you for contacting our support team.

Best regards,
IT Support Team
"""
            else:
                # Use custom template
                subject_template = Template(template.subject)
                body_template = Template(template.body)
                
                context = Context({
                    'ticket_number': work_order.ticket_number,
                    'title': work_order.title,
                    'status': work_order.get_status_display(),
                    'priority': work_order.get_priority_display(),
                    'requester': work_order.requester,
                    'assigned_to': work_order.assigned_to,
                    'created_at': work_order.created_at,
                })
                
                subject = subject_template.render(context)
                body = body_template.render(context)
            
            # Send email
            send_mail(
                subject=subject,
                message=body,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@example.com'),
                recipient_list=[sender_email],
                fail_silently=True
            )
            
        except Exception as e:
            print(f"Error sending confirmation email: {e}")


def process_all_email_accounts():
    """Process emails for all active email accounts"""
    active_accounts = EmailAccount.objects.filter(is_active=True)
    results = {}
    
    for account in active_accounts:
        try:
            processor = EmailProcessor(account)
            result = processor.process_emails()
            processor.disconnect()
            results[account.name] = result
        except Exception as e:
            print(f"Error processing emails for account {account.name}: {e}")
            results[account.name] = {'error': str(e)}
    
    return results
