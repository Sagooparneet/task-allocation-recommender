"""Read-only, supervisor-owned reports over existing application records."""
from datetime import date, datetime, time, timedelta, timezone
import re

from sqlalchemy import func, or_

from app.extensions import db
from app.models import Task, TaskAssignment
from app.services.worker_directory import directory_names


def parse_report_dates(arguments, today=None):
    today = today or kenya_now().date()
    values = {key: arguments.get(key, '').strip()[:32] for key in ('start_date', 'end_date')}
    parsed = {}
    errors = {}
    for key, value in values.items():
        if not value:
            continue
        try:
            if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
                raise ValueError('Invalid date')
            parsed[key] = date.fromisoformat(value)
            if parsed[key] > today:
                errors[key] = 'Choose today or an earlier date.'
        except ValueError:
            errors[key] = 'Enter a valid date in day, month and year order using the date field.'
    if not errors and len(parsed) == 2 and parsed['start_date'] > parsed['end_date']:
        errors['end_date'] = 'Choose an end date on or after the start date.'
    return values, parsed, errors


def kenya_now():
    return datetime.now(timezone(timedelta(hours=3))).replace(tzinfo=None)


def build_report(supervisor_id, boundaries, page_number=1, breakdown="", category=""):
    query = Task.query.filter(Task.supervisor_id == supervisor_id)
    # created_at is legacy, timezone-naive server-local time. Filter its recorded
    # calendar date without inventing a timezone or rewriting historical rows.
    # Bound datetimes work on both SQLite and PostgreSQL (no dialect date casts).
    if boundaries.get('start_date'):
        query = query.filter(Task.created_at >= datetime.combine(boundaries['start_date'], time.min))
    if boundaries.get('end_date'):
        query = query.filter(Task.created_at <= datetime.combine(boundaries['end_date'], time.max))
    grouped = dict(query.with_entities(Task.status, func.count(Task.id)).group_by(Task.status).all())
    total = sum(grouped.values())
    counts = {
        'total': total,
        'waiting': grouped.get('Pending', 0),
        'assigned': grouped.get('Assigned', 0),
        'in_progress': grouped.get('In progress', 0),
        'completed': grouped.get('Completed', 0),
    }
    counts['other'] = total - sum(counts[key] for key in ('waiting', 'assigned', 'in_progress', 'completed'))
    # Graphs use the complete filtered query, never just the visible table page.
    priority_counts = dict(query.with_entities(Task.priority, func.count(Task.id))
                           .group_by(Task.priority).all())
    priorities = [(key, priority_counts.get(key, 0)) for key in ('High', 'Medium', 'Low')]
    unclassified = total - sum(value for _, value in priorities)
    if unclassified:
        priorities.append(('Other / not recorded', unclassified))
    statuses = [(label, counts[key]) for key, label in (
        ('waiting', 'Waiting'), ('assigned', 'Assigned'),
        ('in_progress', 'In progress'), ('completed', 'Completed'))]
    if counts['other']:
        statuses.append(('Other status', counts['other']))
    def chart_rows(items):
        return [{'label': label, 'count': value,
                 'percent': round(value * 100 / total, 1) if total else 0}
                for label, value in items]
    charts = {'status': chart_rows(statuses), 'priority': chart_rows(priorities)}
    # SVG geometry uses exact proportions; displayed percentages are rounded.
    for key, rows in charts.items():
        offset = 0
        for index, row in enumerate(rows):
            share = row['count'] * 100 / total if total else 0
            row.update(arc=share, gap=100-share, offset=-offset, colour=index)
            row['value'] = ('Pending' if row['label'] == 'Waiting' else
                            'other' if row['label'].startswith('Other') else row['label'])
            offset += share
    known_statuses = ('Pending', 'Assigned', 'In progress', 'Completed')
    known_priorities = ('High', 'Medium', 'Low')
    allowed = {'status': known_statuses + ('other',), 'priority': known_priorities + ('other',)}
    if (breakdown or category) and (breakdown not in allowed or category not in allowed[breakdown]):
        raise ValueError('Unsupported report selection')
    table_query = query
    selection_label = ''
    if breakdown:
        column = Task.status if breakdown == 'status' else Task.priority
        known = known_statuses if breakdown == 'status' else known_priorities
        table_query = query.filter(or_(column.notin_(known), column.is_(None))) if category == 'other' else query.filter(column == category)
        selection_label = ('Other status' if breakdown == 'status' else 'Other / not recorded') if category == 'other' else ('Waiting' if category == 'Pending' else category)
    now = kenya_now()
    counts['overdue'] = query.filter(or_(Task.status != 'Completed', Task.status.is_(None)),
                                    Task.deadline < now).count()
    page = table_query.order_by(Task.created_at.desc(), Task.id.desc()).paginate(
        page=page_number, per_page=10, error_out=False)
    workers = {}
    task_ids = [task.id for task in page.items]
    if task_ids:
        assignments = TaskAssignment.query.join(Task).filter(
            Task.supervisor_id == supervisor_id,
            TaskAssignment.supervisor_id == supervisor_id,
            TaskAssignment.task_id.in_(task_ids),
        ).order_by(TaskAssignment.id).all()
        names = directory_names() if assignments else {}
        seen = set()
        for assignment in assignments:
            pair = (assignment.task_id, assignment.agent_id)
            if pair not in seen:
                workers.setdefault(assignment.task_id, []).append(
                    names.get(assignment.agent_id, 'Worker record unavailable'))
                seen.add(pair)
    return {'counts': counts, 'page': page, 'workers': workers, 'now': now, 'charts': charts,
            'breakdown': breakdown, 'category': category, 'selection_label': selection_label}
