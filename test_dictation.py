"""Dictation contracts, using a deterministic clock and an isolated database."""
import tempfile
import unittest
from pathlib import Path
from app import App, mask_word


class Dictation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.clock = 1000.
        self.app = App(Path(self.tmp.name) / 'words.sqlite3', now=lambda: self.clock, seed=False)
        self.app.import_book(dict(id='test', title='听写测试', publisher='测试', edition='测试', grade=6,
            term='上', source_url='https://example.com', words=[dict(english='paste', meaning='粘贴'),
            dict(english='post office', meaning='邮局')]))
        self.counter = 0

    def start(self, kind='dictation_en', **settings):
        return self.app.start(dict(book_id='test', minutes=1, learning_order='sequential', practice_type=kind, **settings))

    def act(self, s, action, **kw):
        self.counter += 1
        return self.app.act(s['id'], action, dict(position=s['position'], request_id=str(self.counter), **kw))['session']

    def test_full_answer_single_submission_and_modes(self):
        for kind in ('dictation_en', 'dictation_zh'):
            s = self.start(kind)
            self.assertEqual(s['practice_type'], kind)
            self.assertEqual(s['current']['masked'], '_____')
            for key in ('meaning', 'phonetic', 'reveal'):
                self.assertNotIn(key, s['current'])
            with self.assertRaises(ValueError): self.act(s, 'hint')
            with self.assertRaises(ValueError): self.act(s, 'answer', answer='paste')
            self.clock += 20  # Listening is not writing time.
            s = self.act(s, 'ready')
            deadline = s['current']['writing_deadline']
            self.assertEqual(deadline, self.clock + 15)
            self.clock += 1
            self.assertEqual(self.act(s, 'ready')['current']['writing_deadline'], deadline)
            s = self.act(s, 'answer', answer='paste')
            self.assertEqual(s['current']['result'], 'correct')
            self.assertEqual(s['current']['reveal'], 'paste')
            self.assertEqual(s['position'], 0)
            s = self.act(s, 'answer', answer='wrong')
            self.assertEqual(s['current']['tries'], 1)
            self.assertEqual(s['stars'], 10)
            s = self.act(s, 'next')
            self.assertEqual(s['current']['masked'], '____ ______')
            self.assertIsNone(s['current']['writing_deadline'])
            self.act(s, 'finish')

    def test_draft_expiry_restart_and_session_boundary(self):
        s = self.start()
        self.clock += 59
        s = self.act(s, 'ready')
        s = self.act(s, 'draft', answer='pa', revision=2)
        self.act(s, 'draft', answer='p', revision=1)  # An older request cannot overwrite.
        self.clock += 2
        self.app = App(self.app.path, now=lambda: self.clock, seed=False)
        s = self.app.state(s['id'])
        self.assertEqual(s['status'], 'active')
        self.assertEqual(s['current']['draft'], 'pa')
        self.assertEqual(s['current']['writing_deadline'], 1074)
        self.clock = 1074
        s = self.app.state(s['id'])
        self.assertEqual(s['current']['result'], 'timeout')
        s = self.act(s, 'answer', answer='paste')  # Late input cannot replace the saved answer.
        self.assertEqual(s['current']['draft'], 'pa')
        s = self.act(s, 'next')
        self.assertEqual(s['status'], 'timeout')
        r = self.app.report(s['id'])
        self.assertEqual((r['dictation_correct'], r['dictation_wrong'], r['dictation_timeout']), (0, 0, 1))
        self.assertEqual(r['words'][0]['attempts'][0]['answer'], 'pa')
        self.assertEqual(r['total'], 2)
        self.assertEqual(r['practice_completed'], 1)
        self.assertEqual(len(self.app.mistakes()), 1)

    def test_complete_draft_at_deadline_and_separate_mistakes(self):
        s = self.act(self.start(), 'ready')
        s = self.act(s, 'draft', answer='wrong', revision=1)
        self.clock += 15
        s = self.app.state(s['id'])
        self.assertEqual(s['current']['result'], 'wrong')
        self.act(s, 'finish')
        s = self.start('hint')
        s = self.act(s, 'answer', answer=mask_word('paste')[1])
        self.act(s, 'finish')
        self.assertEqual(len(self.app.mistakes()), 1, 'Hint practice must not clear a dictation error')
        s = self.act(self.start(), 'ready')
        self.act(s, 'draft', answer='paste', revision=1)
        self.clock += 15
        s = self.app.state(s['id'])
        self.assertEqual(s['current']['result'], 'correct')
        self.assertEqual(len(self.app.mistakes()), 0)
        self.assertEqual(self.app.report(s['id'])['dictation_correct'], 1)

    def test_current_audio_can_finish_after_session_deadline_but_no_new_word(self):
        s = self.start()
        self.clock = s['deadline'] + 1
        s = self.act(s, 'ready')
        self.assertEqual(s['current']['writing_deadline'], self.clock + 15)
        s = self.act(s, 'answer', answer='paste')
        s = self.act(s, 'next')
        self.assertEqual(s['status'], 'timeout')
        self.assertEqual(s['position'], 0)

    def test_draft_while_second_read_is_playing(self):
        s = self.start()
        s = self.act(s, 'draft', answer='pa', revision=1)
        self.assertEqual(s['current']['draft'], 'pa')
        self.assertIsNone(s['current']['writing_deadline'])
        with self.assertRaises(ValueError): self.act(s, 'answer', answer='paste')
        s = self.act(s, 'ready')
        self.assertEqual(s['current']['draft'], 'pa')
        self.assertEqual(s['current']['writing_deadline'], self.clock + 15)

    def test_blank_at_deadline_is_a_wrong_attempt(self):
        s = self.act(self.start(), 'ready')
        self.clock += 15
        s = self.app.state(s['id'])
        self.assertEqual(s['current']['result'], 'timeout')
        r = self.app.report(s['id'])
        self.assertEqual(r['words'][0]['attempts'][0]['correct'], 0)
        self.assertEqual(r['words'][0]['attempts'][0]['answer'], '')
        self.assertEqual((r['attempted'], r['practice_completed'], r['first_correct']), (1, 1, 0))
        self.assertEqual(len(self.app.mistakes()), 1)
        self.assertEqual(self.act(s, 'next')['position'], 1)

    def test_manual_has_no_word_deadline_and_survives_restart(self):
        for kind in ('dictation_en', 'dictation_zh'):
            s = self.start(kind, dictation_mode='manual', dictation_seconds=30)
            with self.assertRaises(ValueError): self.act(s, 'answer', answer='paste')
            s = self.act(s, 'draft', answer='paste', revision=1)
            s = self.act(s, 'ready')
            self.assertEqual(s['current']['phase'], 'writing')
            self.assertIsNone(s['current']['writing_deadline'])
            self.clock += 40
            self.app = App(self.app.path, now=lambda: self.clock, seed=False)
            s = self.app.state(s['id'])
            self.assertEqual(s['dictation_mode'], 'manual')
            self.assertEqual(s['current']['phase'], 'writing')
            self.assertEqual(s['current']['result'], '')
            self.assertEqual(s['current']['tries'], 0)
            self.assertEqual(self.act(s, 'ready')['current']['writing_deadline'], None)
            s = self.act(s, 'answer', answer='paste')
            self.assertEqual(s['current']['result'], 'correct')
            s = self.act(s, 'next')
            self.assertEqual(s['position'], 1)
            s = self.act(s, 'ready')
            self.clock += 80  # Overall time stops new words, never submits a manual answer.
            self.assertEqual(self.app.state(s['id'])['current']['result'], '')
            s = self.act(s, 'answer', answer='')
            self.assertEqual(s['current']['result'], 'wrong')
            self.assertEqual(self.act(s, 'next')['status'], 'timeout')
            r = self.app.report(s['id'])
            self.assertEqual(r['dictation_mode'], 'manual')
            self.assertEqual((r['dictation_correct'], r['dictation_wrong'], r['dictation_timeout']), (1, 1, 0))

    def test_custom_countdown_and_invalid_settings(self):
        for settings in [dict(dictation_mode='other'), *[dict(dictation_seconds=n) for n in (0, 301, True, 1.5, '15')]]:
            with self.assertRaises(ValueError): self.start(**settings)
        s = self.act(self.start(dictation_mode='auto', dictation_seconds=5), 'ready')
        deadline = self.clock + 5
        self.assertEqual(s['current']['writing_deadline'], deadline)
        self.clock += 4
        self.assertEqual(self.act(s, 'ready')['current']['writing_deadline'], deadline)
        self.assertEqual(self.app.state(s['id'])['current']['result'], '')
        self.clock += 1
        self.assertEqual(self.app.state(s['id'])['current']['result'], 'timeout')
        self.assertEqual(self.app.report(s['id'])['dictation_seconds'], 5)


if __name__ == '__main__':
    unittest.main()
