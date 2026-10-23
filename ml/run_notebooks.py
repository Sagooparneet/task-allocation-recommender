from pathlib import Path
import nbformat
from nbclient import NotebookClient
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--start', type=int, default=1)
args=parser.parse_args()
for path in sorted((Path(__file__).resolve().parent/'notebooks').glob('*.ipynb')):
    if int(path.name[:2]) < args.start:
        continue
    print('Executing '+path.name,flush=True)
    nb=nbformat.read(path,as_version=4)
    NotebookClient(nb,timeout=900,kernel_name='python3',resources={'metadata':{'path':str(path.parent)}}).execute()
    nbformat.validate(nb); nbformat.write(nb,path)
    print('Saved '+path.name,flush=True)
