# Supabase production CA

`supabase-prod-ca-2021.crt` is the public Supabase production root CA used by the
application's PostgreSQL session-pooler connections. The certificate URL is the
production URL referenced by Supabase Studio's SSL Configuration UI at pinned
Supabase repository revision `4ab54b935919ba3f4bb92f436ae4e757108e4f8a`:

- [Supabase Studio SSL configuration](https://github.com/supabase/supabase/blob/4ab54b935919ba3f4bb92f436ae4e757108e4f8a/apps/studio/components/interfaces/Settings/Database/SSLConfiguration.tsx)
- [Certificate download](https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt)

The downloaded file's SHA-256 is `700723581420DD1AC98FD7E9AC529F0EF210EADCAF87FC868A3AD7D114C2F3B7`.
X.509 parsing confirmed subject and issuer `CN=Supabase Root 2021 CA, O=Supabase Inc,
L=New Castle, S=Delware, C=US`, validity from 2021-04-28 10:56:53 UTC through
2031-04-26 10:56:53 UTC, CA basic constraints, and `keyCertSign` usage. The
certificate is packaged only at `/app/certs/supabase-prod-ca-2021.crt`; it does
not modify the image's global trust store.

Production defaults to `sslmode=verify-full` with this file. An explicit
`sslrootcert` or supported `sslmode` in `DATABASE_URL` remains honored subject to
the validation rules in settings. The image workflow checks the packaged CA
fingerprint and performs a credential-free PostgreSQL SSLRequest followed by a
Python SSL hostname-verifying handshake. This check does not authenticate the
application database role; that remains a separate operator check.
