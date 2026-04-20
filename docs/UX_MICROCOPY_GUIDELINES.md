# UX Microcopy Guidelines

This guide defines text rules for user-facing UI in Payswap/ParkPe.

## Goals

- Keep UI clean, short, and scannable.
- Avoid text overflow that breaks card alignment.
- Maintain one consistent product voice.

## Language Rules

- Use clear English for all customer/admin-facing UI copy.
- Do not use Hinglish or mixed-language text in UI labels/help text.
- Prefer active voice and direct instructions.

## Length Rules

- Card title: <= 3 words where possible.
- Card subtitle/helper line: <= 70 characters preferred.
- Button labels: 1-3 words.
- Empty-state description: 1 short sentence.
- Avoid multi-sentence helper text inside dense cards.

## Style Rules

- Say what users can do, not implementation details.
  - Good: `Add flow steps in Admin to enable orchestration.`
  - Avoid: long explanations of internal modules unless required.
- Use consistent terms:
  - `Add Vehicle`, `View All`, `Quick Actions`, `Save`, `Cancel`
- Use sentence case for helper text.
- Avoid filler words like "just", "basically", "simply", "now".

## Alignment-Safe Copy Patterns

- Prefer concise numeric hints:
  - `Partial payment: min ₹X, max ₹Y`
- Keep warnings short:
  - `Cart total exceeds limit. Remove items or pay the cart first.`
- Keep confirmations short:
  - `Redeem this voucher for cart total (N bills, ₹X)?`

## Content to Avoid in Tight UI Areas

- Long legal-style explanations inside cards.
- Repeated instructions in multiple adjacent sections.
- Long parenthetical phrases when a short label works.

## Review Checklist (Before Merge)

- Is every visible string in clear English?
- Can each helper line be shortened further?
- Does any text wrap into 3+ lines inside cards?
- Do action labels follow existing app terminology?
- Are warnings concise and unambiguous?

## Scope

Apply to:
- Frontend app screens (`frontend/projects/parkpe/src/...`)
- Portal templates (`backend/portal/templates/...`)
- Modal copy, empty states, helper text, button labels, tooltips.
