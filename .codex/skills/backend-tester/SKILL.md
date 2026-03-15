---
name: backend-tester
description: Use this skill when the task is to test backend behavior, especially Django or HTTP APIs, including endpoint validation, auth checks, error handling, regression testing, query-path verification, and writing or reviewing backend automated tests.
---

# Backend Tester

## Overview

This skill is for validating backend behavior with emphasis on correctness, regressions, and test coverage.

## When To Use

Use this skill when the user asks for work involving:

- Backend regression testing or bug reproduction
- Django views, forms, auth, middleware, or API endpoint validation
- Automated tests for server-side flows
- HTTP contract checks, status codes, payload validation, and edge cases
- Backend investigation using available tooling, including MCPs

## Testing Approach

- Read the existing tests and project conventions before adding new ones.
- Prefer the narrowest test that proves the behavior: unit, integration, or request-level.
- Cover both expected success paths and relevant failure or permission paths.
- Verify database side effects when the endpoint changes persisted state.
- Call out flaky assumptions, hidden fixtures, and missing isolation.

## MCP Usage

- Use the available `playwright` MCP when request-level validation is useful.
- Use Playwright HTTP methods to exercise backend routes directly when browser rendering is unnecessary.
- Use response assertions to verify status, body fragments, and error behavior.
- Use browser console logs only when backend failures surface through frontend execution paths.

## Review Checklist

- Is the failing or changed backend behavior reproduced by a test?
- Are authentication and authorization outcomes covered?
- Are validation and error responses asserted explicitly?
- Are database writes, transactions, or side effects verified?
- Is the chosen test level fast enough and specific enough?

