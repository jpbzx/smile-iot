# Documentation

Academic artifacts, system specifications, and architectural reference for the SMILE-IoT project.

---

## Contents

### Core Documentation
- **[`SPEC.md`](SPEC.md)** — **Complete system specification** (fonte de verdade)
  - Architecture diagrams
  - Hardware/firmware/software details
  - Database schemas
  - MQTT protocol specification
  - Security considerations
  - Development roadmap

### Supporting Documents
- **[`AGENT_README.md`](AGENT_README.md)** — GitHub Copilot agent instructions
  - Agent behavior patterns
  - Commit policies
  - Diagnostic commands
  - Security best practices

- **[`SMILE-IoT_esqueleto.md`](SMILE-IoT_esqueleto.md)** — Initial project outline (legacy)
  - High-level system overview
  - Basic architecture concepts
  - *Note: Being consolidated into SPEC.md*

---

## Document Structure

```
docs/
├── SPEC.md                 # ⭐ Primary reference (always up-to-date)
├── AGENT_README.md         # Agent configuration & workflow
├── SMILE-IoT_esqueleto.md  # Legacy outline (to be deprecated)
└── README.md               # This file
```

---

## Documentation Guidelines

### For Developers
- **Start with [`SPEC.md`](SPEC.md)** for system-wide understanding
- **Check [`../README.md`](../README.md)** for quick start instructions
- **Read module-specific READMEs:**
  - [`firmware/README.md`](../firmware/README.md) — ESP32 code
  - [`software/README.md`](../software/README.md) — Dashboard & backend
  - [`hardware/README.md`](../hardware/README.md) — Circuit schematics

### For GitHub Copilot Agent
- **Follow [`AGENT_README.md`](AGENT_README.md)** patterns
- **Consult [`SPEC.md`](SPEC.md)** before proposing architecture changes
- **Never commit secrets** — use `.env` or secret managers

---

## Key Files by Topic

| Topic | Primary Document | Supplementary |
|-------|------------------|---------------|
| System Architecture | `SPEC.md` § 3 | `../README.md` § 2 |
| Firmware (ESP32) | `../firmware/README.md` | `SPEC.md` § 5 |
| Software (Dashboard) | `../software/README.md` | `SPEC.md` § 7 |
| Hardware (SCT-013) | `../hardware/README.md` | `SPEC.md` § 4 |
| MQTT Protocol | `SPEC.md` § 6 | `../firmware/README.md` |
| Database Schemas | `SPEC.md` § 8 | `../software/README.md` |
| Security | `SPEC.md` § 6.2 | `../README.md` § 9 |

---

## Maintenance

### Update Frequency
- **`SPEC.md`:** Update on every feature merge
- **`README.md` (root):** Update on major milestones
- **Module READMEs:** Update when API/interface changes

### Version Control
- Commit documentation changes **with** related code changes
- Use conventional commit messages: `docs: update SPEC.md with InfluxDB schema`

---

**⚡ For code execution instructions, see respective module directories**
