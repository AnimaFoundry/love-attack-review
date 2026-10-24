"""Meaningful false-acceptance, denominator and paired-contrast controls. MIT."""
import unittest
from analyze import aggregate, paired
from prepare import CONDITIONS, FRAMING, FORMAT_REQUEST, DEFAULT_REQUEST, generate
from validators import assess

class AnalysisControls(unittest.TestCase):
    def item(self, text, expected, condition='TASK_ONLY', task='unit'):
        return {'case_id':task+'__'+condition, 'task_id':task,'condition':condition,
                'expected':expected,'assessment':assess(text,expected) if text is not None else None}

    def test_rejection_is_not_repair_and_wrong_valid_zero_survives(self):
        expected={'state':'absent','value':None}
        items=[self.item('{"state":"observed","value":0}',expected),
               self.item('```json\n{"state":"absent","value":null}\n```',expected),
               self.item('{"state":"absent","value":0}',expected),
               self.item('some reassurance',expected),self.item(None,expected)]
        r=aggregate(items)['ALL']
        self.assertEqual(r['formatting_recovered_correct'],1)
        self.assertEqual(r['schema_intercepted_wrong_without_correction'],1)
        s=r['pipelines']['schema_filter']
        self.assertEqual((s['accepted_correct'],s['accepted_wrong'],s['rejected'],s['unavailable_truncated_or_budget_excluded']),(1,1,2,1))
        self.assertEqual(s['conditional_correctness'],.5)
        self.assertEqual(s['correct_answers_per_initiated'],.2)

    def test_reject_all_has_zero_coverage_and_undefined_conditional_accuracy(self):
        r=aggregate([self.item('refusal',{'state':'unknown','value':None})])['ALL']['pipelines']['schema_filter']
        self.assertEqual(r['coverage'],0)
        self.assertIsNone(r['conditional_correctness'])

    def test_expected_does_not_control_acceptance(self):
        text='{"state":"observed","value":0}'
        a=assess(text,{'state':'observed','value':0})
        b=assess(text,{'state':'unknown','value':None})
        self.assertEqual(a['schema_accept'],b['schema_accept'])
        self.assertTrue(a['schema_accepted_correct'])
        self.assertTrue(b['schema_accepted_wrong'])

    def test_social_and_plain_operative_requests_identical(self):
        self.assertEqual(FRAMING['FORMAT_PLAIN'],FORMAT_REQUEST)
        self.assertTrue(FRAMING['RELATIONAL_FORMAT'].endswith(FORMAT_REQUEST))
        self.assertEqual(FRAMING['DEFAULT_PLAIN'],DEFAULT_REQUEST)
        self.assertTrue(FRAMING['LEGITIMACY_DEFAULT'].endswith(DEFAULT_REQUEST))

    def test_higher_priority_contract_is_same_across_conditions(self):
        task={'task_id':'unit','family':'test','instruction':'Use the marked field only.',
              'input_text':'marked=0','expected_json':{'state':'observed','value':0}}
        c=generate([task],'Return exact state and value JSON only.')
        self.assertEqual(len(c),7)
        self.assertEqual(len({x['messages'][0]['content'] for x in c}),1)
        self.assertEqual({x['messages'][0]['role'] for x in c},{'system'})
        self.assertTrue(all('audit_reasoning' not in str(x['messages']) for x in c))

    def test_paired_direction_and_absent_unknown_change(self):
        expected={'state':'absent','value':None}
        group=[self.item('{"state":"absent","value":null}',expected,c) for c in CONDITIONS]
        for x in group:
            if x['condition']=='LEGITIMACY_DEFAULT':
                x['assessment']=assess('{"state":"unknown","value":null}',expected)
        r=paired(group)
        self.assertEqual(r['DEFAULT_PLAIN__LEGITIMACY_DEFAULT__schema_accepted_wrong']['intervention_only'],1)
        self.assertEqual(r['DEFAULT_PLAIN__LEGITIMACY_DEFAULT__raw_exact_correct']['baseline_only'],1)

if __name__=='__main__':
    unittest.main()
