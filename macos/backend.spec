from pathlib import Path
import os

root = Path(SPECPATH).parent
python_lib = Path(os.environ['DYLD_LIBRARY_PATH'])
analysis = Analysis([str(root / 'macos/backend.py')], pathex=[str(root)],
    binaries=[(str(python_lib / name), '.') for name in ('libssl.3.dylib', 'libcrypto.3.dylib')],
    datas=[(str(root / 'static'), 'static'), (str(root / 'data/books'), 'data/books'),
           (str(root / 'data/phonetics.json'), 'data'),
           (str(root / 'data/phonetics-course.json'), 'data'),
           (str(root / 'data/phonetics-media'), 'data/phonetics-media'),
           (str(root / 'data/sources/official/1212001601265-phonetics.tsv'), 'data/sources/official')])
archive = PYZ(analysis.pure)
executable = EXE(archive, analysis.scripts, [], exclude_binaries=True, name='WordIsleBackend',
                 console=True, target_arch='universal2')
collection = COLLECT(executable, analysis.binaries, analysis.datas, name='WordIsleBackend')
bundle = BUNDLE(collection, name='WordIsleBackend.app', bundle_identifier='net.wordisle.backend',
                info_plist={'LSBackgroundOnly': True, 'LSMinimumSystemVersion': '12.3'})
