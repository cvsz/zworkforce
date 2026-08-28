import os
import re

def rebrand():
    root = '.'
    
    # Exclude directories
    exclude_dirs = {'.git', '.web-venv', '__pycache__', 'node_modules', 'logs', 'dist', 'build', 'venv2', '.local'}

    # 1. Content replacement
    for root_dir, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            # allow specific extensions and .env files
            if not (file.endswith(('.py', '.md', '.txt', '.json', '.yaml', '.yml', '.html', '.css', '.js')) or file.startswith('.env') or file == 'Makefile'):
                continue
            path = os.path.join(root_dir, file)
            try:
                with open(path, encoding='utf-8') as f:
                    content = f.read()
            except UnicodeDecodeError:
                continue

            orig_content = content
            
            # Replace "zAICoder" with "zAICoder"
            content = content.replace("zAICoder", "zAICoder")
            content = content.replace("zAICoder", "zAICoder")
            content = content.replace("zc_", "zc_")
            content = content.replace("ZC", "ZC")
            content = content.replace(".zc", ".zc")

            content = re.sub(r'\bclaude(?!-)\b', 'zc', content)

            if content != orig_content:
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Updated content in {path}")

    # 2. Rename files
    # We collect all renames first
    renames = []
    for root_dir, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for name in files + dirs:
            if 'zc' in name or 'ZC' in name or 'zAICoder' in name:
                new_name = name
                new_name = new_name.replace('zc_', 'zc_')
                new_name = new_name.replace('ZC', 'ZC')
                new_name = new_name.replace('zAICoder', 'zAICoder')
                new_name = re.sub(r'\bclaude\b', 'zc', new_name)
                
                if new_name != name:
                    old_path = os.path.join(root_dir, name)
                    new_path = os.path.join(root_dir, new_name)
                    renames.append((old_path, new_path))
                    
    # Sort renames by length descending to rename deepest paths first
    renames.sort(key=lambda x: len(x[0]), reverse=True)
    
    for old, new in renames:
        if os.path.exists(old):
            os.rename(old, new)
            print(f"Renamed {old} to {new}")

if __name__ == '__main__':
    rebrand()
