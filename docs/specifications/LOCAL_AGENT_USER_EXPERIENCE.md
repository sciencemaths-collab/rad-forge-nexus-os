# Local Agent User Experience

Status: frozen for Component BB

## Contract

- The loopback root serves a self-contained responsive interface with no CDN,
  analytics, third-party fonts, external images, or cross-origin requests.
- The interface covers password login, goal/project entry, candidate retrieval,
  complete human review, and exact-digest approval.
- It states before and after approval that no work is executed or published.
- Bearer material remains only in JavaScript memory; it is never placed in URL,
  local storage, cookies, HTML, or logs.
- Static responses use no-store, MIME protection, frame denial, no-referrer, and
  a restrictive Content Security Policy.
- Forms are keyboard operable and labelled; status changes use an ARIA live
  region; focus is visible; reduced-motion preferences are respected.
- The README supplies a copyable private-password, configuration, attestation,
  startup, browser, and secret-handling path.
- The interface remains loopback-only. BB does not deploy or publish a service.

## Public claim

The repository may be described as public open-source software and as a qualified
local planning/review Agent baseline. It may not be described as production-ready,
live-model-qualified, universally autonomous, or safe for arbitrary tools without
their separate registration and evidence.
