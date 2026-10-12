<!--
Template for one report to cSurvey's author (cepelabs/cSurvey). Copy this file to
upstream/NNNN-short-name/PR.md (or ISSUE.md when there is no patch), fill it in, and
delete these comments. Everything below the line is what gets pasted into GitHub.
Write in English. Keep it short. The author knows the code, so show the evidence.
Add the patch beside it as fix.patch (see README.md "Making the patch").
-->

---

# <What is wrong, in one line — the title of the PR / issue>

## Problem

<What the user sees: the message, the wrong print, the crash. Paste the exact error text in a code
block. Say which cSurvey version (Help › About, or the cSurveyPC.exe date).>

## Cause

<File and line (`cSurveyPC/xxx.vb:123`), the few lines of code that do it, and why that is wrong. If it
only happens in some setups (a file system, a locale, a TopoDroid version), say which one and how you
know.>

## Fix

<The change, as a short code block, and why it is safe: who else reads what you changed, and what stays the
same for everybody else. For an issue without a patch: what you would expect instead.>

## How to reproduce

1. <The smallest steps from a clean start. Attach a tiny .csx when a file is needed. Never attach a club
   survey with real coordinates without asking the club.>
2. …
3. → <what happens>

## Tested

- <What was checked and how: built and run? only reasoned from the code? which files?>
