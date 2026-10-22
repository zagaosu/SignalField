# Security

SignalField is a local-first demo. It binds to `127.0.0.1` by default and has no
authentication, multi-user isolation, TLS, or public-deployment hardening. Do not
expose it directly to the internet.

## Secrets

- Put real credentials only in the server-side `.env` file.
- `.env` is ignored by Git; only `.env.example` is committed.
- The API returns missing configuration names, never key values.
- Keys are never written to run state, the browser, or application logs.

## URL and content safety

- The reader accepts only public `http/https` URLs.
- Credentials in URLs, loopback/link-local/private destinations, and unsafe
  redirects are rejected.
- Page content is treated as untrusted text; it cannot issue instructions to the
  agent, and scripts are not executed.
- Fetched pages are not persisted in full; only source metadata, short excerpts,
  and verified quote spans are stored.

## Reporting

Open a private security advisory in the GitHub repository rather than posting a
working exploit publicly. This is a portfolio project without a bug-bounty
program.
