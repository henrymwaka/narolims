# NARO-LIMS Lab Configuration Principles

## Purpose
Define how laboratories are configured in NARO-LIMS without code duplication,
hard-coding, or template forks.

## Core Rules

1. No lab-specific templates
2. No hard-coded laboratory logic in views
3. All lab behavior must be data-driven
4. Configuration precedes customization
5. Workflows are assigned, not embedded
6. Metadata schemas define fields, not models

## Forbidden Anti-Patterns

- if lab.name == "Soils"
- Duplicate templates per lab
- Per-lab model subclasses
- Feature flags tied to lab names

## Architectural Contract

Any change that violates these principles must be rejected at PR review.
