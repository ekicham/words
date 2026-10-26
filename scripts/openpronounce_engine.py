"""Pinned OpenPronounce 0.3.0 worker. Models are local; no network during scoring."""
import argparse
import base64
import contextlib
import functools
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
import traceback
import wave

MODELS = {
    'facebook/wav2vec2-large-960h': 'bdeaacdf88f7a155f50a2704bc967aa81fbbb2ab',
    'facebook/wav2vec2-lv-60-espeak-cv-ft': 'ae45363bf3413b374fecd9dc8bc1df0e24c3b7f4',
}


def write_state(folder, name, data):
    temporary = folder / (name + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False))
    temporary.replace(folder / name)


def initialize(folder, download=False):
    os.environ.update(HF_HOME=str(folder / 'models'), HF_HUB_DISABLE_TELEMETRY='1', HF_HUB_DISABLE_XET='1',
                      OPENPRONOUNCE_DEVICE='cpu', NUMBA_CACHE_DIR=str(folder / 'numba'), TOKENIZERS_PARALLELISM='false')
    if not download:
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1')
    import espeakng_loader
    os.environ['PHONEMIZER_ESPEAK_LIBRARY'] = espeakng_loader.get_library_path()
    os.environ['PHONEMIZER_ESPEAK_DATA_PATH'] = espeakng_loader.get_data_path()
    from huggingface_hub import snapshot_download
    paths = {}
    for index, (model, revision) in enumerate(MODELS.items()):
        if download:
            write_state(folder, 'progress.json', dict(message=f'正在下载/检查模型 {index+1} / 2（每个约 1.2 GB），请保持应用开启…'))
        for attempt in range(3 if download else 1):
            try:
                paths[model] = snapshot_download(model, revision=revision, local_files_only=not download,
                                                allow_patterns=['*.json', 'pytorch_model.bin', 'README.md'], max_workers=2)
                break
            except Exception:
                if not download or attempt == 2: raise
                write_state(folder, 'progress.json', dict(message=f'模型 {index+1} 下载中断，正在续传（重试 {attempt+1}/2）…'))
                time.sleep(2)
    import torch
    torch.set_num_threads(2)
    from transformers import Wav2Vec2ForCTC, Wav2Vec2Processor
    from openpronounce import speech, phones, audio
    @functools.lru_cache(maxsize=2)
    def load(model=speech.MODEL_NAME):
        processor = Wav2Vec2Processor.from_pretrained(paths[model], local_files_only=True)
        network = Wav2Vec2ForCTC.from_pretrained(paths[model], local_files_only=True).eval()
        return processor, network
    # Version-pinned adapter: preserve OpenPronounce scoring, pin model paths and replace only network TTS.
    speech._load_models = load
    phones._load_model = lambda: load(phones.PHONE_MODEL_NAME)
    def reference(text, lang='en', **kwargs):
        if lang != 'en' or not re.fullmatch(r"[A-Za-z][A-Za-z '-]{0,59}", text): raise ValueError('无效的参考例词。')
        target = folder / ('reference-' + hashlib.sha256(text.encode()).hexdigest()[:24] + '.wav')
        if not target.exists():
            try:
                subprocess.run(['/usr/bin/say','-v','Samantha','-r','145','--file-format=WAVE','--data-format=LEI16@16000','-o',str(target),text], check=True, capture_output=True, timeout=20)
            except Exception:
                target.unlink(missing_ok=True)
                raise ValueError('无法生成本机参考声，请在 macOS 中安装 Samantha 英文声音后重试。') from None
        return str(target)
    audio.text2speech = reference
    load(speech.MODEL_NAME); phones._load_model()
    # Ensure the phonemizer and installed macOS voice also work before reporting ready.
    if not speech.get_phonemes('father'): raise RuntimeError('phonemizer unavailable')
    reference('father')
    return speech, paths


def evaluate(speech, data):
    import numpy as np
    example = data.get('example')
    if not isinstance(example, str) or not re.fullmatch(r"[A-Za-z][A-Za-z '-]{0,59}", example): raise ValueError('参考例词无效。')
    encoded = data.get('audio')
    if not isinstance(encoded, str) or len(encoded) > 400000: raise ValueError('录音格式无效。')
    with wave.open(io.BytesIO(base64.b64decode(encoded, validate=True)), 'rb') as wav:
        if wav.getparams()[:3] != (1,2,16000) or not 8000 <= wav.getnframes() <= 128000: raise ValueError('录音须为 0.5–8 秒、16 kHz 单声道 WAV。')
        samples = np.frombuffer(wav.readframes(wav.getnframes()),dtype='<i2').astype(np.float32) / 32768
    if float(np.sqrt(np.mean(samples**2))) < 0.001:
        raise ValueError('没有检测到足够清晰的声音，请靠近麦克风重新录制；本次不计分。')
    result = speech.compare_audio_with_text(samples, example, use_phone_model=True)
    # Reports use actual text/phone recognition and the upstream score, never a fabricated per-phone percentage.
    return {key:result[key] for key in ('score','transcribe','differences','acoustic_distance')}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--parent-pid',type=int,required=True)
    parser.add_argument('--prepare',action='store_true')
    args=parser.parse_args();os.umask(0o077);args.data_dir.mkdir(parents=True,exist_ok=True)
    def watch_parent():
        while True:
            time.sleep(1)
            if os.getppid()!=args.parent_pid: os._exit(0)
    threading.Thread(target=watch_parent,daemon=True).start()
    guard = (args.data_dir / 'engine.lock').open('a')
    fcntl.flock(guard, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if args.prepare:
        speech, paths = initialize(args.data_dir,download=True)
        files = [dict(path=str(path.relative_to(args.data_dir)),size=path.stat().st_size)
                 for directory in paths.values() for path in Path(directory).iterdir() if path.is_file()]
        write_state(args.data_dir,'models-ready.json',dict(version='0.3.0',models=MODELS,files=files))
        write_state(args.data_dir,'progress.json',dict(message='模型和本机参考声已准备好。'))
        return
    output=sys.stdout
    with contextlib.redirect_stdout(sys.stderr): speech, _=initialize(args.data_dir)
    for line in sys.stdin:
        try:
            if len(line)>401000: raise ValueError('录音过大。')
            with contextlib.redirect_stdout(sys.stderr): result=evaluate(speech,json.loads(line))
        except Exception as error:
            traceback.print_exc(file=sys.stderr)
            result=dict(error=str(error) if isinstance(error,ValueError) else '本地模型运行失败，本次不计分。请重新准备模型或查看 engine.log。')
        output.write(json.dumps(result,ensure_ascii=False,allow_nan=False)+'\n');output.flush()

if __name__=='__main__':main()
