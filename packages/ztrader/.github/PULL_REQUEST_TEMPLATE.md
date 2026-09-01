## Description

## Language and Coding Standards
- **Communication**: Always talk in Thai when interacting with users.
- **Code & Technical Assets**: All code, comments, documentation, and technical definitions must be in English.

Please include a summary of the changes and the related issue. List any dependencies that are required for this change.

Fixes # (issue)

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Refactoring/Code cleanup

## Safety & Security Checklist

- [ ] No API keys, passphrases, tokens, or credentials are hardcoded or committed.
- [ ] All database queries use parameterized SQL or SQLAlchemy constructs (SQL Injection Safe).
- [ ] Execution mode defaults to `paper` and live trading remains gated by safety limits.
- [ ] All new strategy/risk logic has been thoroughly tested.
- [ ] No local `.env` files are tracked.

## Testing & Coverage

- [ ] All unit and integration tests pass successfully.
- [ ] Code coverage has been maintained or increased (minimum 80%).

Test execution command run:
```bash
PYTHONPATH=backend/src pytest backend/tests/
```
