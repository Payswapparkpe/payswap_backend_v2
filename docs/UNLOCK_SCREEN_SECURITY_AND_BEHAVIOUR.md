# Unlock Screen – Security & Behaviour (R&D)

## Purpose

After session lock (manual or inactivity), the user must re-enter a 4-digit PIN to access the app. The unlock screen is the **only** active page until they unlock or sign in again. No navigation (including Back) should show previous protected pages.

---

## What MUST happen (security)

| Requirement | How it’s enforced |
|------------|-------------------|
| Back button must not show previous page (dashboard, etc.) | **Client:** History API – on load we `pushState` so the “previous” entry is also the unlock URL. On `popstate` (Back), we `pushState` again so Back never leaves the unlock page. |
| No access to protected routes without auth | **Server:** Session is cleared on lock. `SessionLockMiddleware` redirects any request to a protected path (when user is anonymous and has `lock_identity`) to `/auth/unlock-with-pin/`. |
| 30 min timer only for this “visit” to unlock | **Server:** `lock_started_at` cookie set when landing with `new_lock=1` (from Lock screen) or when cookie was missing (e.g. after unlock we clear it). Refresh does not send `new_lock=1`, so timer is not reset. |
| Only two ways to leave unlock screen | **Design:** (1) Enter correct PIN → full session restored, redirect to `next`. (2) “Unlock using Password” / X → go to signin. Timer expiry → redirect to signin and clear lock cookies. |
| No bypass via URL / direct navigation | **Server:** Any GET to a protected URL while anonymous with `lock_identity` is redirected to unlock. So typing URL or “back” to dashboard still lands on unlock. |

---

## What must NOT happen

| Anti-requirement | Why |
|------------------|-----|
| Back must not open dashboard or any protected page | Otherwise user could see or interact with protected content without entering PIN. |
| Refresh must not reset 30 min timer | Timer is “per visit”; only a new lock (manual or after unlock) should start a fresh 30 min. |
| Unlock screen must not be skippable | Enforced by middleware + no usable “previous” history entry (Back stays on unlock). |
| Protected pages must not load without session | Middleware runs before view; anonymous + `lock_identity` → redirect to unlock. |

---

## Flow summary

1. **Lock (manual or inactivity)**  
   Session cleared, `lock_identity` cookie kept. Redirect to `/auth/unlock-with-pin/?next=...&new_lock=1` (manual lock) or `/auth/unlock-with-pin/?next=...` (middleware after inactivity; cookie was cleared on last unlock so timer starts fresh).

2. **Unlock page load**  
   - If `new_lock=1`: server sets `lock_started_at` cookie and redirects to same URL without `new_lock=1`.  
   - Client: one `pushState(unlockUrl)` so Back goes to same URL (same document).  
   - `popstate`: on Back, push same URL again so user never leaves unlock.

3. **User presses Back**  
   Browser moves to previous history entry; we made it the same unlock URL, so the document stays the unlock page. `popstate` runs, we push the unlock URL again. Result: Back does nothing visible; user stays on unlock.

4. **User refreshes**  
   GET unlock without `new_lock=1`; server uses existing `lock_started_at` → timer continues.

5. **User unlocks**  
   POST PIN → success → clear `lock_started_at` cookie, create session, redirect to `next`. No Back to unlock from there (normal app history).

6. **Timer expires**  
   JS redirects to `/auth/unlock-expired/` → server clears lock cookies and redirects to signin.

---

## Files involved

- **Template:** `portal/templates/portal/auth/unlock_with_pin.html` – History API script (pushState + popstate).
- **Views:** `portal/views.py` – `UnlockWithPinView` (GET/POST), `lock_screen_view`, `unlock_expired_view`; cookie handling and `new_lock=1` redirect.
- **Middleware:** `portal/middleware.py` – `SessionLockMiddleware` redirects anonymous + `lock_identity` to unlock.
- **Utils:** `portal/utils/session_lock.py` – `get_user_from_lock_cookie`, `can_offer_pin_unlock`.

---

## Testing (manual)

1. Log in, set PIN, then Lock screen.  
2. On unlock page, press Back repeatedly → URL and content must stay on unlock; no dashboard.  
3. Refresh → timer must not reset (e.g. same countdown).  
4. Unlock, then Lock again → timer must show full 30 min.  
5. With DevTools, try navigating to `/dashboard/` → must redirect to unlock.  
6. Let timer hit 0 → must redirect to signin and lock cookies cleared.
