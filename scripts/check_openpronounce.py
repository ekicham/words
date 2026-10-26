"""Actual local-model smoke check; synthetic voices do not validate children's accuracy."""
import base64
import io
import json
from pathlib import Path
import subprocess
import sys
import time
import wave
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from local_assessment import LocalAssessment

folder=Path(sys.argv[1]).resolve()
local=LocalAssessment(folder)
if len(sys.argv)>2:
    binary=Path(sys.argv[2]).resolve()
    local.command=lambda:[str(binary)]
assert local.status()['ready'],local.status()
results={}
try:
    for spoken in ('father','banana'):
        target=folder/(spoken+'.wav')
        subprocess.run(['/usr/bin/say','-v','Samantha','-r','145','--file-format=WAVE','--data-format=LEI16@16000','-o',str(target),spoken],check=True)
        start=time.monotonic();result=local.assess(dict(example='father'),target.read_bytes());result['elapsed']=round(time.monotonic()-start,2)
        results[spoken]=result;print(json.dumps({spoken:result},ensure_ascii=False),flush=True)
    silence=io.BytesIO()
    with wave.open(silence,'wb') as wav:
        wav.setparams((1,2,16000,0,'NONE','not compressed'));wav.writeframes(b'\x00\x00'*16000)
    try: local.assess(dict(example='father'),silence.getvalue())
    except ValueError as error: results['silence']=str(error)
    else: raise AssertionError('silence must not score')
    assert results['father']['score']>results['banana']['score'],results
    print(json.dumps(dict(passed=True,results=results,syntheticSpeech=True,childAccuracyValidated=False),ensure_ascii=False),flush=True)
finally:local.close()
