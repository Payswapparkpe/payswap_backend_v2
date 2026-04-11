# Parkpe Auth Storage – Production Security

## Current behaviour

- **Token and user** are stored in **localStorage** after login/OTP verify so that **reload does not log out** the user.
- Keys: `parkpe_auth_token`, `parkpe_auth_user`.
- On **401**, session is cleared from memory and localStorage and the user is redirected to login.

## Is it safe for production?

**Short answer:** It is **acceptable for production** if you follow standard security practices. It is **not** the most secure option; the strongest approach is httpOnly cookies (see below).

### Risks of storing JWT in localStorage

1. **XSS (Cross-Site Scripting)**  
   Any script that runs on your origin (e.g. malicious third-party script, compromised dependency) can read `localStorage` and steal the token. So the token is visible to JavaScript on the same origin.

2. **Persistence**  
   The token stays until the user logs out or it expires. On a shared device, someone else could use the same browser and still be logged in if the user did not log out.

### Why it is still used in production

- Many SPAs use this pattern and ship to production.
- It is **not less secure** than keeping the token only in memory (which we had before); we only added persistence. Memory is also readable by JS in case of XSS.
- With **HTTPS**, **short-lived tokens**, and **hardening against XSS**, risk can be kept at an acceptable level.

### Production best practices (recommended)

1. **HTTPS only**  
   Use HTTPS everywhere in production. Do not serve the app or API over HTTP.

2. **Short token lifetime**  
   Backend (e.g. SimpleJWT) should use a reasonable access token expiry (e.g. 15–60 minutes). Refresh token (if any) should be stored and used according to your security policy.

3. **Harden against XSS**  
   - Prefer trusted dependencies and keep them updated.
   - Avoid `innerHTML` / `dangerouslySetInnerHtml` with user or external data; use safe binding.
   - Consider **Content-Security-Policy (CSP)** headers to limit script sources.

4. **No sensitive data in token payload**  
   JWTs are often base64-decoded. Do not put sensitive PII or secrets in the payload; keep it to what the app needs (e.g. user id, role).

5. **Logout and 401**  
   We already clear session (memory + localStorage) on logout and on 401, so expired or invalid tokens do not stay in storage.

### Stronger option: httpOnly cookies

For **higher security** (e.g. strict compliance or high-risk flows):

- Backend should **set the access token in an httpOnly, Secure, SameSite cookie** instead of (or in addition to) returning it in the JSON body.
- Frontend would **not** store the token in localStorage or in memory; the browser would send the cookie automatically with `credentials: 'include'`.
- **XSS cannot read httpOnly cookies**, so token theft via script is much harder.

This requires backend changes (e.g. auth_parkpe to set cookie and optionally still return a minimal body) and frontend changes (no token in AuthService, use `withCredentials: true` for API calls). We can do this in a follow-up if you want to move to cookie-based auth.

## Production deployment checklist

**Jab app production pe deploy karo, ye ensure karo:**

1. **HTTPS only**  
   App aur API dono **HTTPS** par chalne chahiye. HTTP production mein use mat karo (token/session hijack ka risk).
2. **Token expiry**  
   Backend `.env` mein `JWT_ACCESS_TOKEN_LIFETIME=3600` (60 min) ya 900–3600 ke beech rakho.
3. **CSP**  
   Frontend `index.html` mein CSP meta hai; production server par optional: strict CSP **header** bhi set kar sakte ho.
4. **Token payload**  
   JWT mein sirf `user_id` (aur standard claims) – koi PII/sensitive data token mein nahi.

## Summary

| Aspect              | Status / Recommendation |
|---------------------|-------------------------|
| Production use      | **Acceptable** with HTTPS, short token lifetime, and XSS hardening. |
| Reload persistence  | **Implemented** via localStorage. |
| Logout / 401        | **Implemented** – session cleared from memory and localStorage. |
| Stronger option     | Use **httpOnly cookie** for token (backend + frontend change). |
