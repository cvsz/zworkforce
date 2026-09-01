import ast
import os

target = '/home/zeazdev/zeaz-platform/apps/ztrader/backend/src/ztrader/main.py'
with open(target, 'r') as f:
    lines = f.readlines()

with open(target, 'r') as f:
    source = f.read()

tree = ast.parse(source)

schemas_code = []
schema_names = []
lines_to_remove = []

for node in tree.body:
    if isinstance(node, ast.ClassDef):
        if any(isinstance(base, ast.Name) and base.id == 'BaseModel' for base in node.bases):
            schema_names.append(node.name)
            class_lines = lines[node.lineno-1:node.end_lineno]
            schemas_code.append("".join(class_lines))
            for i in range(node.lineno-1, node.end_lineno):
                lines_to_remove.append(i)

# Create domain/schemas.py
os.makedirs('/home/zeazdev/zeaz-platform/apps/ztrader/backend/src/ztrader/domain', exist_ok=True)
with open('/home/zeazdev/zeaz-platform/apps/ztrader/backend/src/ztrader/domain/schemas.py', 'w') as f:
    f.write("from pydantic import BaseModel, ConfigDict, Field\n")
    f.write("from typing import List, Dict, Any, Literal, Optional\n")
    f.write("from uuid import UUID\n")
    f.write("from ztrader.engine.strategy import Candle\n\n")
    for code in schemas_code:
        f.write(code)
        f.write("\n")

print("Created schemas.py with:", schema_names)

# Remove schemas from main.py and add import
new_lines = []
for i, line in enumerate(lines):
    if i not in lines_to_remove:
        new_lines.append(line)

import_statement = "from ztrader.domain.schemas import " + ", ".join(schema_names) + "\n"

# Insert import near the top
for i, line in enumerate(new_lines):
    if line.startswith("from pydantic import BaseModel"):
        new_lines.insert(i, import_statement)
        break

with open(target, 'w') as f:
    f.writelines(new_lines)

print("Updated main.py")
