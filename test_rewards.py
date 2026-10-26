"""Reward accounting checks in temporary databases only."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import tempfile
import unittest
from app import App


class FamilyRewards(unittest.TestCase):
    def test_prize_settings_persist_and_preserve_awarded_prizes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'settings.sqlite3'
            app = App(path, now=lambda: 1000, seed=False)
            self.assertTrue(callable(getattr(app, 'reward_config', None)), 'Prize settings are not implemented')
            initial = app.reward_config()
            self.assertEqual(len(initial['prizes']), 8)
            self.assertEqual(set(p['icon'] for p in initial.get('presets', [])), set(initial['icons']))
            for preset in initial['presets']:
                self.assertTrue(preset['name'] and preset['detail'])
                self.assertLessEqual(len(preset['name']), 12)
                self.assertLessEqual(len(preset['detail']), 120)
            app.import_book(dict(id='settings-test', title='测试', publisher='测试', edition='测试', grade=6,
                term='上', source_url='https://example.com', words=[dict(english='Monday', meaning='星期一', unit='Unit 1')]))
            s = app.start(dict(book_id='settings-test'))
            for i in range(240): app.act(s['id'], 'answer', dict(position=i, answer='day', request_id=str(i)))
            old = app.draw_reward(dict(request_id='old', config_revision=initial['revision']))['draw']
            edited = [dict(name='亲子活动'+str(i), icon='🎁', detail='和家人一起安排的活动。') for i in range(8)]
            saved = app.save_reward_config(dict(prizes=edited, revision=initial['revision']))
            self.assertEqual(App(path, seed=False).reward_config(), saved)
            self.assertEqual(saved['prizes'], edited)
            self.assertEqual(app.rewards()['prizes'], edited)
            with self.assertRaises(ValueError): app.draw_reward(dict(request_id='old-page-without-version'))
            self.assertEqual(app.draw_reward(dict(request_id='old', config_revision=initial['revision']))['draw'], old)
            with self.assertRaises(ValueError): app.draw_reward(dict(request_id='stale', config_revision=initial['revision']))
            with self.assertRaises(ValueError): app.save_reward_config(dict(prizes=initial['prizes'], revision=initial['revision']))
            for bad in [None, [], edited[:-1], edited+[edited[0]], [dict(edited[0], name=' ')]*8,
                        [dict(edited[0], name='字'*13)]*8, [dict(edited[0], detail='字'*121)]*8,
                        [dict(edited[0], icon='not-an-icon')]*8, [dict(edited[0], name=1)]*8]:
                with self.assertRaises(ValueError): app.save_reward_config(dict(prizes=bad, revision=saved['revision']))
                self.assertEqual(app.reward_config(), saved)
            self.assertEqual(app.rewards()['wallet'], dict(earned=2400, spent=800, available=1600))
            new = app.draw_reward(dict(request_id='new', config_revision=saved['revision']))['draw']
            self.assertIn(new['prize'], edited)
            self.assertEqual(new['cost'], 800)
            self.assertEqual(app.redeem_reward('old')['prize'], old['prize'])
            self.assertEqual(app.draw_reward(dict(config_revision=app.reward_config()['revision'], request_id='old'))['draw']['prize'], old['prize'])

    def test_wallet_draw_retry_and_redemption(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'rewards.sqlite3'
            app = App(path, now=lambda: 1000, seed=False)
            self.assertTrue(callable(getattr(app, 'rewards', None)), 'Reward API is not implemented')
            self.assertEqual(app.rewards()['wallet'], dict(earned=0, spent=0, available=0))
            with self.assertRaises(ValueError): app.draw_reward(dict(config_revision=app.reward_config()['revision'], request_id='empty'))
            app.import_book(dict(id='reward-test', title='测试', publisher='测试', edition='测试', grade=6,
                term='上', source_url='https://example.com', words=[dict(english='Monday', meaning='星期一', unit='Unit 1')]))
            s = app.start(dict(book_id='reward-test'))
            for i in range(240):
                app.act(s['id'], 'answer', dict(position=i, answer='day', request_id='answer-'+str(i)))
            before = app.report(s['id'])
            self.assertEqual(app.rewards()['wallet']['earned'], before['stars'])
            result = app.draw_reward(dict(config_revision=app.reward_config()['revision'], request_id='first', cost=1, prize_index=99))
            self.assertEqual(result['wallet'], dict(earned=2400, spent=800, available=1600))
            self.assertEqual(result['draw']['cost'], 800)
            self.assertIn(result['draw']['prize'], app.rewards()['prizes'])
            self.assertEqual(app.draw_reward(dict(config_revision=app.reward_config()['revision'], request_id='first'))['draw'], result['draw'])
            self.assertEqual(App(path, now=lambda:1000, seed=False).rewards()['wallet'], result['wallet'])
            redeemed = app.redeem_reward('first')
            self.assertEqual(redeemed['redeemed_at'], 1000)
            self.assertEqual(app.redeem_reward('first'), redeemed)
            with self.assertRaises(ValueError): app.redeem_reward('missing')
            for key in ['', None, True, '../x', 'x'*101]:
                with self.assertRaises(ValueError): app.draw_reward(dict(request_id=key, config_revision=app.reward_config()['revision']))
            # Identical requests from two windows consume only once.
            with ThreadPoolExecutor(max_workers=2) as pool:
                duplicate = list(pool.map(lambda _:app.draw_reward(dict(config_revision=app.reward_config()['revision'], request_id='same')), range(2)))
            self.assertEqual(duplicate[0]['draw'], duplicate[1]['draw'])
            self.assertEqual(app.rewards()['wallet']['available'], 800)
            # Two distinct requests cannot spend the last 800 stars twice.
            def draw(key):
                try: return app.draw_reward(dict(request_id=key, config_revision=app.reward_config()['revision']))
                except ValueError: return None
            with ThreadPoolExecutor(max_workers=2) as pool:
                competing = list(pool.map(draw, ['last-a', 'last-b']))
            self.assertEqual(sum(r is not None for r in competing), 1)
            final = app.rewards()
            self.assertEqual(final['wallet'], dict(earned=2400, spent=2400, available=0))
            self.assertEqual(len(final['draws']), 3)
            self.assertEqual(app.report(s['id']), before, 'Spending must not alter learning or earned stars')
            self.assertEqual(app.bootstrap()['summary']['stars'], 2400)
            self.assertEqual(app.bootstrap()['summary']['available_stars'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
