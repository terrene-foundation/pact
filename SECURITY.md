# Security Policy

The CARE Platform handles cryptographic trust chains, constraint enforcement, and
tamper-evident audit records. Vulnerabilities in these areas have direct trust
implications. We take security seriously and appreciate responsible disclosure.

## Supported Versions

| Version | Supported     |
| ------- | ------------- |
| 0.1.x   | Yes (current) |

As the project is pre-1.0, only the latest release on the `main` branch receives
security patches. When 1.0 is released, this table will be updated with a formal
support window.

## Reporting Vulnerabilities

**Do not open a public GitHub issue for security vulnerabilities.**

Send vulnerability reports to:

**security@terrene.foundation**

Include the following in your report:

1. **Description** -- what the vulnerability is and its potential impact
2. **Reproduction steps** -- minimal steps to reproduce the issue
3. **Affected component** -- which module or file is involved
4. **Severity assessment** -- your assessment of the severity (Critical, High,
   Medium, Low)

### Response Timeline

- **Acknowledgment**: within 48 hours of receipt
- **Initial assessment**: within 5 business days
- **Patch timeline**: depends on severity (see below)

| Severity | Target Patch Time |
| -------- | ----------------- |
| Critical | 7 days            |
| High     | 14 days           |
| Medium   | 30 days           |
| Low      | Next release      |

### Researcher Acknowledgment

After a vulnerability is patched and disclosed, we publicly credit the reporter
(unless they prefer to remain anonymous). Credits are listed in the release notes
for the patching version.

## Responsible Disclosure Process

1. **Reporter** sends details to security@terrene.foundation
2. **Maintainers** acknowledge within 48 hours and begin assessment
3. **Maintainers** develop and test a patch (timeline based on severity)
4. **Maintainers** notify the reporter before public disclosure
5. **Patch** is released with a security advisory
6. **Reporter** is credited in release notes (if desired)

We ask reporters to:

- Allow a reasonable window for patching before public disclosure
- Not exploit the vulnerability beyond what is necessary to demonstrate it
- Not access or modify data belonging to other users

## Security-Sensitive Areas

The following areas of the codebase are security-critical. Changes to these modules
require heightened review.

### Critical Severity

- **Trust chain cryptography** (`care_platform/trust/`) -- Genesis records,
  delegation chains, capability attestations, and their cryptographic integrity.
  A bypass here breaks the entire trust model.

- **Constraint enforcement** (`care_platform/constraint/`) -- Constraint envelope
  evaluation and the verification gradient engine. A bypass could allow an agent to
  exceed its authorized permissions.

- **Audit chain integrity** (`care_platform/audit/`) -- Tamper-evident audit anchors
  and chain verification. Compromising the audit chain destroys accountability.

### High Severity

- **Approval queue** (`care_platform/execution/approval.py`) -- Human-in-the-loop
  approval for HELD actions. A bypass could allow self-approval of restricted
  actions.

- **Platform configuration** (`care_platform/config/`) -- Configuration parsing and
  validation. Malformed configuration could weaken constraints.

### Medium Severity

- **Session management** (`care_platform/execution/session.py`) -- Session state
  and checkpoints. Information disclosure through session data.

- **Audit export** (`care_platform/audit/anchor.py`, `export` method) -- Audit
  chain export for external review. Sensitive operational data could be disclosed
  if export filtering is bypassed.

## Security Practices

### No Hardcoded Secrets

All API keys, credentials, and sensitive configuration must come from environment
variables (loaded from `.env`). The codebase enforces this through:

- The `.env.example` template (no real values)
- `.gitignore` excluding `.env` files
- Code review requirements documented in `rules/security.md`

Never commit files containing secrets. If a secret is accidentally committed,
treat it as compromised and rotate it immediately.

### Dependency Security

- Dependencies are pinned with minimum versions in `pyproject.toml`
- We monitor for known vulnerabilities in dependencies
- Security-relevant dependency updates are applied promptly
- Contributors should run `pip audit` (or equivalent) before submitting PRs that
  add or update dependencies

### Contributor Security Checklist

Before submitting a PR that touches trust, crypto, or enforcement modules:

- [ ] No secrets, API keys, or credentials in the diff
- [ ] All user input is validated before use
- [ ] No `eval()`, `exec()`, or `subprocess.call(..., shell=True)` on user input
- [ ] Database queries use parameterized queries or ORM (no string interpolation)
- [ ] Constraint envelope changes maintain monotonic tightening invariant
- [ ] Audit chain changes preserve tamper-evidence properties
- [ ] Trust chain changes preserve cryptographic integrity
- [ ] Error messages do not leak sensitive internal state

## Scope

### In Scope

- All code in the `care_platform/` package
- Configuration parsing and validation
- Trust chain and cryptographic operations
- Constraint enforcement logic
- Audit chain integrity
- CLI commands that modify trust or constraint state
- Dependencies used by the platform

### Out of Scope

- The Kailash SDK itself (report to the Kailash project)
- The EATP SDK itself (report to the EATP project)
- Third-party services integrated via API keys
- Issues that require physical access to the deployment host
- Social engineering attacks against maintainers
- Denial-of-service attacks against the hosting infrastructure

## License

The CARE Platform is Apache 2.0 licensed, owned by the Terrene Foundation.
This security policy applies to the open-source codebase at
https://github.com/terrene-foundation/care.
