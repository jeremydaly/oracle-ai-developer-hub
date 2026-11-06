"""Execute with the current interpreter and save matching notebook outputs."""
import sys
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager

root=Path(__file__).resolve().parent
path=root/'postgresql_vs_oracle_agent_memory.ipynb'
nb=nbformat.read(path,as_version=4)
km=KernelManager(kernel_name='python3')
km.kernel_spec.argv=[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}']
client=NotebookClient(nb,timeout=600,km=km,resources={'metadata':{'path':str(root)}})
try:
    client.execute()
finally:
    nbformat.write(nb,path)
print('Executed',sum(c.cell_type=='code' for c in nb.cells),'code cells; outputs saved.')
