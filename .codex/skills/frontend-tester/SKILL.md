---
name: frontend-tester
description: Use this skill when the task is to test frontend behavior, including page rendering, interactivity, navigation, form flows, responsive checks, accessibility basics, and end-to-end regressions using available browser automation MCPs.
---

# Frontend Tester

## Overview

This skill is for validating frontend behavior with emphasis on user flows, rendering correctness, and end-to-end regressions.

## When To Use

Use this skill when the user asks for work involving:

- UI regression testing
- Form submission flows and navigation checks
- Browser-based validation of Django templates or frontend pages
- Responsive or interaction-state verification
- End-to-end testing using available MCPs

## Testing Approach

- Start from the user-visible behavior, not implementation details.
- Prefer stable selectors and assertions tied to actual outcomes.
- Validate main flows first, then key error or empty states.
- Check keyboard and focus behavior when forms or dialogs are involved.
- Keep tests deterministic and avoid timing-based assertions where possible.

## MCP Usage

- Use the available `playwright` MCP as the default browser automation tool.
- Drive full page flows, clicks, fills, and navigations through Playwright.
- Capture visible text, HTML, screenshots, and console logs when debugging failures.
- Use HTTP response expectations when frontend actions depend on backend requests.

## Review Checklist

- Does the tested flow reflect how a user actually uses the interface?
- Are success, failure, and validation states covered where relevant?
- Are selectors resilient to incidental markup changes?
- Is the test reliable across normal local runs?
- Were browser console errors checked when behavior looked inconsistent?

