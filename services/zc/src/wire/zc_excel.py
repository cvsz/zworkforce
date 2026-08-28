"""
zc_excel.py — Conversational spreadsheet / data-analysis assistant
AI Model Coder CLI v1.14.0

A chat loop purpose-built for spreadsheet work: describe what you want in
plain English — clean up messy data, build a financial model, summarize a
table, add a chart — and each turn updates an in-memory set of sheets that
gets written out to a real .xlsx file after every turn, so the workbook on
disk always reflects the latest state of the conversation.

This is the CLI's answer to a "zAICoder in Excel"-style experience: no
Office add-in, just a terminal chat that keeps a real .xlsx file in sync.

Requires: pandas, openpyxl (see requirements.txt — both optional deps,
only needed for this module).

CLI:
  --excel [FILE]           Start an Excel chat session, optionally loading
                            an existing .xlsx/.csv as the starting data
  --excel-output FILE      Workbook to write after every turn
                            (default: <input>.xlsx or excel_session.xlsx)
  --excel-sheet NAME       Which sheet to load from a multi-sheet .xlsx
                            (default: first sheet)

Slash commands inside the session:
  /help                Show this help
  /exit, /quit         End the session (workbook is already saved)
  /sheets              List current sheets and their shape
  /show SHEET [N]       Print the first N rows of SHEET (default 10)
  /undo                Revert to the state before the last applied change
"""
import ast
import re
import sys

try:
    import pandas as pd
except ImportError:
    pd = None

SYSTEM_PROMPT = """\
You are a spreadsheet assistant embedded in a CLI tool. The user is \
chatting with you to clean messy data, build financial models, summarize \
data, and create tables and charts — all applied directly to a live set \
of pandas DataFrames that get written back to a real .xlsx file after \
every turn.

You have access to a dict called `sheets` (sheet name -> pandas \
DataFrame) and the `pandas` module (as `pd`). To add a chart, call the \
provided `add_chart(sheet, chart_type, title, categories_col, value_cols)` \
helper, where chart_type is one of "bar", "line", or "pie", \
categories_col is a single column name, and value_cols is a list of \
column names.

Respond in ONE of two ways:

1. If the request requires changing the data (cleaning, transforming, \
computing new columns, building a model, adding a chart), respond with \
ONLY a single fenced python code block that mutates `sheets` in place \
(e.g. `sheets["Sheet1"] = sheets["Sheet1"].dropna()`) and/or calls \
`add_chart(...)`. No prose outside the code block.

2. If the request is a question that doesn't require changing the data \
(e.g. "what's the average of column X", "explain this model"), answer in \
plain text with no code block. You may compute the answer yourself from \
the sheet summary given to you, but do not guess at exact values you \
can't see — say so if you'd need a code-modifying turn to compute them.

Never write to disk, never import anything beyond pandas/numpy/datetime, \
never use `open(`, `os`, `sys`, `subprocess`, or `eval`/`exec`.
"""

_CODE_BLOCK = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)

# Forbidden AST node types and attributes for safe code execution
_FORBIDDEN_NODES = (
    ast.Import,
    ast.ImportFrom,
)

_FORBIDDEN_ATTRS = frozenset([
    "os", "sys", "subprocess", "socket", "shutil", "pathlib",
    "open", "eval", "exec", "__import__", "compile", "globals", 
    "locals", "vars", "dir", "getattr", "setattr", "delattr",
])


