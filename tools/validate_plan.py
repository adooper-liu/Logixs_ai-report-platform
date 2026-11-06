"""Validate the architecture package, not platform runtime functionality.

No business data, services, network or model calls are used.
"""
from __future__ import annotations
import copy
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inside_root(relative):
    path = (ROOT / relative).resolve()
    require(path.is_relative_to(ROOT), f'Path leaves independent project: {relative}')
    return path


def load(path):
    return json.loads(inside_root(path).read_text(encoding='utf-8'))


def validate_proposals(recommendation):
    unique([p['proposal_id'] for p in recommendation['proposals']], 'proposal IDs')
    for proposal in recommendation['proposals']:
        operator = proposal['operator']
        params = proposal['parameters']
        if operator == 'cast_decimal':
            require(isinstance(params['precision'], int) and not isinstance(params['precision'], bool), 'Decimal precision is required')
            require(isinstance(params['scale'], int) and not isinstance(params['scale'], bool), 'Decimal scale is required')
            require(0 <= params['scale'] <= params['precision'] <= 38, 'Invalid decimal precision/scale')
            require(bool(params['locale']), 'Decimal locale must be explicit')
            require(params['format'] is None, 'Decimal cannot carry a date format')
        else:
            require(params['precision'] is None and params['scale'] is None, 'Non-decimal numeric parameters')
            if operator == 'preserve_as_string':
                require(params['format'] is None and params['locale'] is None, 'Preserve must not transform format')
            else:
                require(operator in ('parse_date', 'parse_local_datetime'), 'Unknown operator')
                require(bool(params['format']) and bool(params['locale']), 'Date format and locale must be explicit')
        require(proposal['impact'] == ('preserve' if operator == 'preserve_as_string' else 'type_conversion'), 'Incorrect impact classification')


def validate_load_modes(pipeline):
    for part in pipeline['inputs']:
        mode = part.get('load_mode', pipeline.get('load_mode'))
        require(mode in ('append', 'full_snapshot', 'partition_replace', 'upsert') or not part['required'], 'Missing input load semantics')
        config = part if 'load_mode' in part else pipeline
        if mode in ('full_snapshot', 'partition_replace'):
            require(config.get('scope_required_for_replace') is True, 'Replacement requires explicit scope')
            require(config.get('empty_scope_requires_completeness_evidence') is True, 'Empty replacement requires completeness evidence')
        if mode == 'append':
            require(bool(config.get('idempotency_identity')), 'Append requires identity')



def unique(items, label):
    require(len(items) == len(set(items)), f'Duplicate {label}')


