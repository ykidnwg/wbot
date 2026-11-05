# Facebook Pages integration

## Contract reviewed

The adapter follows the official Meta documentation reviewed on 2026-11-01:

- [Access Tokens](https://developers.facebook.com/documentation/facebook-login/guides/access-tokens)
- [Pages API getting started](https://developers.facebook.com/documentation/pages-api/getting-started)
- [Pages API posts](https://developers.facebook.com/documentation/pages-api/posts)

The configured default Graph API version is `v26.0`, and it is supplied through
`META_GRAPH_API_VERSION` rather than duplicated in application code.

## OAuth and permissions

The server-side authorization URL requests:

- `pages_show_list`
- `pages_manage_metadata`
- `pages_manage_posts`
- `pages_manage_read_engagement`

The callback exchanges the authorization code server-side, calls `/me`, then
calls `/me/accounts` to discover Pages and Page access tokens. Page tokens are
stored only as encrypted server-side envelopes. They are never returned to the
browser, logs, or audit details.

Meta app review and role/test-user requirements apply before non-development
accounts can use these permissions. Page access and publishing capabilities are
limited by the permissions and tasks granted to the connected Meta user.

## Security decisions

- OAuth state is 48 random URL-safe bytes, hashed in PostgreSQL, expires after
  ten minutes, and is consumed once under a row lock.
- The callback requires the authenticated WBot session and the exact configured
  redirect URI.
- Access tokens use AES-GCM with a 32-byte URL-safe base64 key from
  `TOKEN_ENCRYPTION_KEY`.
- Missing Meta credentials or encryption key produces `NEEDS_CREDENTIALS`; the
  application does not simulate a connected account.
- The current milestone discovers and stores Pages. It does not publish posts.

## Required configuration

Set these only in a private environment or secret manager:

```text
META_APP_ID=
META_APP_SECRET=
META_OAUTH_REDIRECT_URI=https://your-api.example.com/api/v1/social/oauth/facebook/callback
META_GRAPH_API_VERSION=v26.0
TOKEN_ENCRYPTION_KEY=
```

The redirect URI must match the URI configured in the Meta app exactly. Generate
the encryption key with a trusted secret-management tool and rotate it only with
a planned token re-encryption migration.

## Publishing (implemented)

The worker publishes text to `/{page-id}/feed` and images to `/{page-id}/photos`
with the encrypted Page access token. A post is marked `published` only when the
Graph response returns an `id` or `post_id`.

- Authentication/permission/validation failures stop without retrying.
- Rate limits and non-ambiguous temporary/network failures retry with backoff.
- Timeouts and 5xx responses during the POST are marked `uncertain` because the
  post may have been created. They are never retried automatically; a human must
  check the Page before using the manual retry endpoint.
- The published URL is derived from the returned post id when it contains a
  numeric story id; otherwise the external id is stored without inventing a URL.
- Tests use a fake publisher and make no Meta API calls. Live publishing was not
  exercised in this environment because Meta credentials and a connected Page
  were not configured.
