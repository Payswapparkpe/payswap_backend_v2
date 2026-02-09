"""
Utility to load and parse DLT templates from CSV
"""
import csv
import os
from typing import List, Dict, Optional
from django.conf import settings


def load_dlt_templates() -> List[Dict[str, str]]:
    """
    Load DLT templates from CSV file
    
    Returns:
        List of template dictionaries with keys: name, dlt_id, header, content, communication_type
    """
    templates = []
    csv_path = os.path.join(settings.BASE_DIR, 'DLT', 'template-data.csv')
    
    if not os.path.exists(csv_path):
        return templates
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Clean DLT ID (remove quotes and apostrophe)
                dlt_id = row.get('Template DLT ID', '').strip().strip("'").strip('"')
                template_name = row.get('Template Name', '').strip()
                template_content = row.get('Template Content', '').strip()
                header = row.get('Header', 'PYSWAP').strip()
                communication_type = row.get('Communication Type', '').strip()
                
                if dlt_id and template_name and template_content:
                    # Count number of variables in template
                    var_count = template_content.count('{#var#}')
                    
                    templates.append({
                        'name': template_name,
                        'dlt_id': dlt_id,
                        'header': header,
                        'content': template_content,
                        'communication_type': communication_type,
                        'var_count': var_count
                    })
    except Exception as e:
        print(f"Error loading templates: {str(e)}")
    
    return templates


def get_template_by_name(template_name: str) -> Optional[Dict[str, str]]:
    """
    Get a specific template by name
    
    Args:
        template_name: Name of the template
        
    Returns:
        Template dict or None if not found
    """
    templates = load_dlt_templates()
    for template in templates:
        if template['name'] == template_name:
            return template
    return None


def get_template_by_dlt_id(dlt_id: str) -> Optional[Dict[str, str]]:
    """
    Get a specific template by DLT ID
    
    Args:
        dlt_id: DLT ID of the template
        
    Returns:
        Template dict or None if not found
    """
    templates = load_dlt_templates()
    for template in templates:
        if template['dlt_id'] == dlt_id:
            return template
    return None
