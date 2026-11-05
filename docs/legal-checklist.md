# Legal checklist before scaling outreach

**Not legal advice.** This lists the questions to settle, with a qualified advisor where needed,
before sending research emails at any volume. It maps each point to what Preuve already does and
what you, the operator, still have to decide. PRD §36–§37 require this review before scaling
US/EU outreach.

## Who you're writing to and why

- [ ] **Purpose.** Outreach is customer research, one to one, written and approved by a person
      (Preuve's approval gate). Keep it that way: no bulk sends, no marketing offers.
- [ ] **Recipients are business contacts** found on public business pages, with the source kept
      for each (Preuve stores the URL, date and quote). Don't add personal addresses; the
      privacy check flags free-mail ones.
- [ ] **Lawful basis (GDPR / UK GDPR, if writing to people in the EU/UK).** Most cold B2B
      research relies on *legitimate interests*. Write down a short legitimate-interests
      assessment: your purpose, why email to this person is necessary, why it's balanced (low
      volume, relevant to their role, easy opt-out).
- [ ] **Transparency.** Within a month of collecting someone's data (at the latest in your first
      email) tell them who you are, why you have their address, where you found it, and how to
      object or have it deleted. Preuve's footer covers identity and opt-out; add a line on the
      source and a link or note on how you handle their data.

## Each email (CAN-SPAM in the US; PECR in the UK; ePrivacy rules in the EU)

- [ ] **Accurate sender and subject.** Real name and address in `From`; subject describes the
      email. Preuve uses the configured real identity and forbids fake company identities.
- [ ] **A working opt-out in every email**, honoured promptly (CAN-SPAM: within 10 business
      days). Preuve adds an unsubscribe link and `List-Unsubscribe` headers, and reading
      "stop"/"unsubscribe" replies suppresses the sender automatically. **The link only works
      for recipients once Preuve has a public URL** (see `docs/operations.md`).
- [ ] **Postal address** (CAN-SPAM requires a valid physical postal address in commercial
      email): set `EMAIL_POSTAL_ADDRESS`.
- [ ] **PECR (UK) and EU national rules:** unsolicited email to *individual* subscribers needs
      consent; to *corporate* subscribers it's generally allowed with identity and an opt-out,
      but sole traders and some partnerships count as individuals, and some EU countries are
      stricter. Decide which countries you'll write to.

## Data rights and retention

- [ ] **Access and deletion requests:** Settings → Privacy looks a person up by email, exports
      everything as JSON and erases it (suppressing the address and blocking re-import). Answer
      within one month (GDPR).
- [ ] **Retention:** page text is kept 30 days; never-contacted prospects are flagged after
      180 days. Decide how long to keep replies and interview notes once a case is closed, and
      delete cases you no longer need.
- [ ] **Records:** keep the legitimate-interests assessment and a note of this checklist's
      decisions.

## Processors and transfers

- [ ] **Gemini** (Google) receives research text; reply and interview text only if you set
      `ALLOW_PRIVATE_TO_GEMINI=true`. If you enable it, note Google as a processor and the
      transfer outside the EU/UK.
- [ ] **Your mailbox provider** (e.g. Gmail) processes every email; **Sentry** receives error
      reports only if `SENTRY_DSN` is set (scrubbed of request and personal data).
- [ ] **Backups** contain personal data: keep `BACKUP_DIR` somewhere access-controlled, and
      remember that deleted people survive in older backups until they rotate out (14 days).

## Volume and reputation

- [ ] Keep the daily limit low (`OUTREACH_DAILY_LIMIT`, default 20) and the 30-day per-address
      cooldown. Watch bounces (auto-suppressed).
- [ ] Authenticate your sending domain (SPF, DKIM, DMARC) with your mail provider.
