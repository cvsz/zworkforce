import unittest
from zworkforce.evaluator import evaluate, validate_criteria, EvaluationError
from zworkforce.skills import sign_manifest, verify_manifest, SkillError

class SkillsEvaluatorTests(unittest.TestCase):
    def test_evaluator(self):
        status,score,details=evaluate('{"ok":true}',[{"type":"json"},{"type":"contains","value":"ok"}]); self.assertEqual(status,"passed"); self.assertEqual(score,1.0)
    def test_bad_criterion(self):
        with self.assertRaises(EvaluationError): evaluate("x",[{"type":"unknown"}])
    def test_invalid_regex_criterion_is_rejected(self):
        with self.assertRaises(EvaluationError): evaluate("abc", [{"type":"regex", "pattern":"["}])
    def test_validate_criteria_does_not_evaluate_content(self):
        validate_criteria([{"type": "contains", "value": "not present"}])
    def test_validate_criteria_rejects_non_list(self):
        with self.assertRaises(EvaluationError): validate_criteria({"type": "non_empty"})
    def test_skill_signature(self):
        manifest={"id":"repo-review","version":"1.0.0","allowed_tools":["workspace_read"],"system_prompt_append":"Review carefully."}; sig=sign_manifest(manifest,"a-secure-signing-key-123456789")
        self.assertTrue(verify_manifest(manifest,sig,"a-secure-signing-key-123456789",True)); manifest["version"]="1.0.1"; self.assertFalse(verify_manifest(manifest,sig,"a-secure-signing-key-123456789",True))

if __name__ == "__main__": unittest.main()
