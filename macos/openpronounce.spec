from pathlib import Path
import os
from PyInstaller.utils.hooks import collect_all, copy_metadata, collect_submodules
root=Path(SPECPATH).parent
library=Path(os.environ['DYLD_LIBRARY_PATH'])
datas=[(str(root/'.build/openpronounce/notices'),'source-and-notices')]; binaries=[(str(library/name),'.') for name in ('libssl.3.dylib','libcrypto.3.dylib')]; hidden=[]
for name in ('openpronounce','espeakng_loader','librosa'):
    data, binary, imports=collect_all(name)
    datas+=data; binaries+=binary; hidden+=imports
for name in ('openpronounce','torch','transformers','huggingface-hub','numpy','scipy','soundfile','librosa','phonemizer'):
    datas+=copy_metadata(name)
hidden += collect_submodules('scipy._external')
hidden += ['transformers.models.wav2vec2.modeling_wav2vec2','transformers.models.wav2vec2.processing_wav2vec2',
           'transformers.models.wav2vec2_phoneme.tokenization_wav2vec2_phoneme']
a=Analysis([str(root/'scripts/openpronounce_engine.py')],pathex=[str(root)],datas=datas,binaries=binaries,hiddenimports=hidden,
           excludes=['matplotlib','IPython','pytest','tkinter','tensorboard','tensorflow','jax','torchaudio','torchvision'])
z=PYZ(a.pure)
e=EXE(z,a.scripts,[],exclude_binaries=True,name='OpenPronounceEngine',console=True,target_arch='arm64')
c=COLLECT(e,a.binaries,a.datas,name='OpenPronounceEngine')
b=BUNDLE(c,name='OpenPronounceEngine.app',bundle_identifier='net.wordisle.openpronounce',
         info_plist={'LSBackgroundOnly':True,'LSMinimumSystemVersion':'14.0'})
