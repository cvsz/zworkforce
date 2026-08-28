# Contributing Guidelines for Zaapi Clone

Thank you for contributing to the Zaapi conversational commerce clone project! Review this document to align on development standards, testing requirements, and branch workflows.

---

## 1. Branch Strategy
* **`main`**: Production-ready branch. Do not commit directly to `main`.
* **`feature/*`**: Create feature branches from `main` for developing new modules (e.g. `feature/inbox-search`).

---

## 2. Coding Standards
* **Vanilla CSS**: Global theme overrides must use variables inside `src/index.css`. Keep colors aligned with Zaapi emerald green (`#00c28e`).
* **Icons**: Use `lucide-react` library assets. Avoid importing custom SVGs unless necessary.
* **Pure States**: Keep React component states optimized. Avoid memory leaks inside simulator event listeners.

---

## 3. Pull Request Checklist
Before opening a PR, ensure you run:
1. **Compilation Check**:
   ```bash
   npm run build
   ```
2. **Commit Alignment**: Ensure your branch is rebased on top of `main` to prevent merge conflicts.
