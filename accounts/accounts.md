# Accounts – Authentication, User Management, and Gitea Integration Module

This module provides the full system for **authentication**, **user management**, **invitations**, **password resets**, and **automatic synchronization with Gitea**.  
It completely replaces Django’s default user model with a corporate-grade, Git-integrated user system.

---

## ✨ Key Features

### ✔️ 1. Custom User Model
The module defines `accounts.User`, replacing Django’s `AbstractUser` and adding:

- **Unique email**, used as the main identifier.
- **Role-based access system**:
  - `admin`, `manager`, `senior`, `regular`, `junior`
- **Permission shortcuts** (`can_manage_users`, `can_delete_users`, etc.).
- Extended Gitea-related fields:
  - `gitea_full_name`, `gitea_visibility`, `gitea_location`, etc.
  - `gitea_max_repo_creation`, `gitea_restricted`, `gitea_prohibit_login`
- Sync metadata:
  - `gitea_id`, `gitea_avatar_url`, `gitea_url`
  - `password_updated_at`

---

## 🔄 2. Automatic Gitea Synchronization

Using Django signals (`pre_save`, `post_save`, `pre_delete`), the module keeps Django users seamlessly synced with Gitea:

### On user creation:
- Creates the corresponding user in Gitea.
- Fills `gitea_id` and `gitea_avatar_url`.

### On user updates:
- If `username` changes → triggers a Gitea rename.
- Updates email, admin flag, full name, visibility, website, description, and more.

### On password change:
- If `GITEA_SYNC_PASSWORD=True`, the new password is also updated on Gitea.

### On user deletion:
- Attempts to delete the user in Gitea (fails safely if unable).

All remote operations run **after the DB transaction commit**, ensuring integrity and avoiding failures affecting the Django app.

---

## 🔐 3. Invitation & Activation Flow

The module implements a corporate-style onboarding workflow:

1. Admin/Manager creates a user → account starts **inactive**, with an unusable password.
2. A unique `UserInvite` token is generated.
3. The system emails (or displays) an activation link.
4. The invited user sets a password and the account becomes active.

The same mechanism also powers **password resets**.

---

## 🛡️ 4. Secure Password Reset (anti-abuse)

The `/forgot/` endpoint includes:

- Email/IP rate limiting.
- Complete protection against **user enumeration**.
- Generic success messages for security.

---

## 🧩 5. Bootstrap-ready Forms

The module includes forms for:

- Creating users (`UserCreateForm`)
- Editing own profile (`SelfProfileForm`)
- Editing any user as Admin/Manager (`AdminUserForm`)
- Password setup via invite (`PasswordSetupForm`)

All forms automatically apply Bootstrap classes.

---

## 🧭 6. Main Views

- Login / Logout (`SignInView`, `SignOutView`)
- Smart entry (`/users/`):
  - Admin/Manager → Gitea user list
  - Regular users → own profile
- Profile screen (`ProfileView`)
- Gitea user list (`GiteaUserListView`)
- Create/Edit/Delete users
- Resend invitation
- Password reset via token

---

## 🧱 7. Utilities

### Context Processor  
Provides `U` in every template:

```django
{% if U.can_manage_users %}
   <!-- admin buttons -->
{% endif %}
