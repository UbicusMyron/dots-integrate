import copy
import unittest

from scripts.admission import BINDING_FIELDS, evaluate_admission, valid_registry


def fixture():
    binding = dict(tool_id='demo', operation='preview', artifact_digest='a'*64,
                   runtime_digest='b'*64, context_digest='c'*64, suite_digest='d'*64)
    entry = dict(binding, validation_id='run-001', validated_at='2026-10-12T12:00:00+08:00',
                 evidence_ref='evidence/run-001.json', evidence_digest='e'*64)
    return binding, dict(schema_version=1, revision=1, entries=[entry])


class AdmissionTests(unittest.TestCase):
    def test_exact_binding_and_no_mutation(self):
        binding, registry = fixture()
        original = copy.deepcopy(registry)
        self.assertEqual(evaluate_admission(binding, registry), dict(allowed=True, code='ADMITTED', validation_id='run-001'))
        self.assertEqual(registry, original)
        registry['entries'].clear()
        self.assertEqual(evaluate_admission(binding, registry)['code'], 'NOT_ALLOWLISTED')

    def test_every_binding_field_prevents_reuse(self):
        binding, registry = fixture()
        for field in BINDING_FIELDS:
            with self.subTest(field=field):
                other = dict(binding)
                other[field] = 'other' if field in ('tool_id', 'operation') else 'f'*64
                self.assertFalse(evaluate_admission(other, registry)['allowed'])

    def test_precedence_and_unknown(self):
        binding, registry = fixture()
        self.assertEqual(evaluate_admission({}, None)['code'], 'INVALID_BINDING')
        self.assertEqual(evaluate_admission(binding, None)['code'], 'REGISTRY_UNAVAILABLE')
        self.assertEqual(evaluate_admission(binding, {})['code'], 'REGISTRY_INVALID')
        self.assertFalse(evaluate_admission(dict(binding, operation='*'), registry)['allowed'])

    def test_malformed_and_duplicates(self):
        binding, registry = fixture()
        for field, value in [('schema_version', True), ('schema_version', 2), ('revision', True), ('revision', -1)]:
            bad = copy.deepcopy(registry); bad[field] = value
            self.assertFalse(valid_registry(bad))
        for field, value in [('validated_at', '2026-02-30T12:00:00Z'), ('validated_at', '2026-10-12T12:00:00'),
                             ('validated_at', '2026-10-12T12:00:00+01:99'), ('evidence_ref', ''), ('operation', '*')]:
            bad = copy.deepcopy(registry); bad['entries'][0][field] = value
            self.assertFalse(valid_registry(bad))
        bad = copy.deepcopy(registry); del bad['entries'][0]['evidence_digest']
        self.assertFalse(valid_registry(bad))
        registry['entries'].append(copy.deepcopy(registry['entries'][0]))
        self.assertFalse(valid_registry(registry))
        registry['entries'][1]['artifact_digest'] = 'f'*64
        self.assertTrue(valid_registry(registry))