def validate_plan():
    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        raise SystemExit('Install planning dependencies: python -m pip install -r requirements-plan.txt')

    project = load('project.json')
    require(project['status'] == 'architecture_planned', 'Incorrect completion claim')
    for flag in ('runtime_implemented', 'production_ready', 'legacy_runtime_dependency', 'external_ai_calls_performed'):
        require(project[flag] is False, f'Planning package must not claim {flag}')
    require(project['independent_project'] is True, 'Project must be independent')
    require(len(project['layers']) == 3, 'Three platform layers are required')
    require(project['ai']['raw_data_egress_by_default'] is False, 'Raw egress must be off by default')

    for module in project['modules']:
        require(module['phase'] in project['implementation_phases'], 'Unknown implementation phase')
        require(module['status'] == 'planned', 'Do not mark empty modules implemented')
        require(inside_root(module['path']).is_dir(), f'Missing module directory: {module["path"]}')
        require((inside_root(module['path']) / 'README.md').is_file(), f'Missing module boundary: {module["path"]}')

    for relative in project['documents'] + project['design_contracts'] + project['examples']:
        require(inside_root(relative).is_file(), f'Missing referenced file: {relative}')
    for relative in project['documents']:
        path = inside_root(relative)
        content = path.read_text(encoding='utf-8')
        for target in re.findall(r'\]\(([^)]+)\)', content):
            if re.match(r'^[a-z]+://', target) or target.startswith('#'):
                continue
            require(inside_root((path.parent / target.split('#')[0]).relative_to(ROOT)).exists(), f'Broken local link in {relative}: {target}')

    schema = load(project['design_contracts'][0])
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    recommendation = load('examples/synthetic-ai-recommendation.json')
    validator.validate(recommendation)
    require(recommendation['example_only'] is True, 'AI example must be synthetic')
    validate_proposals(recommendation)
    # A schema-valid answer is not execution authorization. Negative fixtures prove
    # that this narrow schema rejects executable code or a direct-apply claim.
    for mutation in ('operator', 'authorization', 'extra_code'):
        bad = copy.deepcopy(recommendation)
        if mutation == 'operator':
            bad['proposals'][0]['operator'] = 'execute_python'
        elif mutation == 'authorization':
            bad['execution_authorized'] = True
        else:
            bad['proposals'][0]['python_code'] = 'untrusted code placeholder'
        require(not validator.is_valid(bad), f'Unsafe schema mutation accepted: {mutation}')

    plan = load('examples/synthetic-platform-plan.json')
    require(plan['example_only'] is True and plan['executable'] is False, 'Example must not claim execution')
    require(plan['contains_real_business_records'] is False, 'No real records in planning examples')
    collections = ('projects', 'streams', 'pipelines', 'models', 'metrics')
    for collection in collections:
        unique([item['id'] for item in plan[collection]], collection)
    projects = {item['id']: item for item in plan['projects']}
    streams = {item['id']: item for item in plan['streams']}
    models = {item['id']: item for item in plan['models']}
    metrics = {item['id']: item for item in plan['metrics']}
    require(len({p['domain'] for p in projects.values()}) >= 2, 'At least two independent domains')
    for stream in streams.values():
        require(stream['project_id'] in projects, 'Unknown stream project')
        require(stream['business_description_required'] is False, 'Descriptions must remain optional')
    for model in models.values():
        for stream_id in model['input_stream_ids']:
            require(streams[stream_id]['project_id'] == model['project_id'], 'Cross-project model input')
        require(model['key_requires_full_validation'] is True, 'Candidate keys need evidence')
    for metric in metrics.values():
        require(models[metric['model_id']]['project_id'] == metric['project_id'], 'Cross-project metric')
    for pipeline in plan['pipelines']:
        validate_load_modes(pipeline)
        require(pipeline['manual_business_review_required'] is False, 'No mandatory review workflow')
        require(pipeline['on_failure'] == 'keep_previous_release', 'Failed run must preserve current release')
        require(pipeline['phase'] in project['implementation_phases'], 'Unknown example delivery phase')
        require(len(pipeline['inputs']) >= 2, 'Examples must not be single-file workflows')
        for part in pipeline['inputs']:
            require(streams[part['stream_id']]['project_id'] == pipeline['project_id'], 'Cross-project input')
        for model_id in pipeline['model_ids']:
            require(models[model_id]['project_id'] == pipeline['project_id'], 'Cross-project pipeline model')
        for metric_id in pipeline['metric_ids']:
            require(metrics[metric_id]['project_id'] == pipeline['project_id'], 'Cross-project pipeline metric')
    for relation in plan['relations']:
        require(models[relation['left_model']]['project_id'] == models[relation['right_model']]['project_id'], 'Cross-project relation')
        require(relation['tests'], 'Relationships need validation tests')

    print('PASS: planning manifests, module boundaries, document links, JSON Schema examples,')
    print('      unsafe-output negative fixtures, cross-project references and two-domain inputs.')
    print('Scope: design-time checks only; no runtime/AI/BI integration was exercised.')
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    try:
        raise SystemExit(validate_plan())
    except (ValueError, KeyError, OSError) as error:
        print(f'FAIL: {error}', file=sys.stderr)
        raise SystemExit(1)
