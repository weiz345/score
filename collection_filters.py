"""Source-backed education filtering, with no age or demographic inference."""
import json
from pathlib import Path
from urllib.parse import urlsplit

RULES = json.loads((Path(__file__).resolve().parent / 'collection_rules.json').read_text())


def education_eligibility(record):
    if not RULES.get('education_filter_enabled', True):
        return dict(eligible=True, education_filter_applied=False, age_verified=False)
    if not isinstance(record, dict):
        return dict(eligible=False, reason='No source-backed undergraduate completion record.')
    education = record.get('education', [])
    if not isinstance(education, list):
        return dict(eligible=False, reason='Education must be a list of source-backed records.')
    for item in education:
        if not isinstance(item, dict):
            continue
        if item.get('degree_level') != 'undergraduate' or item.get('completion_status') != 'completed':
            continue
        year = item.get('completion_year')
        if type(year) is not int:
            continue
        source = item.get('source_url')
        if not isinstance(source, str):
            continue
        parsed = urlsplit(source)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            continue
        if RULES['undergraduate_completion_year_min'] <= year <= RULES['undergraduate_completion_year_max']:
            return dict(eligible=True, undergraduate_completion_year=year,
                        education_source=source, age_verified=False)
    return dict(eligible=False, reason='No documented completed undergraduate degree in 2020–2025. Age is not inferred.')
