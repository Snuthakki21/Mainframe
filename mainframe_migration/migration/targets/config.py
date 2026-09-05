"""Read the single target choice without guessing a language or cloud service.

Only names of environment variables are stored here, never connection secrets.
Language and database choices are independent. Unknown keys are errors: a typo
must not cause a run against the previous database by accident.
"""
from pathlib import Path
import json
import re
from migration.common import Blocked

LANGUAGES = {'python', 'java', 'dotnet'}
DATABASES = {'sqlite', 'oracle', 'bigquery'}
DEFAULTS = Path(__file__).resolve().parents[2] / 'target.json'

def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Blocked(f'Duplicate configuration key: {key}.', 'TARGET_CONFIG')
        result[key] = value
    return result

def _keys(value, allowed, description):
    if not isinstance(value, dict):
        raise Blocked(f'{description} must be an object.', 'TARGET_CONFIG')
    extra = set(value) - set(allowed)
    if extra:
        raise Blocked(f'Unknown {description} key(s): {", ".join(sorted(extra))}.', 'TARGET_CONFIG')

def load_target(path: Path) -> dict:
    """Validate a target file before any target artifacts or connections are created."""
    try:
        target = json.loads(path.read_text(encoding='utf-8-sig'), object_pairs_hook=_object)
    except (OSError, ValueError) as exc:
        raise Blocked(f'Cannot read target configuration: {exc}', 'TARGET_CONFIG') from exc
    _keys(target, {'schema_version','language','database','versions','validation','connections','dependencies'}, 'target')
    if target.get('schema_version') != 1:
        raise Blocked('target.json requires schema_version 1.', 'TARGET_CONFIG')
    language = str(target.get('language','')).lower().strip()
    language = {'.net':'dotnet', 'c#':'dotnet', 'csharp':'dotnet'}.get(language,language)
    database = str(target.get('database','')).lower().strip()
    if language not in LANGUAGES:
        raise Blocked('language must be python, java, or dotnet (C#). No fallback is made.', 'TARGET_CONFIG')
    if database not in DATABASES:
        raise Blocked('database must be sqlite, oracle, or bigquery. GCP is a cloud platform; select bigquery explicitly.', 'TARGET_CONFIG')
    target['language'], target['database'] = language, database
    versions = target.setdefault('versions', {'java_release':17,'dotnet_framework':'net10.0'})
    _keys(versions, {'java_release','dotnet_framework'}, 'versions')
    if versions.get('java_release',17) not in {17,21,25}:
        raise Blocked('java_release must be one of the explicitly supported releases: 17, 21, 25.', 'TARGET_CONFIG')
    if versions.get('dotnet_framework','net10.0') not in {'net8.0','net9.0','net10.0'}:
        raise Blocked('dotnet_framework must be net8.0, net9.0, or net10.0; select the approved installed SDK.', 'TARGET_CONFIG')
    versions.setdefault('java_release',17);versions.setdefault('dotnet_framework','net10.0')
    validation = target.setdefault('validation', {'run_local':True})
    _keys(validation, {'run_local'}, 'validation')
    if type(validation.get('run_local',True)) is not bool:
        raise Blocked('validation.run_local must be true or false.', 'TARGET_CONFIG')
    conns=target.setdefault('connections',{})
    _keys(conns, {'oracle','bigquery'}, 'connections')
    allowed={'oracle':{'dsn_env','user_env','password_env'},'bigquery':{'project_env','dataset_env','location_env','token_env'}}
    for kind,config in conns.items():
        _keys(config, allowed[kind], kind+' connection')
        for value in config.values():
            if not isinstance(value,str) or not re.fullmatch(r'[A-Z][A-Z0-9_]*',value):
                raise Blocked('Connection values must name environment variables, not contain secrets or URLs.', 'TARGET_CONFIG')
    deps=target.setdefault('dependencies',{})
    _keys(deps, {'dotnet_sqlite','dotnet_oracle','java_sqlite','java_oracle','python_oracle'}, 'dependencies')
    for value in deps.values():
        if not isinstance(value,str) or not re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,4}',value):
            raise Blocked('Dependency versions must be explicit numeric versions, not latest or wildcards.', 'TARGET_CONFIG')
    return target

def target_identity(target: dict) -> str:
    """Keep each language/database pair in its own artifact namespace."""
    return target['language']+'-'+target['database']
