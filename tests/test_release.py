import importlib
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from ea_bench.client import ProviderError, parse_json
from ea_bench.registry import entries, get_entry, verify_entry
from ea_bench.paths import DATA
from integrations.packet_stages.clarification import validate, fact_only_reply


class ProtocolTests(unittest.TestCase):
    def test_registry_matches_paper(self):
        rows=entries()
        self.assertEqual(len(rows),232)
        self.assertEqual(len({r['case_key'] for r in rows}),63)
        self.assertEqual(sum(r['track']=='Easy' for r in rows),147)
        self.assertEqual(sum(r['track']=='Hard' for r in rows),85)

    def test_track_ids_and_previous_aliases(self):
        rows = entries()
        self.assertEqual(len({r['id'] for r in rows}), 232)
        for entry in rows:
            with self.subTest(episode=entry['id']):
                self.assertEqual(entry['id'], f"{entry['track'].lower()}:{entry['case']}:{entry['variant']}")
                self.assertEqual(get_entry(entry['id']), entry)
                self.assertEqual(get_entry(f"{entry['cohort']}:{entry['case']}:{entry['variant']}"), entry)
        for episode in ('hard:WB12:R1', 'easy:JB17:M1', 'easy:unknown:full'):
            with self.subTest(episode=episode), self.assertRaises(ValueError):
                get_entry(episode)

    def test_list_by_track(self):
        from ea_bench.cli import main
        for track, tasks, conditions in [('easy', 33, 147), ('hard', 30, 85)]:
            with self.subTest(track=track), patch('sys.argv', ['ea_bench', 'list', '--track', track]):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    main()
                result = json.loads(output.getvalue())
                self.assertEqual(result['base_tasks'], tasks)
                self.assertEqual(result['conditions'], conditions)
                self.assertEqual(result['tracks'], {track.title(): conditions})
                self.assertTrue(all(e['id'].startswith(track + ':') for e in result['episodes']))

    def test_easy_cannot_use_artifact_grade(self):
        from ea_bench.cli import main
        args = ['ea_bench', 'grade', '--episode', 'easy:WB12:R1', '--config', 'unused.json',
                '--artifacts', 'unused', '--output', 'unused']
        error = io.StringIO()
        with patch('sys.argv', args), patch('ea_bench.cli.load_config') as config:
            with contextlib.redirect_stderr(error), self.assertRaises(SystemExit) as raised:
                main()
            self.assertEqual(raised.exception.code, 2)
            config.assert_not_called()
        self.assertIn('grade accepts Hard artifact tasks', error.getvalue())

    def test_json_action_boundary(self):
        self.assertEqual(parse_json('```json\n{"tool":"list_files"}\n```'),{'tool':'list_files'})
        with self.assertRaises(ValueError):parse_json('[1,2]')

    def test_wrong_user_value_rejected(self):
        knowledge={'gold':{'value':True,'answer':'Gold is required.'}}
        record={'reply':'Gold is not required.','requested':[{'fact_id':'gold','question_evidence':'Gold','description':'certification'}],
                'provided':[{'fact_id':'gold','value':False,'knowledge_evidence':'Gold is required.','reply_evidence':'Gold is not required.'}]}
        with self.assertRaises(ValueError):validate(record,'Is Gold required?',knowledge)

    def test_unrequested_fact_not_delivered(self):
        knowledge={'gold':{'value':True,'answer':'Gold is required.'},'days':{'value':2,'answer':'Delivery takes two days.'}}
        record={'reply':'Gold is required. Delivery takes two days.','requested':[{'fact_id':'gold','question_evidence':'Gold','description':'certification'}],
                'provided':[{'fact_id':k,'value':v['value'],'knowledge_evidence':v['answer'],'reply_evidence':v['answer']} for k,v in knowledge.items()]}
        valid=validate(record,'Is Gold required?',knowledge)
        reply=fact_only_reply(valid,knowledge)
        self.assertEqual(reply['reply'],'Gold is required.')
        self.assertEqual([x['fact_id'] for x in reply['provided']],['gold'])
        self.assertEqual([x['fact_id'] for x in reply['suppressed_unrequested']],['days'])


@unittest.skipUnless((DATA/'legacy/cases.json').exists(),'Download the release data to run integration tests')
class IntegrationTests(unittest.TestCase):
    def test_all_public_packets(self):
        for entry in entries():
            with self.subTest(episode=entry['id']):verify_entry(entry)

    def test_closed_state_reference_worlds(self):
        from ea_bench.cli import reference_check
        self.assertEqual(reference_check()['reference_worlds'],262)

    def test_unguarded_guess_is_not_grounded(self):
        from ea_bench.legacy.runner import load,run
        from ea_bench.legacy.expanded.domains import solve
        entry=get_entry('legacy:procurement:M2');public,private=load(entry)
        expected=solve(entry['case'],private['data'],private['policies'])
        graph={**{op:[] for op in private['case_spec']['data']},**private['case_spec']['stages']}
        actions=[dict(op=op,**({} if op.startswith('read_') else {'data':expected[op]})) for op in graph]
        class Scripted:
            def __init__(self):self.answers=iter(actions)
            def complete(self,messages):return json.dumps(next(self.answers))
        with tempfile.TemporaryDirectory() as d:
            result=run(entry,Path(d)/'episode',solver=Scripted(),user_client=object())
        self.assertTrue(result['task_pass'])
        self.assertFalse(result['grounded_pass'])
        self.assertEqual(result['requested_facts'],0)
        self.assertLess(result['Ei'],0)

    def test_transport_failure_is_not_task_failure(self):
        from ea_bench.legacy.runner import run
        class Unavailable:
            def complete(self,messages):raise ProviderError('Service unavailable')
        with tempfile.TemporaryDirectory() as d:
            result=run(get_entry('legacy:procurement:full'),Path(d)/'episode',solver=Unavailable(),user_client=object())
        self.assertEqual(result['status'],'infrastructure_error')
        self.assertIsNone(result['task_pass'])
        self.assertIsNone(result['requested_facts'])

    def test_expanded_state_packets(self):
        from integrations.packet_stages.authored import SOURCE,read_json
        count=0
        for entry in entries():
            if entry['cohort']!='expanded' or entry['case'].startswith('JB'):continue
            with self.subTest(episode=entry['id']):
                case,variant=entry['case'],entry['variant']
                oracle=read_json(SOURCE/case/'private/oracle.json');spec=oracle['variants'][variant]
                world={k:oracle['atoms'][k]['default'] for k in spec['missing']+spec['conflict']}
                cls=getattr(importlib.import_module('integrations.packet_stages.open_'+case.lower()),'Open'+case)
                engine=cls(variant=variant,answers=world) if case=='AW06' else cls(variant,world)
                observation=engine.observation()
                self.assertEqual(set(observation),{'task_description','output_format'})
                self.assertNotIn('oracle.json',json.dumps(observation))
                count+=1
        self.assertEqual(count,79)

    def test_artifact_adapters(self):
        for i in range(1,31):
            with self.subTest(case=i):
                module=importlib.import_module(f'integrations.packet_stages.artifact_adapter_jb{i:02}')
                self.assertTrue(callable(module.check))
                self.assertTrue(callable(module.knowledge))
                for reference in module.REFERENCES.values():
                    self.assertTrue(Path(reference['path']).is_file())

if __name__=='__main__':unittest.main()
