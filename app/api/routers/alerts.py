# app/api/routers/alerts.py
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from pydantic import BaseModel, Field
from app.core.security import current_user, require_roles, optional_user
from app.core.audit import audit
from app.core.db import db
from app.services.data_service import equipment, scope_filter
from app.services.notification_service import NotificationService

router = APIRouter(prefix='/alerts', tags=['Alerts'])

VALID_SEVERITIES = {'LOW', 'MEDIUM', 'HIGH', 'CRITICAL', 'WARNING', 'INFO'}
VALID_STATUSES = {'OPEN', 'ACKNOWLEDGED', 'IN_PROGRESS', 'RESOLVED', 'CLOSED'}
MANUAL_ROLES = ('system_administrator', 'national_administrator', 'facility_manager', 'biomedical_engineer')

# --- Models ---
class AlertCreate(BaseModel):
    alert_type: str = Field(min_length=1, max_length=100)
    severity: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=200)
    message: str = Field(min_length=1, max_length=5000)
    recommendation: Optional[str] = None
    equipment_id: Optional[str] = None
    facility_id: Optional[str] = None
    status: str = 'OPEN'

class AlertPut(AlertCreate):
    pass

class AlertPatch(BaseModel):
    alert_type: Optional[str] = None
    severity: Optional[str] = None
    title: Optional[str] = None
    message: Optional[str] = None
    recommendation: Optional[str] = None
    equipment_id: Optional[str] = None
    facility_id: Optional[str] = None
    status: Optional[str] = None

class BulkAction(BaseModel):
    alert_ids: List[str]
    action: str  # 'acknowledge', 'resolve', 'close'

# --- Helper Functions ---
def _norm(v):
    return str(v or '').strip().upper()

def _validate_scope(u, facility_id):
    if not facility_id:
        raise HTTPException(400, 'facility_id is required for alerts')
    if str(u.get('scope_type')).lower() != 'national' and str(u.get('scope_id')) != str(facility_id):
        raise HTTPException(403, 'Alert facility is outside your access scope')
    with db() as c:
        h = c.execute('SELECT facility_id, status FROM hospitals WHERE facility_id=?', (facility_id,)).fetchone()
    if not h and not any(str(x.get('facility_id')) == str(facility_id) for x in equipment()):
        raise HTTPException(404, f"Facility '{facility_id}' does not exist")
    if h and str(h['status']).upper() != 'ACTIVE':
        raise HTTPException(400, 'Facility is not active')

def _validate_equipment(equipment_id, facility_id):
    if not equipment_id:
        return
    matches = [x for x in equipment() if str(x.get('equipment_id')) == str(equipment_id) and str(x.get('facility_id')) == str(facility_id)]
    if not matches:
        raise HTTPException(400, f"Equipment '{equipment_id}' is not registered at facility '{facility_id}'")

