# ServiceMind Collaboration Notes

## Response and delivery style

- Read the project documents in `README.md` and `docs/` before planning or implementing new modules.
- Summarize the MVP as a whole before moving into implementation details for a new phase.
- Use incremental delivery only: develop one module at a time, validate it locally, and wait for confirmation before moving to the next module.
- Do not dump the full MVP implementation at once.

## Per-module workflow

For each module:

1. Explain the scope, business goal, and files involved.
2. Implement only that module's code.
3. Provide local run and test commands.
4. Verify the module with focused self-tests.
5. Report risks, limitations, and next-step boundaries clearly.

## Code explanation requirements

- When the user asks for explanation or review, provide deep per-file analysis instead of short summaries.
- For each backend file, explain:
  - file location
  - module responsibility
  - design intent
  - role in the overall architecture
  - dependencies and call relationships
  - core implementation logic
  - current risks and hidden bug possibilities
  - extensibility and performance limitations
  - validation standards and debugging approach
- Also explain how the current infrastructure layer works end to end across response models, exception handling, middleware, trace propagation, and health checks.

## Engineering posture

- Keep implementations modular, low-coupled, and easy to test.
- Prefer explicit interfaces and standardized response formats.
- After each module, stop and wait for user confirmation before continuing.
