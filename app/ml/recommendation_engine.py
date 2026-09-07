ROLE_RECOMMENDATIONS = {
 'system_administrator':'Review system governance impact and confirm that the affected facility is responding appropriately.',
 'national_administrator':'Review the alert as part of national equipment oversight and confirm facility action.',
 'national_executive':'Monitor operational impact, equipment availability and the facility response.',
 'facility_manager':'Coordinate the facility response and ensure the affected equipment is safely managed.',
 'biomedical_engineer':'Inspect telemetry and maintenance history, establish technical cause and initiate corrective/preventive maintenance.',
 'maintenance_technician':'Review the equipment and prepare the required inspection, service or corrective maintenance.',
 'clinician':'Observe facility procedures for equipment availability and safe clinical use.'
}

def recommendation_for_role(role, severity, base_recommendation):
    return f'{base_recommendation} {ROLE_RECOMMENDATIONS.get(role, "Follow the applicable facility procedure.")}'