def _create_alert(data, u, source='MANUAL'):
    facility_id = data.facility_id
    _validate_scope(u, facility_id)
    _validate_equipment(data.equipment_id, facility_id)
    
    severity = _norm(data.severity)
    status = _norm(data.status)
    
    if severity not in VALID_SEVERITIES:
        raise HTTPException(400, f'Invalid severity. Allowed: {sorted(VALID_SEVERITIES)}')
    if status not in VALID_STATUSES:
        raise HTTPException(400, f'Invalid status. Allowed: {sorted(VALID_STATUSES)}')
    
    now = datetime.now(timezone.utc).isoformat()
    aid = f'ALT-{uuid4().hex[:12].upper()}'
    
    with db() as c:
        c.execute('''
            INSERT INTO alerts 
            (id, alert_type, source, severity, title, message, recommendation, 
             equipment_id, facility_id, status, created_by, created_at, updated_at, resolved_at, resolved_by)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            aid, data.alert_type.strip(), source, severity, data.title.strip(), 
            data.message.strip(), data.recommendation, data.equipment_id, 
            data.facility_id, status, u['id'], now, now, 
            now if status in {'RESOLVED', 'CLOSED'} else None,
            u['id'] if status in {'RESOLVED', 'CLOSED'} else None
        ))
        alert = dict(c.execute('SELECT * FROM alerts WHERE id=?', (aid,)).fetchone())
    
    audit(u, 'CREATE_ALERT', 'alert', aid, {
        'source': source, 
        'severity': severity, 
        'facility_id': facility_id
    })
    
    # Send notifications using NotificationService
    notifications = NotificationService.notify_alert_created(alert, u)
    
    return {'alert': alert, 'notifications': notifications}

def _transition(alert_id, status, u):
    """Transition alert to a new status"""
    with db() as c:
        row = c.execute('SELECT * FROM alerts WHERE id=?', (alert_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Alert not found')
        
        if str(row['facility_id']) != str(u.get('scope_id')) and str(u.get('scope_type')) != 'national':
            raise HTTPException(403, 'Alert is outside your access scope')
        
        # Validate status transition
        current_status = row['status']
        valid_transitions = {
            'OPEN': ['ACKNOWLEDGED', 'RESOLVED'],
            'ACKNOWLEDGED': ['IN_PROGRESS', 'RESOLVED'],
            'IN_PROGRESS': ['RESOLVED'],
            'RESOLVED': ['CLOSED'],
            'CLOSED': []
        }
        
        if status not in valid_transitions.get(current_status, []):
            raise HTTPException(
                400, 
                f'Invalid status transition from {current_status} to {status}. '
                f'Allowed: {valid_transitions.get(current_status, [])}'
            )
        
        now = datetime.now(timezone.utc).isoformat()
        
        c.execute('''
            UPDATE alerts 
            SET status=?, updated_at=?, resolved_at=?, resolved_by=? 
            WHERE id=?
        ''', (
            status, now,
            now if status == 'RESOLVED' else row['resolved_at'],
            u['id'] if status == 'RESOLVED' else row['resolved_by'],
            alert_id
        ))
        alert = dict(c.execute('SELECT * FROM alerts WHERE id=?', (alert_id,)).fetchone())
    
    audit(u, f'{status}_ALERT', 'alert', alert_id)
    
    # Send notification for status change
    if status in ['RESOLVED', 'CLOSED']:
        # You can add additional notification here if needed
        pass
    
    return alert

# --- Endpoints ---

@router.get('')
def get_alerts(
    u=Depends(optional_user),
    status: Optional[str] = Query(None, description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    source: Optional[str] = Query(None, description="Filter by source"),
    facility_id: Optional[str] = Query(None, description="Filter by facility"),
    equipment_id: Optional[str] = Query(None, description="Filter by equipment"),
    limit: int = Query(100, description="Limit results"),
    offset: int = Query(0, description="Offset for pagination")
):
    """Get alerts with filtering and pagination"""
    with db() as c:
        clauses = []
        args = []
        
        if status:
            clauses.append('status=?')
            args.append(_norm(status))
        if severity:
            clauses.append('severity=?')
            args.append(_norm(severity))
        if source:
            clauses.append('source=?')
            args.append(_norm(source))
        if facility_id:
            clauses.append('facility_id=?')
            args.append(facility_id)
        if equipment_id:
            clauses.append('equipment_id=?')
            args.append(equipment_id)
        
        where_clause = (' WHERE ' + ' AND '.join(clauses)) if clauses else ''
        sql = f'SELECT * FROM alerts{where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?'
        args.extend([limit, offset])
        
        rows = [dict(r) for r in c.execute(sql, args).fetchall()]
    
    rows = scope_filter(rows, u)
    audit(u, 'VIEW_ALERTS', 'alert', details={
        'filters': {
            'status': status, 'severity': severity, 'source': source,
            'facility_id': facility_id, 'equipment_id': equipment_id
        },
        'limit': limit, 'offset': offset
    })
    return rows

@router.get('/stats')
def get_alert_stats(
    u=Depends(optional_user),
    facility_id: Optional[str] = Query(None, description="Filter by facility"),
    days: int = Query(30, description="Number of days to look back")
):
    """Get alert statistics"""
    with db() as c:
        where_clause = "1=1"
        params = []
        
        if facility_id:
            where_clause += " AND facility_id=?"
            params.append(facility_id)
        
        if days > 0:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            where_clause += " AND created_at >= ?"
            params.append(cutoff)
        
        alerts = [dict(r) for r in c.execute(
            f"SELECT * FROM alerts WHERE {where_clause}",
            params
        ).fetchall()]
    
    alerts = scope_filter(alerts, u)
    
    total = len(alerts)
    open_count = len([a for a in alerts if a.get('status') == 'OPEN'])
    acknowledged = len([a for a in alerts if a.get('status') == 'ACKNOWLEDGED'])
    in_progress = len([a for a in alerts if a.get('status') == 'IN_PROGRESS'])
    resolved = len([a for a in alerts if a.get('status') == 'RESOLVED'])
    closed = len([a for a in alerts if a.get('status') == 'CLOSED'])
    
    critical = len([a for a in alerts if a.get('severity') == 'CRITICAL'])
    high = len([a for a in alerts if a.get('severity') == 'HIGH'])
    medium = len([a for a in alerts if a.get('severity') == 'MEDIUM'])
    low = len([a for a in alerts if a.get('severity') == 'LOW'])
    info = len([a for a in alerts if a.get('severity') == 'INFO'])
    
    return {
        'summary': {
            'total': total,
            'open': open_count,
            'acknowledged': acknowledged,
            'in_progress': in_progress,
            'resolved': resolved,
            'closed': closed,
            'critical': critical,
            'high': high,
            'medium': medium,
            'low': low,
            'info': info
        },
        'generated_at': datetime.now(timezone.utc).isoformat()
    }

@router.get('/equipment/{equipment_id}')
def equipment_alerts(
    equipment_id: str,
    limit: int = Query(100, description="Limit results"),
    u=Depends(optional_user)
):
    """Get alerts for a specific equipment"""
    with db() as c:
        rows = [dict(r) for r in c.execute(
            'SELECT * FROM alerts WHERE equipment_id=? ORDER BY created_at DESC LIMIT ?',
            (equipment_id, limit)
        ).fetchall()]
    
    rows = scope_filter(rows, u)
    audit(u, 'VIEW_ALERTS', 'equipment', equipment_id)
    return rows

@router.get('/{alert_id}')
def get_alert(alert_id: str, u=Depends(optional_user)):
    """Get a single alert by ID"""
    with db() as c:
        row = c.execute('SELECT * FROM alerts WHERE id=?', (alert_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Alert not found')
        alert = dict(row)
        alert_scope = scope_filter([alert], u)
        if not alert_scope:
            raise HTTPException(403, 'Alert is outside your access scope')
        audit(u, 'VIEW_ALERT', 'alert', alert_id)
        return alert

@router.post('', status_code=201)
def create_alert(data: AlertCreate, u=Depends(require_roles(*MANUAL_ROLES))):
    """Create a new manual alert"""
    return _create_alert(data, u, 'MANUAL')

@router.put('/{alert_id}')
def replace_alert(
    alert_id: str,
    data: AlertPut,
    u=Depends(require_roles(*MANUAL_ROLES))
):
    """Full replacement of an alert"""
    with db() as c:
        row = c.execute('SELECT * FROM alerts WHERE id=?', (alert_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Alert not found')
        if row['source'] != 'MANUAL':
            raise HTTPException(403, 'System-generated alerts cannot be edited')
        
        _validate_scope(u, data.facility_id)
        _validate_equipment(data.equipment_id, data.facility_id)
        
        severity = _norm(data.severity)
        status = _norm(data.status)
        
        if severity not in VALID_SEVERITIES or status not in VALID_STATUSES:
            raise HTTPException(400, 'Invalid severity or status')
        
        now = datetime.now(timezone.utc).isoformat()
        
        c.execute('''
            UPDATE alerts 
            SET alert_type=?, severity=?, title=?, message=?, recommendation=?,
                equipment_id=?, facility_id=?, status=?, updated_at=?,
                resolved_at=?, resolved_by=? 
            WHERE id=?
        ''', (
            data.alert_type.strip(), severity, data.title.strip(), 
            data.message.strip(), data.recommendation, data.equipment_id,
            data.facility_id, status, now,
            now if status in {'RESOLVED', 'CLOSED'} else None,
            u['id'] if status in {'RESOLVED', 'CLOSED'} else None,
            alert_id
        ))
        alert = dict(c.execute('SELECT * FROM alerts WHERE id=?', (alert_id,)).fetchone())
    
    audit(u, 'UPDATE_ALERT', 'alert', alert_id, {'method': 'PUT'})
    return alert

@router.patch('/{alert_id}')
def patch_alert(
    alert_id: str,
    data: AlertPatch,
    u=Depends(require_roles(*MANUAL_ROLES))
):
    """Partial update of an alert"""
    with db() as c:
        row = c.execute('SELECT * FROM alerts WHERE id=?', (alert_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Alert not found')
        if row['source'] != 'MANUAL':
            raise HTTPException(403, 'System-generated alerts cannot be edited')
        
        current = dict(row)
        merged = {
            k: (getattr(data, k) if getattr(data, k) is not None else current[k]) 
            for k in ['alert_type', 'severity', 'title', 'message', 'recommendation', 
                      'equipment_id', 'facility_id', 'status']
        }
        payload = AlertPut(**merged)
        result = replace_alert(alert_id, payload, u)
        audit(u, 'PATCH_ALERT', 'alert', alert_id)
        return result

@router.patch('/{alert_id}/acknowledge')
def acknowledge_alert(alert_id: str, u=Depends(require_roles(*MANUAL_ROLES))):
    """Acknowledge an alert"""
    return _transition(alert_id, 'ACKNOWLEDGED', u)

@router.patch('/{alert_id}/resolve')
def resolve_alert(alert_id: str, u=Depends(require_roles(*MANUAL_ROLES))):
    """Resolve an alert"""
    return _transition(alert_id, 'RESOLVED', u)

@router.patch('/{alert_id}/close')
def close_alert(alert_id: str, u=Depends(require_roles(*MANUAL_ROLES))):
    """Close a resolved alert"""
    with db() as c:
        row = c.execute('SELECT * FROM alerts WHERE id=?', (alert_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Alert not found')
        if row['status'] != 'RESOLVED':
            raise HTTPException(400, 'Only resolved alerts can be closed')
    
    return _transition(alert_id, 'CLOSED', u)

@router.post('/bulk')
def bulk_action(
    action_data: BulkAction,
    u=Depends(require_roles(*MANUAL_ROLES))
):
    """Perform bulk actions on multiple alerts"""
    if action_data.action not in ['acknowledge', 'resolve', 'close']:
        raise HTTPException(400, f'Invalid action. Allowed: acknowledge, resolve, close')
    
    results = []
    errors = []
    
    for alert_id in action_data.alert_ids:
        try:
            if action_data.action == 'acknowledge':
                result = _transition(alert_id, 'ACKNOWLEDGED', u)
            elif action_data.action == 'resolve':
                result = _transition(alert_id, 'RESOLVED', u)
            elif action_data.action == 'close':
                result = _transition(alert_id, 'CLOSED', u)
            results.append({'alert_id': alert_id, 'status': 'success'})
        except Exception as e:
            errors.append({'alert_id': alert_id, 'error': str(e)})
    
    audit(u, f'BULK_{action_data.action.upper()}_ALERTS', 'alert', details={
        'success_count': len(results),
        'error_count': len(errors)
    })
    
    return {
        'action': action_data.action,
        'successful': len(results),
        'failed': len(errors),
        'results': results,
        'errors': errors
    }

@router.delete('/{alert_id}')
def delete_alert(alert_id: str, u=Depends(require_roles(*MANUAL_ROLES))):
    """Delete an alert (manual alerts only)"""
    with db() as c:
        row = c.execute('SELECT * FROM alerts WHERE id=?', (alert_id,)).fetchone()
        if not row:
            raise HTTPException(404, 'Alert not found')
        if row['source'] != 'MANUAL':
            raise HTTPException(403, 'System-generated alerts cannot be deleted')
        if str(u.get('scope_type')) != 'national' and str(row['facility_id']) != str(u.get('scope_id')):
            raise HTTPException(403, 'Alert is outside your access scope')
        c.execute('DELETE FROM alerts WHERE id=?', (alert_id,))
    
    audit(u, 'DELETE_ALERT', 'alert', alert_id)
    return {'message': 'Alert deleted successfully', 'alert_id': alert_id}

@router.delete('/bulk')
def bulk_delete_alerts(
    alert_ids: List[str] = Query(..., description="List of alert IDs to delete"),
    u=Depends(require_roles('system_administrator', 'national_administrator'))
):
    """Delete multiple alerts (system admins only)"""
    deleted = []
    errors = []
    
    for alert_id in alert_ids:
        try:
            with db() as c:
                row = c.execute('SELECT * FROM alerts WHERE id=?', (alert_id,)).fetchone()
                if not row:
                    errors.append({'alert_id': alert_id, 'error': 'Not found'})
                    continue
                if row['source'] != 'MANUAL':
                    errors.append({'alert_id': alert_id, 'error': 'System alerts cannot be deleted'})
                    continue
                c.execute('DELETE FROM alerts WHERE id=?', (alert_id,))
                deleted.append(alert_id)
        except Exception as e:
            errors.append({'alert_id': alert_id, 'error': str(e)})
    
    audit(u, 'BULK_DELETE_ALERTS', 'alert', details={
        'deleted_count': len(deleted),
        'error_count': len(errors)
    })
    
    return {
        'deleted': deleted,
        'deleted_count': len(deleted),
        'errors': errors,
        'error_count': len(errors)
    }

@router.get('/resolved/count')
def get_resolved_count(
    facility_id: Optional[str] = Query(None, description="Filter by facility"),
    days: int = Query(30, description="Number of days to look back"),
    u=Depends(optional_user)
):
    """Get count of resolved alerts in a time period"""
    with db() as c:
        query = "SELECT COUNT(*) as count FROM alerts WHERE status IN ('RESOLVED', 'CLOSED')"
        params = []
        
        if facility_id:
            query += " AND facility_id=?"
            params.append(facility_id)
        
        if days > 0:
            cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
            query += " AND resolved_at >= ?"
            params.append(cutoff)
        
        row = c.execute(query, params).fetchone()
    
    return {'resolved_count': row['count'] if row else 0}