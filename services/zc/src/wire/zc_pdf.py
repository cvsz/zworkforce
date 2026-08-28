"""
zc_pdf.py — Conversational PDF assistant (Skills API only)
AI Model Coder CLI v1.33.0

A chat loop for .pdf files, same shape as zc_word.py's --docx-native —
each turn is a Messages API call carrying the pdf Skill
(zc_skills_api.py) in a code-execution container, so the PDF is
created, filled, or edited entirely server-side.

Skills-only, same reasoning as zc_word.py: no hand-rolled fallback
exists for PDFs in this CLI (this project's only other PDF-adjacent code
is zc_files.py's generic upload/download, which doesn't create or
edit PDF content), so --pdf-native is the only path, named consistently
with --docx-native / --excel-native / --pptx-native.

CLI:
  --pdf-native [FILE]      Start a PDF chat session, optionally loading an
                            existing .pdf as the starting document
  --pdf-output FILE        PDF to write after every turn that produces one
                            (default: <input>.pdf or pdf_session.pdf)

Slash commands: /exit, /quit only — same limitation as --docx-native /
--excel-native / --pptx-native (the Skill owns the document server-side).
"""
import re
import sys


def cmd_pdf_chat(api_key, model, input_path=None, output_path=None, max_tokens=4096):
    """Mirrors zc_word.py's cmd_docx_chat one-for-one against the pdf
    Skill instead of docx. No local PDF-generation dependency needed for
    this path."""
    from wire.zc_files import FilesAPI
    from wire.zc_skills_api import SkillsApiClient, build_user_content, extract_output_file_ids

    files_api = FilesAPI(api_key=api_key, model=model)
    client = SkillsApiClient(api_key=api_key, model=model, max_tokens=max_tokens)

    output_path = output_path or (
        re.sub(r"\.\w+$", "", input_path) + ".pdf" if input_path else "pdf_session.pdf"
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

    print(f"\033[94mAI Model Coder — PDF chat (native Skills API)\033[0m  (model: {model})")
    print(f"PDF: {output_path}  (saved after every turn that produces one)")
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
            messages, skills=["pdf"], container_id=container_id, has_file_uploads=has_uploads,
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

    print(f"\033[94mSession ended. Final PDF: {output_path}\033[0m")
    return output_path
