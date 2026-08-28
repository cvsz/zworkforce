"""
zc_word.py — Conversational Word-document assistant (Skills API only)
AI Model Coder CLI v1.33.0

A chat loop for .docx files, same shape as --excel-native/--pptx-native in
zc_excel.py / zc_powerpoint.py: each turn is a Messages API call
carrying the docx Skill (zc_skills_api.py) in a code-execution
container, so the document is built and edited entirely server-side.

Unlike Excel and PowerPoint, this module has no hand-rolled fallback —
there's no local python-docx exec loop here, because that hand-rolled path
was never built for Word documents in this CLI. This is Skills-only, which
is why the CLI flag is --docx-native with no plain --docx counterpart:
"native" still names which path it is (Anthropic's own maintained
implementation vs. a hand-rolled one), even though today it's the only
path available. Requires Skills access on the account.

CLI:
  --docx-native [FILE]     Start a Word-document chat session, optionally
                            loading an existing .docx as the starting
                            document
  --docx-output FILE       Document to write after every turn that
                            produces one (default: <input>.docx or
                            docx_session.docx)

Slash commands: /exit, /quit only — the docx Skill owns the document
server-side, so there's no local copy here to list sections, preview, or
undo (mirrors --excel-native / --pptx-native's same limitation).
"""
import re
import sys


def cmd_docx_chat(api_key, model, input_path=None, output_path=None, max_tokens=4096):
    """Mirrors zc_powerpoint.py's _cmd_pptx_chat_native /
    zc_excel.py's _cmd_excel_chat_native one-for-one — same
    upload-once/download-per-turn shape — against the docx Skill instead
    of pptx/xlsx. No local python-docx dependency needed for this path."""
    from wire.zc_files import FilesAPI
    from wire.zc_skills_api import SkillsApiClient, build_user_content, extract_output_file_ids

    files_api = FilesAPI(api_key=api_key, model=model)
    client = SkillsApiClient(api_key=api_key, model=model, max_tokens=max_tokens)

    output_path = output_path or (
        re.sub(r"\.\w+$", "", input_path) + ".docx" if input_path else "docx_session.docx"
    )

    pending_file_ids = []
    if input_path:
        try:
            uploaded = files_api.upload(input_path)
        except (RuntimeError, OSError) as e:
            print(f"[ERROR] Could not upload {input_path}: {e}", file=sys.stderr)
            sys.exit(1)
        fid = uploaded.get("id")
        if not fid:
            print(f"[ERROR] Upload succeeded but returned no file id: {uploaded}", file=sys.stderr)
            sys.exit(1)
        pending_file_ids = [fid]

    print(f"\033[94mAI Model Coder — Word chat (native Skills API)\033[0m  (model: {model})")
    print(f"Document: {output_path}  (saved after every turn that produces one)")
    print("Type /exit to quit.\n")

    messages = []
    container_id = None
    while True:
        try:
            user_input = input("\033[92myou›\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in ("/exit", "/quit"):
            break

        messages.append({"role": "user", "content": build_user_content(user_input, pending_file_ids)})
        has_uploads = bool(pending_file_ids)
        pending_file_ids = []  # only attach on the turn that actually introduces the file

        data = client.call_with_skills_turn(
            messages, skills=["docx"], container_id=container_id, has_file_uploads=has_uploads,
        )
        if "error" in data:
            print(f"\033[91m✗ {data['error']}\033[0m\n")
            messages.pop()
            continue

        container_id = (data.get("container") or {}).get("id", container_id)
        messages.append({"role": "assistant", "content": data.get("content", [])})

        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        if text:
            print(f"\033[96mzc›\033[0m {text}\n")

        new_file_ids = extract_output_file_ids(data)
        if new_file_ids:
            try:
                files_api.download(new_file_ids[-1], output_path)
                print(f"\033[90m  (saved to {output_path})\033[0m\n")
            except RuntimeError as e:
                print(f"\033[93m  Couldn't download generated file: {e}\033[0m\n")

    print(f"\033[94mSession ended. Final document: {output_path}\033[0m")
    return output_path
