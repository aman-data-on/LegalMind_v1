# LegalMind V1 — Document Model

Source: all_lock.md, lines 1–1140 (Step 6). Canonical source: all_lock.md (Steps 1-9).

---

## Step 6 — Document Types vs Legal/Regulatory References

**Status: LOCKED**

These are two different concepts.

### Document Type

Document Type answers:

> "What kind of document is this?"

Initial V1 types:

* MSA — Master Services Agreement
* NDA — Non-Disclosure Agreement
* TOS — Terms of Service
* SLA — Service Level Agreement
* DPA — Data Processing Agreement
* AUP — Acceptable Use Policy
* Privacy Policy
* Order Form
* Amendment / Addendum
* Other

A document can be classified by source:

```text
Document Type = MSA
Source = Organization
```

or:

```text
Document Type = MSA
Source = Counterparty
```

### Legal / Regulatory Reference

A Legal/Regulatory Reference answers:

> "What law, regulation, statute, or legal requirement may be relevant?"

Examples:

* DPDP Act
* Information Technology Act
* GDPR
* Sector-specific regulations

These are not contract types.

Example:

```text
ABC MSA
 │
 ├── Compared with → LeapSwitch Standard MSA
 │
 └── Relevant to → DPDP Act
```

Note: the exact document taxonomy beyond this initial V1 list, and the regulatory reference workflow, remain **Status: NOT YET SPECIFIED** per the source text.
