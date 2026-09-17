# T46 — Final Demo Runbook

Status: Phase 3 template, to be filled in and executed by Satish around the
actual final demo. **No stakeholder attendance, feedback, questions asked,
or outcome is recorded in this document, because no real final demo has
happened yet in this engagement.** Every bracketed placeholder below is
something only Satish can truthfully fill in after the real event.

This document is the step-by-step script for the day of the real demo —
narrower and more rehearsed than T45's preparation material, which covers
broader prep.

## 1. Logistics

- **Date/time:** [Satish: fill in]
- **Audience:** [Satish: fill in — names/roles of actual attendees]
- **Format:** [Satish: fill in — in-person / video call / recorded]
- **Presenter:** Satish Jagtap

## 2. Environment freeze checklist (do this the morning of, not the night before)

- [ ] Pull latest code, run `pytest -v` one final time, confirm pass count
- [ ] Restart backend + frontend fresh (avoid stale in-memory state from
      earlier testing sessions)
- [ ] Re-ingest the demo document set from a known-clean state
- [ ] Confirm whether `GEMINI_API_KEY` is set for this run and note it (so
      Q&A about "real Gemini vs. fallback" has an honest, current answer)
- [ ] Close unrelated terminal history/browser tabs that might reveal
      internal notes or unrelated data

## 3. Scripted walkthrough

Follow the 9-step narrative in `docs/T45_Demo_Preparation.md` section 1.
Do not deviate into ad-hoc queries during the actual demo unless a
stakeholder asks — ad-hoc queries against an untested prompt/document
combination can surprise you live; the fallback paths are honest but
that doesn't mean they look polished on a screen share.

## 4. Live Q&A — reference `docs/T45_Demo_Preparation.md` section 4 for
prepared honest answers to expected questions. Do not improvise an answer
that overstates what has been tested — "I haven't verified that yet, I'll
follow up" is always an acceptable answer.

## 5. Post-demo record (fill in immediately after, while memory is fresh)

**[Satish: fill in after the real demo — do not let an AI assistant
draft this section, since it did not attend the demo and cannot know what
was actually said or asked]**

- Attendees who actually joined:
- Questions actually asked:
- Feedback actually received:
- Follow-up items actually committed to:
- What actually went well:
- What actually did not land well or broke live:

## 6. Explicit reminder

Per this project's standing rule: no mentor feedback, peer review,
stakeholder attendance, or demo outcome may be fabricated or inferred by
an AI assistant on Satish's behalf. Section 5 above must be filled in by
Satish from the real event, not generated.

---
⚠️ AI-generated template. Section 5 requires human authorship from the
actual event — do not fill it in synthetically.
