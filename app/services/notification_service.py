# app/services/notification_service.py
from datetime import datetime, timezone
from app.core.db import db
from app.core.audit import audit
from app.services.email_service import send_email
from typing import List, Dict, Any, Optional

# Role-based notification preferences
ROLE_NOTIFICATION_PREFERENCES = {
    'system_administrator': {
        'all_equipment': True,
        'all_facilities': True,
        'critical_alerts': True,
        'user_actions': True,
        'system_events': True
    },
    'national_administrator': {
        'all_equipment': True,
        'all_facilities': True,
        'critical_alerts': True,
        'user_actions': True,
        'system_events': True
    },
    'national_executive': {
        'all_equipment': True,
        'all_facilities': True,
        'critical_alerts': True,
        'user_actions': False,
        'system_events': True
    },
    'facility_manager': {
        'own_facility': True,
        'critical_alerts': True,
        'maintenance_updates': True,
        'equipment_registration': True,
        'user_actions': True
    },
    'biomedical_engineer': {
        'own_facility': True,
        'technical_alerts': True,
        'maintenance_updates': True,
        'equipment_registration': True
    },
    'maintenance_technician': {
        'own_facility': True,
        'maintenance_updates': True,
        'work_orders': True,
        'equipment_status': True
    },
    'clinician': {
        'own_facility': True,
        'equipment_availability': True,
        'critical_alerts': True
    }
}