class ExcelSession:
    def __init__(self, input_path=None, sheet_name=None):
        if pd is None:
            raise ImportError(
                "pandas is required for --excel (pip install pandas openpyxl)"
            )
        self.sheets = {}
        self._history_stack = []  # for /undo — list of {name: df.copy()} snapshots
        self._pending_charts = []  # (sheet, chart_type, title, categories_col, value_cols)

        if input_path:
            self._load(input_path, sheet_name)
        else:
            self.sheets["Sheet1"] = pd.DataFrame()

    def _load(self, path, sheet_name=None):
        if path.lower().endswith(".csv"):
            self.sheets["Sheet1"] = pd.read_csv(path)
        else:
            all_sheets = pd.read_excel(path, sheet_name=None)
            if sheet_name:
                if sheet_name not in all_sheets:
                    raise ValueError(f"Sheet {sheet_name!r} not found; have {list(all_sheets)}")
                self.sheets = {sheet_name: all_sheets[sheet_name]}
            else:
                self.sheets = all_sheets

    # ── context for the model ───────────────────────────────────────────

    def summary(self):
        parts = []
        for name, df in self.sheets.items():
            cols = ", ".join(f"{c} ({df[c].dtype})" for c in df.columns[:30])
            parts.append(
                f"Sheet {name!r}: {df.shape[0]} rows x {df.shape[1]} cols. "
                f"Columns: {cols or '(empty)'}"
            )
            if not df.empty:
                parts.append(f"First rows of {name!r}:\n{df.head(5).to_string()}")
        return "\n".join(parts) if parts else "(no data loaded yet)"

    # ── applying a model turn ───────────────────────────────────────────

    def _snapshot(self):
        self._history_stack.append({k: v.copy() for k, v in self.sheets.items()})
        if len(self._history_stack) > 20:
            self._history_stack.pop(0)

    def undo(self):
        if not self._history_stack:
            return False
        self.sheets = self._history_stack.pop()
        return True

    def _validate_code_ast(self, code: str) -> tuple[bool, str]:
        """Validate code using AST to prevent code injection attacks.
        
        This is more secure than string-based denylists which can be bypassed
        through encoding, obfuscation, or character concatenation.
        """
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"syntax error: {e}"
        
        # Check for forbidden node types (imports)
        for node in ast.walk(tree):
            if isinstance(node, _FORBIDDEN_NODES):
                return False, f"forbidden statement: {ast.dump(node)}"
            
            # Check for forbidden attribute access
            if isinstance(node, ast.Attribute):
                if node.attr in _FORBIDDEN_ATTRS:
                    return False, f"forbidden attribute: {node.attr}"
            
            # Check for forbidden names (function calls like open(), eval(), etc.)
            if isinstance(node, ast.Name):
                if node.id in _FORBIDDEN_ATTRS:
                    return False, f"forbidden name: {node.id}"
            
            # Check for Call nodes with forbidden functions
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_ATTRS:
                    return False, f"forbidden function call: {node.func.id}"
                if isinstance(node.func, ast.Attribute) and node.func.attr in _FORBIDDEN_ATTRS:
                    return False, f"forbidden method call: {node.func.attr}"
        
        return True, ""

    def apply_code(self, code):
        """Run model-generated code against `self.sheets`. Returns (ok, message)."""
        # Validate code using AST before execution
        is_valid, error_msg = self._validate_code_ast(code)
        if not is_valid:
            return False, f"[blocked] generated code contains unsafe operations: {error_msg}"

        self._snapshot()
        local_ns = {
            "sheets": self.sheets,
            "pd": pd,
            "add_chart": self._add_chart,
        }
        try:
            exec(compile(code, "<excel-turn>", "exec"), {"__builtins__": {
                "len": len, "range": range, "sum": sum, "min": min, "max": max,
                "round": round, "sorted": sorted, "list": list, "dict": dict,
                "str": str, "int": int, "float": float, "bool": bool,
                "enumerate": enumerate, "zip": zip, "abs": abs,
            }}, local_ns)
        except Exception as e:
            self.undo()
            return False, f"[ERROR] generated code failed: {e}"
        self.sheets = local_ns["sheets"]
        return True, "applied"

    def _add_chart(self, sheet, chart_type, title, categories_col, value_cols):
        self._pending_charts.append((sheet, chart_type, title, categories_col, value_cols))

    # ── persistence ──────────────────────────────────────────────────────

    def save(self, output_path):
        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for name, df in self.sheets.items():
                df.to_excel(writer, sheet_name=name[:31], index=False)

        if self._pending_charts:
            self._write_charts(output_path)

    def _write_charts(self, output_path):
        import openpyxl
        from openpyxl.chart import BarChart, LineChart, PieChart, Reference

        wb = openpyxl.load_workbook(output_path)
        for sheet, chart_type, title, categories_col, value_cols in self._pending_charts:
            sheet_key = sheet[:31]
            if sheet_key not in wb.sheetnames or sheet_key not in self.sheets:
                continue
            ws = wb[sheet_key]
            df = self.sheets[sheet_key]
            if categories_col not in df.columns:
                continue
            cat_idx = df.columns.get_loc(categories_col) + 1
            n_rows = df.shape[0]

            chart_cls = {"bar": BarChart, "line": LineChart, "pie": PieChart}.get(chart_type, BarChart)
            chart = chart_cls()
            chart.title = title or f"{sheet_key} chart"
            cats = Reference(ws, min_col=cat_idx, min_row=2, max_row=n_rows + 1)

            for col_name in value_cols:
                if col_name not in df.columns:
                    continue
                val_idx = df.columns.get_loc(col_name) + 1
                data = Reference(ws, min_col=val_idx, min_row=1, max_row=n_rows + 1)
                chart.add_data(data, titles_from_data=True)
            chart.set_categories(cats)
            anchor_col = chr(ord("A") + df.shape[1] + 2)
            ws.add_chart(chart, f"{anchor_col}2")
        wb.save(output_path)
        self._pending_charts = []


HELP_TEXT = """\
Commands:
  /help                Show this help
  /exit, /quit         End the session (workbook is already saved)
  /sheets              List current sheets and their shape
  /show SHEET [N]      Print the first N rows of SHEET (default 10)
  /undo                Revert to the state before the last applied change
"""


