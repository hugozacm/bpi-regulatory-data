"""Complete output dictionary; uses actual columns and the build's saved mapping."""


def build_dictionary(cols, dictionary):
    derived = {}
    for field in dictionary['fields']:
        for name in ([field['name']] if field['type'] == 'stock' else [field['name'] + '_ytd', field['name'] + '_quarter']):
            derived[name] = field
    dictionary_rows = []
    core_fields = {
        'total_assets': ('BHCK2170 / ASSET', 'Quarter-end total assets; source basis identifies the reporting perimeter'),
        'total_equity': ('BHCT3210 / EQ', 'Y-9C holding-company equity or bank-reported equity; not fully harmonised'),
        'total_loans': ('BHCK2122', 'Y-9C loans net of unearned income; not populated from bank net-allowance loans'),
        'loans_net_allowances': ('LNLSNET', 'FDIC bank loans net of allowances; separate definition'),
        'total_deposits': ('BHDM6631+BHDM6636+BHFN6631+BHFN6636 / DEP', 'Strict component sum or FDIC bank aggregate'),
        'net_income_ytd': ('BHCK4340', 'Reported holder YTD; bank-only historical YTD withheld'),
        'net_income_quarter': ('BHCK4340 / NETINC', 'Q1 direct or adjacent YTD difference; uncertain quarter flows withheld'),
        'bank_member_net_income_ytd': ('NETINC', 'Current members YTD evidence; not historical group YTD'),
        'top_rssd': ('NIC ID_RSSD_PARENT / ID_RSSD_OFFSPRING', 'Highest dated control root; not independently verified institution classification'),
        'entity_key': ('TOP_RSSD_<top_rssd>', 'Stable root identifier, not a retroactive merger identifier'),
        'report_date': ('RSSD9999 / REPDTE', 'Quarter-end date YYYYMMDD'),
        'bank_count': ('Ownership ledger', 'Number of assigned bank records; not proof of complete group membership'),
        'basis': ('Pipeline selection', 'CONSOLIDATED_Y9C or BANK_ONLY_AGGREGATE; independent candidates use the latter basis'),
        'name': ('RSSD9017 / NAMEHCR / NAME', 'May be absent when no verified root name is available'),
        'release_status': ('MVP packaging', 'MVP_V1_RESEARCH_DRAFT; not financial certification'),
        'coverage_note': ('Pipeline review', 'Reporting perimeter and classification limitations'),
        'nested_bank_overlap': ('Dated NIC graph', 'Nested reporting banks detected; aggregate bank values withheld'),
        'flow_perimeter_review': ('NIC control dates and transformations', 'Uncertain quarter flows withheld in MVP; reported YTD evidence retained'),
        'classification_status': ('Pipeline review', 'Institution types not independently verified'),
        'primary_source': ('Pipeline selection', 'FR_Y9C or FDIC_BANK_ONLY'),
    }
    for field in ('DEP', 'DEPDOM', 'DEPFOR', 'DEPIDOM', 'DEPNIDOM'):
        core_fields['bank_sum_' + field] = (field, 'Strict matched-bank-perimeter sum; separate from consolidated deposits')
    for name in cols:
        f = derived.get(name, {})
        dictionary_rows.append({'column': name, 'unit': 'USD_thousands' if name in derived or name in {
            'total_assets', 'total_equity', 'total_loans', 'loans_net_allowances', 'total_deposits',
            'net_income_ytd', 'net_income_quarter', 'bank_member_net_income_ytd'} or name.startswith('bank_sum_') else 'metadata',
            'source_field': f.get('field', core_fields.get(name, ('', ''))[0]), 'fdic_equivalent': f.get('fdic') or '',
            'schedule': f.get('schedule', ''), 'item': f.get('item', ''),
            'measurement': 'quarterly_flow' if name.endswith('_quarter') else f.get('type',
                'stock' if name in {'total_assets', 'total_equity', 'total_loans', 'loans_net_allowances', 'total_deposits'} or name.startswith('bank_sum_') else
                'YTD_flow' if name in {'net_income_ytd', 'bank_member_net_income_ytd'} else 'metadata'),
            'notes': f.get('reporting_note', core_fields.get(name, ('', 'See MVP_V1.md'))[1])})
    for entry in dictionary_rows:
        name=entry['column']
        entry['label']=name.replace('_',' ').capitalize()
        entry['missingness']='Blank means unavailable, withheld or not reported; never implicitly zero.'
        if name.endswith('_quarter'):
            entry['calculation']='Q1 reported YTD; Q2–Q4 current YTD minus compatible prior-quarter YTD. Withheld for missing prior inputs or uncertain reporting perimeter.'
        elif name.endswith('_ytd'):
            entry['calculation']='Reported year-to-date value where available; bank-member sums are current-perimeter evidence, not historical group YTD.'
        elif entry['measurement']=='stock':
            entry['calculation']='Quarter-end reported balance or strict matched-bank sum; not differenced.'
        else:
            entry['calculation']=entry['notes']
    if len(dictionary_rows)!=len(set(cols)) or any(not e['notes'] for e in dictionary_rows):
        raise ValueError('Incomplete or duplicate output dictionary')
    return dictionary_rows