class NotificationService:
    @staticmethod
    def get_role_recipients(
        facility_id: Optional[str] = None,
        roles: Optional[List[str]] = None,
        exclude_roles: Optional[List[str]] = None,
        include_national: bool = True
    ) -> List[Dict]:
        """Get users by role and facility scope"""
        with db() as c:
            query = "SELECT id, name, email, role, scope_type, scope_id FROM users WHERE active=1"
            params = []
            
            if roles:
                placeholders = ','.join(['?'] * len(roles))
                query += f" AND role IN ({placeholders})"
                params.extend(roles)
            
            if exclude_roles:
                placeholders = ','.join(['?'] * len(exclude_roles))
                query += f" AND role NOT IN ({placeholders})"
                params.extend(exclude_roles)
            
            users = [dict(r) for r in c.execute(query, params).fetchall()]
        
        # Filter by facility scope
        if facility_id and not include_national:
            users = [u for u in users if str(u.get('scope_id')) == str(facility_id)]
        elif facility_id:
            users = [u for u in users if str(u.get('scope_id')) == str(facility_id) or u.get('scope_type') == 'national']
        
        return users

    @staticmethod
    def notify_equipment_registered(equipment_record: Dict, actor: Optional[Dict] = None) -> Dict:
        """Send notifications when new equipment is registered"""
        facility_id = equipment_record.get('facility_id')
        equipment_id = equipment_record.get('equipment_id')
        equipment_type = equipment_record.get('equipment_type', 'Unknown')
        
        now = datetime.now(timezone.utc).isoformat()
        results = []
        
        # Get all relevant users
        roles_to_notify = [
            'system_administrator', 'national_administrator', 'national_executive',
            'facility_manager', 'biomedical_engineer', 'maintenance_technician'
        ]
        
        users = NotificationService.get_role_recipients(facility_id, roles_to_notify)
        
        # Role-specific messages
        role_messages = {
            'system_administrator': f"New equipment registered: {equipment_id} ({equipment_type}) at facility {facility_id}. Please ensure system configuration is complete.",
            'national_administrator': f"New equipment registered: {equipment_id} ({equipment_type}) at facility {facility_id}. Review national equipment inventory.",
            'national_executive': f"Equipment added to inventory: {equipment_id} ({equipment_type}) at {facility_id}. Equipment capacity updated.",
            'facility_manager': f"New equipment onboarded: {equipment_id} ({equipment_type}). Please ensure proper setup, assign responsible staff, and schedule initial maintenance.",
            'biomedical_engineer': f"New equipment registered: {equipment_id} ({equipment_type}). Please review technical specifications, perform initial inspection, and establish maintenance schedule.",
            'maintenance_technician': f"New equipment added: {equipment_id} ({equipment_type}). Awaiting maintenance schedule and work order creation."
        }
        
        with db() as c:
            for user in users:
                role = user.get('role', '')
                message = role_messages.get(role, f"New equipment registered: {equipment_id} ({equipment_type}) at facility {facility_id}.")
                
                # Add actor info if provided
                if actor:
                    actor_name = actor.get('name', 'A user')
                    message += f"\n\nRegistered by: {actor_name}"
                
                subject = f"New Equipment Registered - {equipment_id}"
                
                # Add facility info
                with db() as c2:
                    facility = c2.execute('SELECT facility_name FROM hospitals WHERE facility_id=?', (facility_id,)).fetchone()
                    if facility:
                        subject += f" at {facility['facility_name']}"
                        message = f"Facility: {facility['facility_name']}\n\n{message}"
                
                # Send email
                try:
                    ok, detail = send_email(user['email'], subject, message)
                    status = 'SENT' if ok else 'PENDING'
                except Exception as e:
                    ok = False
                    detail = str(e)
                    status = 'PENDING'
                
                # Store in notification queue
                c.execute('''
                    INSERT INTO notification_queue 
                    (user_id, email, subject, body, status, created_at, sent_at, notification_type, read_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user['id'],
                    user['email'],
                    subject,
                    message,
                    status,
                    now,
                    now if status == 'SENT' else None,
                    'EQUIPMENT_REGISTERED',
                    None
                ))
                
                results.append({
                    'user_id': user['id'],
                    'email': user['email'],
                    'role': role,
                    'status': status,
                    'detail': detail,
                    'message_preview': message[:100] + '...' if len(message) > 100 else message
                })
        
        try:
            audit(actor, 'EQUIPMENT_REGISTERED_NOTIFICATIONS', 'equipment', equipment_id, {
                'recipients': len(results),
                'facility_id': facility_id,
                'equipment_type': equipment_type
            })
        except Exception:
            pass
        
        return {
            'recipients': len(results),
            'emails_sent': sum(r['status'] == 'SENT' for r in results),
            'emails_pending': sum(r['status'] == 'PENDING' for r in results),
            'results': results
        }

    @staticmethod
    def notify_equipment_updated(equipment_id: str, facility_id: str, changes: Dict, actor: Optional[Dict] = None) -> Dict:
        """Send notifications when equipment is updated"""
        now = datetime.now(timezone.utc).isoformat()
        results = []
        
        # Get facility and facility managers
        with db() as c:
            facility = c.execute('SELECT facility_name FROM hospitals WHERE facility_id=?', (facility_id,)).fetchone()
            facility_name = facility['facility_name'] if facility else facility_id
        
        # Get users to notify - facility managers and biomedical engineers
        users = NotificationService.get_role_recipients(
            facility_id, 
            ['facility_manager', 'biomedical_engineer', 'maintenance_technician']
        )
        
        with db() as c:
            for user in users:
                role = user.get('role', '')
                subject = f"Equipment Updated - {equipment_id}"
                
                message = f"Equipment {equipment_id} at {facility_name} has been updated.\n\n"
                message += "Changes made:\n"
                for key, value in changes.items():
                    message += f"  - {key}: {value}\n"
                
                if actor:
                    message += f"\nUpdated by: {actor.get('name', 'A user')}"
                
                # Role-specific action
                action_messages = {
                    'facility_manager': "Please review the changes and verify equipment status.",
                    'biomedical_engineer': "Please verify technical specifications and update maintenance records.",
                    'maintenance_technician': "Please review changes and update work orders if necessary."
                }
                message += f"\n\n{action_messages.get(role, 'Please review the equipment changes.')}"
                
                try:
                    ok, detail = send_email(user['email'], subject, message)
                    status = 'SENT' if ok else 'PENDING'
                except Exception as e:
                    ok = False
                    detail = str(e)
                    status = 'PENDING'
                
                c.execute('''
                    INSERT INTO notification_queue 
                    (user_id, email, subject, body, status, created_at, sent_at, notification_type, read_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user['id'],
                    user['email'],
                    subject,
                    message,
                    status,
                    now,
                    now if status == 'SENT' else None,
                    'EQUIPMENT_UPDATED',
                    None
                ))
                
                results.append({
                    'user_id': user['id'],
                    'email': user['email'],
                    'role': role,
                    'status': status
                })
        
        return {
            'recipients': len(results),
            'emails_sent': sum(r['status'] == 'SENT' for r in results),
            'emails_pending': sum(r['status'] == 'PENDING' for r in results),
            'results': results
        }

    @staticmethod
    def notify_equipment_status_changed(equipment_id: str, facility_id: str, old_status: str, new_status: str, actor: Optional[Dict] = None) -> Dict:
        """Send notifications when equipment status changes"""
        now = datetime.now(timezone.utc).isoformat()
        results = []
        
        with db() as c:
            facility = c.execute('SELECT facility_name FROM hospitals WHERE facility_id=?', (facility_id,)).fetchone()
            facility_name = facility['facility_name'] if facility else facility_id
        
        # Get all relevant users
        roles_to_notify = ['system_administrator', 'national_administrator', 'facility_manager', 
                          'biomedical_engineer', 'maintenance_technician', 'clinician']
        users = NotificationService.get_role_recipients(facility_id, roles_to_notify)
        
        status_icons = {
            'OPERATIONAL': '✅',
            'MAINTENANCE': '🔧',
            'DECOMMISSIONED': '❌'
        }
        
        with db() as c:
            for user in users:
                role = user.get('role', '')
                subject = f"Equipment Status Change - {equipment_id}"
                
                message = f"{status_icons.get(new_status, '📌')} Equipment {equipment_id} at {facility_name}\n\n"
                message += f"Status changed from: {old_status}\n"
                message += f"New status: {new_status}\n\n"
                
                if actor:
                    message += f"Changed by: {actor.get('name', 'A user')}"
                
                # Role-specific guidance
                role_guidance = {
                    'system_administrator': f"Equipment {equipment_id} status changed to {new_status}. Verify system impact.",
                    'national_administrator': f"Equipment {equipment_id} status changed to {new_status}. National inventory updated.",
                    'facility_manager': f"Equipment {equipment_id} is now {new_status}. Please ensure appropriate staff are notified.",
                    'biomedical_engineer': f"Equipment {equipment_id} is now {new_status}. Update maintenance records as needed.",
                    'maintenance_technician': f"Equipment {equipment_id} is now {new_status}. Update work orders accordingly.",
                    'clinician': f"Equipment {equipment_id} is now {new_status}. Clinical availability updated."
                }
                message += f"\n\n{role_guidance.get(role, f'Equipment {equipment_id} status updated to {new_status}.')}"
                
                try:
                    ok, detail = send_email(user['email'], subject, message)
                    status = 'SENT' if ok else 'PENDING'
                except Exception as e:
                    ok = False
                    detail = str(e)
                    status = 'PENDING'
                
                c.execute('''
                    INSERT INTO notification_queue 
                    (user_id, email, subject, body, status, created_at, sent_at, notification_type, read_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user['id'],
                    user['email'],
                    subject,
                    message,
                    status,
                    now,
                    now if status == 'SENT' else None,
                    'EQUIPMENT_STATUS_CHANGE',
                    None
                ))
                
                results.append({
                    'user_id': user['id'],
                    'email': user['email'],
                    'role': role,
                    'status': status
                })
        
        return {
            'recipients': len(results),
            'emails_sent': sum(r['status'] == 'SENT' for r in results),
            'emails_pending': sum(r['status'] == 'PENDING' for r in results),
            'results': results
        }

    @staticmethod
    def notify_alert_created(alert: Dict, actor: Optional[Dict] = None) -> Dict:
        """Send notifications when an alert is created"""
        facility_id = alert.get('facility_id')
        equipment_id = alert.get('equipment_id') or 'N/A'
        severity = alert.get('severity', 'MEDIUM')
        title = alert.get('title', 'Alert')
        
        now = datetime.now(timezone.utc).isoformat()
        results = []
        
        # Determine which roles to notify based on severity
        roles_to_notify = ['system_administrator', 'national_administrator']
        if severity in ['HIGH', 'CRITICAL']:
            roles_to_notify.extend(['national_executive', 'facility_manager', 'biomedical_engineer', 'clinician'])
        else:
            roles_to_notify.extend(['facility_manager', 'biomedical_engineer'])
        
        users = NotificationService.get_role_recipients(facility_id, roles_to_notify)
        
        severity_icons = {
            'CRITICAL': '🚨',
            'HIGH': '🔴',
            'MEDIUM': '🟡',
            'LOW': '🟢',
            'INFO': 'ℹ️'
        }
        
        with db() as c:
            for user in users:
                role = user.get('role', '')
                subject = f"{severity_icons.get(severity, '🔔')} {severity} Alert - {equipment_id}"
                
                message = f"Alert Generated for {equipment_id}\n\n"
                message += f"Title: {title}\n"
                message += f"Severity: {severity}\n"
                message += f"Facility: {facility_id}\n\n"
                message += f"Details: {alert.get('message', 'No details provided')}\n\n"
                
                if alert.get('recommendation'):
                    message += f"Recommendation: {alert['recommendation']}\n\n"
                
                if actor:
                    message += f"Generated by: {actor.get('name', 'System')}"
                
                # Role-specific actions
                role_actions = {
                    'system_administrator': "Please review the alert and ensure system configuration is correct.",
                    'national_administrator': "Please review the alert and coordinate with facility management.",
                    'national_executive': "Please review the alert and ensure appropriate resources are allocated.",
                    'facility_manager': "Please review the alert, assign responsible staff, and coordinate response.",
                    'biomedical_engineer': "Please review the alert, investigate the issue, and update maintenance records.",
                    'clinician': "Please review the alert and ensure clinical operations are not affected."
                }
                message += f"\n\nAction Required: {role_actions.get(role, 'Please review and respond to this alert.')}"
                
                try:
                    ok, detail = send_email(user['email'], subject, message)
                    status = 'SENT' if ok else 'PENDING'
                except Exception as e:
                    ok = False
                    detail = str(e)
                    status = 'PENDING'
                
                c.execute('''
                    INSERT INTO notification_queue 
                    (user_id, email, subject, body, status, created_at, sent_at, notification_type, read_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user['id'],
                    user['email'],
                    subject,
                    message,
                    status,
                    now,
                    now if status == 'SENT' else None,
                    'ALERT_CREATED',
                    None
                ))
                
                results.append({
                    'user_id': user['id'],
                    'email': user['email'],
                    'role': role,
                    'status': status
                })
        
        return {
            'recipients': len(results),
            'emails_sent': sum(r['status'] == 'SENT' for r in results),
            'emails_pending': sum(r['status'] == 'PENDING' for r in results),
            'results': results
        }