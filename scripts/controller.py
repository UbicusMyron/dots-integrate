"""Local demonstration of upload -> validate -> grant -> guarded call."""
from pathlib import Path
import uuid

from scripts.admission import BINDING_FIELDS, binding_key, evaluate_admission, valid_binding, matches, IDENTIFIER
from scripts.common import IntakeError, atomic_json, digest, now, read_json
from scripts.runner import dependencies, execute, manifest, runtime, suite_digest
from scripts.store import Store

CONTEXT = {'mode': 'local-demo', 'connections': [], 'scope': 'trusted-synthetic-tools-only'}
FAILED = {'TEST_TIMEOUT', 'OUTPUT_LIMIT', 'INVALID_OUTPUT', 'EXECUTION_FAILED', 'RESULT_MISMATCH'}


class Controller:
    def __init__(self, state, local_demo=False):
        if not local_demo:
            raise IntakeError('CLOUD_ADAPTER_UNAVAILABLE', 'Cloud adapter is not configured; local results cannot grant cloud access')
        self.store = Store(state)

    def initialize(self):
        self.store.initialize()
        return {'mode': 'local-demo', 'entries': []}

    def _records(self):
        records = self.store.records()
        for path, record in records:
            if (not isinstance(record, dict) or type(record.get('workflow_version')) is not int or record.get('workflow_version') != 1
                    or record.get('mode') != 'local-demo' or not valid_binding(record.get('binding'))
                    or not matches(IDENTIFIER, record.get('validation_id'))
                    or path.name != record['validation_id'] + '.json'
                    or type(record.get('attempt')) is not int or record['attempt'] < 1
                    or record.get('state') not in ('pending', 'validating', 'passed', 'failed', 'blocked', 'revoked')):
                raise IntakeError('STATE_INVALID')
        return [r for _, r in records]

    def _evidence_valid(self, entry):
        try:
            expected_ref = f"evidence/{entry['validation_id']}.json"
            if entry['evidence_ref'] != expected_ref:
                return False
            evidence = read_json(self.store.path(expected_ref), 'EVIDENCE_INVALID')
            return (digest(evidence) == entry['evidence_digest'] and evidence['mode'] == 'local-demo'
                    and evidence['binding'] == {k: entry[k] for k in BINDING_FIELDS}
                    and evidence['validation_id'] == entry['validation_id']
                    and evidence['report']['outcome'] == 'passed'
                    and bool(evidence['cases']) and all(c['passed'] is True for c in evidence['cases']))
        except (IntakeError, KeyError, TypeError):
            return False

    def _recover(self):
        registry = self.store.registry()
        records = self._records()
        by_id = {r['validation_id']: r for r in records}
        for record in records:
            if record['state'] in ('pending', 'validating'):
                record.update(state='blocked', reason_code='EXECUTION_INTERRUPTED', updated_at=now())
                self.store.save_record(record)
        valid = []
        for entry in registry['entries']:
            record = by_id.get(entry['validation_id'])
            if (record and record['state'] == 'passed' and binding_key(record['binding']) == binding_key(entry)
                    and self._evidence_valid(entry)):
                valid.append(entry)
            elif record:
                record.update(state='revoked', reason_code='EVIDENCE_INVALID', updated_at=now())
                self.store.save_record(record)
        if len(valid) != len(registry['entries']):
            registry.update(entries=valid, revision=registry['revision'] + 1)
            self.store.save_registry(registry)
        valid_ids = {e['validation_id'] for e in valid}
        for record in records:
            if record['state'] == 'passed' and record['validation_id'] not in valid_ids:
                record.update(state='revoked', reason_code='NOT_ALLOWLISTED', updated_at=now())
                self.store.save_record(record)
        return registry

    def _revoke(self, artifact, operation, reason):
        registry = self.store.registry()
        keep = [e for e in registry['entries'] if (e['artifact_digest'], e['operation']) != (artifact, operation)]
        if len(keep) != len(registry['entries']):
            registry.update(entries=keep, revision=registry['revision'] + 1)
            self.store.save_registry(registry)  # revoke before changing record
        for record in self._records():
            if (record['binding']['artifact_digest'], record['binding']['operation']) == (artifact, operation) and record['state'] == 'passed':
                record.update(state='revoked', reason_code=reason, updated_at=now())
                self.store.save_record(record)

    def _binding(self, artifact, operation):
        root = self.store.verified_snapshot(artifact)
        tool = manifest(root)
        if operation not in tool['operations']:
            raise IntakeError('NOT_ALLOWLISTED')
        config = tool['operations'][operation]
        environment = runtime()
        binding = dict(tool_id=tool['tool_id'], operation=operation, artifact_digest=artifact,
                       runtime_digest=digest(environment), context_digest=digest(CONTEXT), suite_digest=suite_digest(config))
        return root, tool, config, environment, binding

    def upload(self, source):
        with self.store.locked():
            self._recover()
            manifest(source)  # reject malformed input before persisting
            artifact = self.store.snapshot(source)
            tool = manifest(self.store.verified_snapshot(artifact))
            results = [self._validate(artifact, operation) for operation in tool['operations']]
            return {'mode': 'local-demo', 'artifact_digest': artifact, 'results': results}

    def validate(self, artifact, operation):
        with self.store.locked():
            self._recover()
            return {'mode': 'local-demo', 'results': [self._validate(artifact, operation)]}

    def _validate(self, artifact, operation):
        self._revoke(artifact, operation, 'REVALIDATION_REQUESTED')
        root, tool, config, environment, binding = self._binding(artifact, operation)
        validation_id = 'run-' + uuid.uuid4().hex
        previous = [r for r in self._records() if r['binding']['artifact_digest'] == artifact and r['binding']['operation'] == operation]
        record = dict(workflow_version=1, mode='local-demo', validation_id=validation_id,
                      binding=binding, suite=config, attempt=max((r['attempt'] for r in previous), default=0) + 1,
                      state='pending', evidence_ref=None, reason_code=None, updated_at=now())
        self.store.save_record(record)
        dep_results, issues = dependencies(tool['dependencies'])
        self.store.audit('validation_started', 'PENDING', validation_id)
        evidence_ref = f'evidence/{validation_id}.json'
        evidence = dict(mode='local-demo', validation_id=validation_id, binding=binding,
                        environment=environment, cases=[], report=None)
        reason = None
        try:
            if issues:
                raise IntakeError(issues[0]['code'])
            if not config['cases']:
                raise IntakeError('MISSING_TEST_CASE')
            record.update(state='validating', updated_at=now())
            self.store.save_record(record)
            for case in config['cases']:
                actual = execute(root, config, case['input'])
                passed = digest(actual) == digest(case['expected'])
                evidence['cases'].append(dict(input=case['input'], expected=case['expected'], actual=actual, passed=passed))
                if not passed:
                    raise IntakeError('RESULT_MISMATCH')
            if self._binding(artifact, operation)[-1] != binding:
                raise IntakeError('BINDING_MISMATCH')
            record.update(state='passed')
        except IntakeError as error:
            reason = error.code
            record.update(state='failed' if reason in FAILED else 'blocked', reason_code=reason)
        except (OSError, KeyboardInterrupt):
            reason = 'EXECUTION_INTERRUPTED'
            record.update(state='blocked', reason_code=reason)
        trial_status = {'passed': 'passed', 'failed': 'failed', 'blocked': 'blocked'}[record['state']]
        if reason:
            issues.append(dict(code=reason, message='Local validation did not pass', next_step='Inspect the fixed test and retry after resolving the cause'))
        evidence['report'] = dict(schema_version=1, source_ref=str(root), environment_ref='local-demo:' + binding['runtime_digest'],
            coverage=['Local Python adapter and declared exact distribution versions only; not cloud or host-isolation validation'],
            dependencies=dep_results, issues=issues,
            trial=dict(status=trial_status, input_ref=evidence_ref, expected_ref=evidence_ref,
                       result_ref=evidence_ref, evidence=[evidence_ref]),
            outcome='passed' if trial_status == 'passed' else 'blocked')
        atomic_json(self.store.path(evidence_ref), evidence)
        record.update(evidence_ref=evidence_ref, updated_at=now())
        if record['state'] == 'passed':
            registry = self.store.registry()
            entry = dict(binding, validation_id=validation_id, validated_at=now(),
                         evidence_ref=evidence_ref, evidence_digest=digest(evidence))
            registry['entries'].append(entry)
            registry['revision'] += 1
            self.store.save_registry(registry)
        self.store.save_record(record)
        self.store.audit('validation_finished', reason or 'PASSED', validation_id)
        return record

    def call(self, artifact, operation, value):
        with self.store.locked():
            try:
                registry = self._recover()
                root, _, config, _, binding = self._binding(artifact, operation)
                result = evaluate_admission(binding, registry)
                if not result['allowed']:
                    raise IntakeError(result['code'])
                entry = next(e for e in registry['entries'] if e['validation_id'] == result['validation_id'])
                if not self._evidence_valid(entry):
                    self._revoke(artifact, operation, 'EVIDENCE_INVALID')
                    raise IntakeError('EVIDENCE_INVALID')
            except IntakeError as error:
                self.store.audit('invocation_denied', error.code)
                raise
            self.store.audit('invocation_started', 'ADMITTED', entry['validation_id'])
            try:
                output = execute(root, config, value)
                if self._binding(artifact, operation)[-1] != binding:
                    raise IntakeError('BINDING_MISMATCH')
            except IntakeError as error:
                self._revoke(artifact, operation, 'INVOCATION_FAILED')
                self.store.audit('invocation_failed', error.code, entry['validation_id'])
                raise
            self.store.audit('invocation_finished', 'SUCCEEDED', entry['validation_id'])
            return dict(mode='local-demo', validation_id=entry['validation_id'], result=output)

    def revoke(self, artifact, operation):
        with self.store.locked():
            self._recover()
            self.store.verified_snapshot(artifact)
            self._revoke(artifact, operation, 'REVOKED')
            self.store.audit('admission_revoked', 'REVOKED')
            return {'mode': 'local-demo', 'revoked': True}

    def listing(self):
        with self.store.locked():
            registry = self._recover()
            return dict(mode='local-demo', registry=registry, validations=self._records())
