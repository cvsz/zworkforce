import os
import re

DIFF_PATH = '/home/cvsz/.gemini/antigravity-cli/brain/f7427ccc-3689-4aa2-a05d-59bf2c5ab146/.system_generated/steps/541/content.md'
OUTPUT_DIR = '/mnt/zok'

def parse_diff():
    if not os.path.exists(DIFF_PATH):
        print(f"Diff file not found at {DIFF_PATH}")
        return

    with open(DIFF_PATH, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    current_file = None
    file_lines = []
    in_header = True

    for line in lines:
        # Match git diff headers: diff --git a/path b/path
        match = re.match(r'^diff --git a/(.*) b/(.*)', line)
        if match:
            # Save previous file if active
            if current_file and file_lines:
                write_file(current_file, file_lines)
            
            # Start new file extraction
            current_file = match.group(2)
            file_lines = []
            in_header = True
            print(f"Extracting file: {current_file}")
            continue

        if current_file:
            if in_header:
                # We skip metadata headers until we hit the hunk start (@@)
                if line.startswith('@@'):
                    in_header = False
                continue
            else:
                # Inside hunk content
                if line.startswith('+'):
                    # Added lines are written (minus the leading +)
                    file_lines.append(line[1:])
                elif line.startswith(' '):
                    # Unchanged lines (context)
                    file_lines.append(line[1:])
                elif line.startswith('-'):
                    # Deleted lines are skipped
                    continue

    # Write the last file
    if current_file and file_lines:
        write_file(current_file, file_lines)

def write_file(rel_path, lines):
    # Ensure it's inside output directory
    dest_path = os.path.join(OUTPUT_DIR, rel_path)
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
    with open(dest_path, 'w', encoding='utf-8') as f:
        f.writelines(lines)
    print(f"Successfully wrote {dest_path} ({len(lines)} lines)")

if __name__ == '__main__':
    parse_diff()