def cmd_excel_chat(api_key, model, input_path=None, output_path=None, sheet_name=None,
                    temperature=0.3, max_tokens=4096, native=False):
    """native=True routes each turn through zc_skills_api.py's xlsx
    Skill (Anthropic's own maintained implementation, server-side in a
    code-execution container) instead of the hand-rolled pandas/openpyxl
    path below. See --excel-native. Requires Skills access on the
    account; the hand-rolled path here remains the default and the
    fallback for accounts without it."""
    if native:
        return _cmd_excel_chat_native(api_key, model, input_path=input_path,
                                      output_path=output_path, max_tokens=max_tokens)

    if pd is None:
        print("[ERROR] pandas is required for --excel. Install with: "
              "pip install pandas openpyxl", file=sys.stderr)
        sys.exit(1)

    from wire.coder import Coder

    try:
        session = ExcelSession(input_path, sheet_name)
    except (ImportError, ValueError, OSError) as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

    output_path = output_path or (
        re.sub(r"\.\w+$", "", input_path) + ".xlsx" if input_path else "excel_session.xlsx"
    )

    c = Coder(api_key=api_key, model=model, temperature=temperature, max_tokens=max_tokens)

    print(f"\033[94mAI Model Coder — Excel chat\033[0m  (model: {c.model})")
    print(f"Workbook: {output_path}  (saved after every applied change)")
    print("Type /help for commands, /exit to quit.\n")

    history = []
    while True:
        try:
            user_input = input("\033[92myou›\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue

        if user_input.startswith("/"):
            parts = user_input.split()
            cmd = parts[0].lower()
            if cmd in ("/exit", "/quit"):
                break
            if cmd == "/help":
                print(HELP_TEXT); continue
            if cmd == "/sheets":
                for name, df in session.sheets.items():
                    print(f"  {name}: {df.shape[0]} rows x {df.shape[1]} cols")
                continue
            if cmd == "/show":
                if len(parts) < 2 or parts[1] not in session.sheets:
                    print(f"[usage] /show SHEET [N] — sheets: {list(session.sheets)}")
                    continue
                n = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 10
                print(session.sheets[parts[1]].head(n).to_string())
                continue
            if cmd == "/undo":
                print("[reverted]" if session.undo() else "[nothing to undo]")
                session.save(output_path)
                continue
            print(f"[unknown command {cmd!r}; try /help]")
            continue

        prompt = f"Current data:\n{session.summary()}\n\nRequest: {user_input}"
        reply = c.generate(prompt, system=SYSTEM_PROMPT, history=history)

        match = _CODE_BLOCK.search(reply)
        if match:
            ok, message = session.apply_code(match.group(1))
            if ok:
                session.save(output_path)
                shapes = ", ".join(f"{n}: {d.shape[0]}x{d.shape[1]}" for n, d in session.sheets.items())
                print(f"\033[96mzc›\033[0m Updated and saved to {output_path} ({shapes})\n")
            else:
                print(f"\033[93mzc›\033[0m {message}\n")
        else:
            print(f"\033[96mzc›\033[0m {reply}\n")

        history.append({"role": "user", "content": user_input})
        history.append({"role": "assistant", "content": reply})

    print(f"\033[94mSession ended. Final workbook: {output_path}\033[0m")
    return output_path


def _cmd_excel_chat_native(api_key, model, input_path=None, output_path=None, max_tokens=4096):
    """--excel-native: same chat shape as cmd_excel_chat above, but every
    turn is a Messages API call carrying the xlsx Skill in a
    code-execution container (see zc_skills_api.py) — the workbook is
    built and edited entirely server-side. No local pandas/openpyxl
    dependency needed for this path; this CLI only uploads the starting
    file (if any, once) and downloads the resulting workbook after each
    turn that produces one.

    Slash commands from the hand-rolled path (/sheets, /show, /undo)
    aren't available here — the xlsx Skill owns the workbook, this CLI
    has no local copy of it to inspect or revert.
    """
    from wire.zc_files import FilesAPI
    from wire.zc_skills_api import SkillsApiClient, build_user_content, extract_output_file_ids

    files_api = FilesAPI(api_key=api_key, model=model)
    client = SkillsApiClient(api_key=api_key, model=model, max_tokens=max_tokens)

    output_path = output_path or (
        re.sub(r"\.\w+$", "", input_path) + ".xlsx" if input_path else "excel_session.xlsx"
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

    print(f"\033[94mAI Model Coder — Excel chat (native Skills API)\033[0m  (model: {model})")
    print(f"Workbook: {output_path}  (saved after every turn that produces one)")
    print("Type /exit to quit. (/sheets, /show, /undo aren't available in --excel-native.)\n")

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
            messages, skills=["xlsx"], container_id=container_id, has_file_uploads=has_uploads,
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

    print(f"\033[94mSession ended. Final workbook: {output_path}\033[0m")
    return output_path