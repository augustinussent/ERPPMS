from pathlib import Path
import ast,json,sys
root=Path(__file__).resolve().parents[1];errors=[];counts={'python':0,'json':0}
for p in root.rglob('*.py'):
 if '.venv' in p.parts:
  continue
 try:ast.parse(p.read_text());counts['python']+=1
 except Exception as e:errors.append(f'{p}: {e}')
for p in root.rglob('*.json'):
 try:json.loads(p.read_text());counts['json']+=1
 except Exception as e:errors.append(f'{p}: {e}')
print(counts)
if errors:print('\n'.join(errors));sys.exit(1)
