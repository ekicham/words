"""Test-only outbound mock; build.py deliberately excludes this module."""
import asyncio
import worker
from workers import Response

calls = 0
async def mock_fetch(url, options):
    global calls
    assert url == 'https://soe.tencentcloudapi.com'
    calls += 1
    await asyncio.sleep(0.05)
    if calls == 2: raise TimeoutError('simulated provider timeout')
    return Response.json({'Response':{'PronAccuracy':88,'RequestId':'mock-'+str(calls),'Words':[]}})
worker.js_fetch = mock_fetch
class Default(worker.Default): pass
class Accounts(worker.Accounts): pass
class Learner(worker.Learner): pass
