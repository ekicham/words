"""Local provider contracts; real model acceptance is recorded separately."""
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app import App
from test_phonetics import recording


class LocalProviderChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.app = App(Path(self.tmp.name) / 'words.sqlite3', seed=False)
        self.lesson = self.app.phonetics_lesson

    def test_switch_preserves_cloud_secret_and_test_provider(self):
        self.lesson.configure(dict(secret_id='AKIDtest', secret_key='SECRETtest'))
        cloud = self.lesson.start(dict(accent='uk', count=10, consent=True))
        service = self.lesson.configure(dict(provider='openpronounce'))
        self.assertEqual(service.get('provider'), 'openpronounce')
        self.assertEqual(self.lesson.config()['secret_key'], 'SECRETtest')
        with patch.object(self.lesson.local, 'status', return_value=dict(available=True, ready=True, busy=False, message='已就绪')):
            local = self.lesson.start(dict(accent='us', count=10, consent=True))
        self.assertEqual(local['provider'], 'openpronounce')
        self.assertEqual(self.lesson.state(cloud['id'])['provider'], 'tencent')
        self.lesson.configure(dict(provider='tencent'))
        self.assertEqual(self.lesson.state(local['id'])['provider'], 'openpronounce')
        self.assertNotIn('SECRETtest', json.dumps(self.lesson.overview()))
        self.assertEqual(self.lesson.config_path.stat().st_mode & 0o777, 0o600)

    def test_local_result_retry_and_no_cloud_fallback(self):
        self.lesson.configure(dict(provider='openpronounce'))
        with patch.object(self.lesson.local, 'status', return_value=dict(available=True, ready=True, busy=False, message='已就绪')):
            state = self.lesson.start(dict(accent='uk', count=10, consent=True))
        body=dict(position=0, request_id='local-1', audio=recording())
        with patch('phonetics.assess') as cloud, patch.object(self.lesson.local, 'assess', side_effect=ValueError('本地模型不可用')):
            failed = self.lesson.act(state['id'], 'assess', body)
            self.assertIsNone(failed['mean']); self.assertEqual(failed['position'],0);cloud.assert_not_called()
        body['request_id']='local-2'
        response=dict(score=72.3, raw_score=72.3, phones=[], request_id='', transcript='FATHER', expected_ipa='fɑːðə', heard_ipa='fɑðə', example=state['course'][0]['uk']['example'])
        with patch.object(self.lesson.local, 'assess', return_value=response) as local, patch('phonetics.assess') as cloud:
            result=self.lesson.act(state['id'],'assess',body)
            again=self.lesson.act(state['id'],'assess',body)
            local.assert_called_once();cloud.assert_not_called()
        self.assertEqual((result['position'],again['mean']),(1,72.3))
        report=self.lesson.act(state['id'],'finish',{})
        self.assertEqual(report['provider'],'openpronounce');self.assertIn('例词',report['notice'])

    def test_legacy_rows_stay_tencent_and_clear_keeps_selection(self):
        self.lesson.configure(dict(secret_id='AKIDtest',secret_key='SECRETtest'))
        state=self.lesson.start(dict(accent='uk',count=10,consent=True))
        self.lesson.configure(dict(provider='openpronounce'))
        self.lesson.configure(dict(clear=True))
        self.assertEqual(self.lesson.service().get('provider'),'openpronounce')
        self.assertFalse(self.lesson.service()['tencent_configured'])
        self.assertEqual(self.lesson.state(state['id'])['provider'],'tencent')
        with self.assertRaises(ValueError): self.lesson.configure(dict(provider='unknown'))

    def test_missing_model_file_invalidates_ready_marker(self):
        local=self.lesson.local
        local.folder.mkdir()
        (local.folder/'models-ready.json').write_text(json.dumps(dict(version='0.3.0',files=[dict(path='missing.bin',size=123)])))
        with patch.object(local,'command',return_value=['engine']), patch('local_assessment.platform.machine',return_value='arm64'), patch('local_assessment.platform.mac_ver',return_value=('15.0','','')), patch('local_assessment.platform.system',return_value='Darwin'):
            self.assertFalse(local.status()['ready'])

    def test_local_response_requires_finite_score(self):
        from local_assessment import parse_result
        parsed=parse_result(dict(score=81.2,transcribe='FATHER',differences=dict(expected_phones=[['f','a']],heard_phones=['f','ə'],errors=[])), 'father')
        self.assertEqual(parsed['heard_ipa'],'f ə')
        self.assertEqual(parsed['expected_ipa'],'f a')
        self.assertEqual(parsed['example'],'father')
        for score in [True,None,float('nan'),101,-1]:
            with self.assertRaises(ValueError):parse_result(dict(score=score), 'father')

if __name__=='__main__':unittest.main()
