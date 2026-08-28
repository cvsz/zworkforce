import os
import re

def main():
    root = '.'
    exclude_dirs = {'.git', '.web-venv', '__pycache__', 'node_modules', 'logs', 'dist', 'build', '.pytest_cache', '.ruff_cache', 'venv2', '.local'}
    
    pattern = re.compile(r'\b(zAICoder|zc)\b(?!-)')
    
    found = False
    for root_dir, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if not file.endswith(('.py', '.md', '.txt', '.json', '.yaml', '.yml', '.html', '.css', '.js')):
                continue
            path = os.path.join(root_dir, file)
            try:
                with open(path, encoding='utf-8') as f:
                    content = f.read()
                    matches = pattern.finditer(content)
                    for m in matches:
                        start = max(0, m.start() - 20)
                        end = min(len(content), m.end() + 20)
                        print(f"{path}: {content[start:end].strip()}")
                        found = True
            except Exception as e:
                pass
    if not found:
        print("No matches found.")

if __name__ == '__main__':
    main()
