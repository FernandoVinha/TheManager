# Tasck – Task Management, Kanban, and Gitea Workflow Module

This module provides the full system for **task management**, **labels**, **task membership**, **activity messages**, and **Git-aware commit tracking**.  
It connects tasks to Gitea forks and pull requests, enabling an end-to-end flow from “work item” to “merged code”.

---

## ✨ Key Features

### ✔️ 1. Task Model

The core entity is `Task`, which represents a work item inside a `Project`.

Each task includes:

- **Project link** (`project`)
- **Title** and **key** (slug, unique per project, auto-generated from the title)
- **Description**
- **Status**:
  - `todo`, `in_progress`, `review`, `verified`, `done`, `failed`
- **Priority**:
  - `low`, `medium`, `high`, `urgent`
- **Reporter** (who created the task)
- **Assignee** (current responsible)
- **Labels** (tags)
- **Due date** and **delivered date**
- Optional **attachment** (file upload)
- Gitea-related fork metadata:
  - `gitea_fork_owner`
  - `gitea_fork_name`
  - `gitea_fork_url`
- Timestamps:
  - `created_at`
  - `updated_at`

Key behavior:

- The `key` field is auto-generated (if empty) from the title using `slugify`:
  - e.g. `"my-task"`, `"my-task-2"`, `"my-task-3"`, ensuring uniqueness per project.

---

## 🏷️ 2. Labels

The module defines a simple `Label` model for tagging tasks:

- `name` (unique)
- `color` (CSS hex, `#RRGGBB` or `#RRGGBBAA`)

Highlights:

- Labels can be reused across tasks.
- A small AJAX endpoint (`LabelCreateAjaxView`) allows creating labels dynamically from the UI:
  - If a label exists, its color can be updated.
  - If it doesn’t, it’s created on the fly.

---

## 👥 3. Task Membership & Roles

Beyond assignee, the module supports **explicit task membership** using `TaskMember`:

- Each membership links:
  - `task`
  - `user`
  - `role` (similar to project roles):
    - `owner`, `maintainer`, `developer`, `reporter`, `guest`

Features:

- Uniqueness per `task + user`.
- Used to express richer collaboration (e.g. reviewers, stakeholders) beyond just a single assignee.
- Works in harmony with project-level membership from the `projects` module.

---

## 💬 4. Task Messages (Discussion & System Activity)

`TaskMessage` provides a lightweight, append-only message stream for each task:

- `task` (FK)
- `agent`:
  - `user` (human message)
  - `gitea` (automated messages about Git/PR/merge)
  - `system` (future system/AI messages)
- `author_name` (free-form name for display)
- `text`
- Optional `payload` (JSON metadata, e.g. raw API responses)
- `created_at`

Use cases:

- User comments (“discussion”).
- Logs of PR creation and merges.
- Error details when Git operations fail.

Messages are displayed in order (`created_at`, `pk`), creating a chronological timeline.

---

## 🔗 5. Git-Aware Commits Tracking

The `TaskCommit` model connects tasks to real commits in the Git repository:

- `task`
- `sha` (commit hash)
- Author metadata:
  - `author_name`
  - `author_email`
  - `committed_date`
- Commit content:
  - `title` (subject line)
  - `message` (full message)
- Diff metrics:
  - `additions`
  - `deletions`
  - `files_changed`
- Links & processing:
  - `html_url` (link to the commit)
  - `code_quality_text` (human/AI notes on code quality)
  - `resolution_text` (how this commit advances/resolves the task)
  - `processed` (whether the commit was already processed by AI)
- `created_at`

This model is designed to support **AI-assisted code review** and **task resolution analysis**, while keeping rich metadata per commit.

---

## 🤝 6. Integration with Gitea (Forks, PRs, and Merge Automation)

The module includes a service layer for Gitea (`tasck/services/gitea.py`) and a signal-based automation:

### Gitea services

Utility functions include:

- Owner checks (`ensure_owner_exists`, `get_owner_kind`)
- Repository operations:
  - `get_repo`, `create_repo`, `delete_repo`, `repo_web_url`
  - `add_collaborator`, `remove_collaborator`
  - `fork_repo`
- Pull requests:
  - `create_pull_request`
  - `merge_pull_request`
- Commits:
  - `list_commits`
  - `get_commit`

### Automatic PR + merge on VERIFIED

A key automation lives in the `Task` signals:

- On `Task` update:
  - If the status changes from something else to **`verified`**:
    1. Checks `gitea_fork_owner` and `gitea_fork_name`.
    2. Fetches repo info for source (fork) and destination (project repo).
    3. Constructs `head` (`<fork_owner>:<branch>`) and `base` branches.
    4. Creates a Pull Request in the project’s main repo.
    5. Immediately attempts to merge it (configurable merge method).
    6. On success:
       - Posts messages in `TaskMessage` (“PR created”, “PR merged successfully”).
       - Optionally updates task status to `done`.
    7. On failure:
       - Records detailed error info in `TaskMessage` (including body of HTTP errors when available).
       - Marks task as `failed`.

All these operations are executed **after the DB commit** using `transaction.on_commit()`, ensuring that the task state is persisted before any external side-effects.

---

## 🧭 7. Views and Workflows

The module provides a complete set of views for working with tasks.

### Task CRUD and listing

- `TaskListView`
  - Lists tasks visible to the user.
  - Admins/managers see all tasks.
  - Regular users see tasks from projects where they are owner or member.
  - Supports text search (`q`).

- `TaskCreateView`
  - Optional `?project=<id>` parameter:
    - Fixes the project and hides the field in the form.
    - Validates project access.
  - Sets `reporter` automatically to the current user.
  - Passes the project into `TaskForm` to limit assignees to project members.

- `TaskDetailView`
  - Shows task details, labels, members, commits, and messages.
  - Supports posting messages directly from the detail page.

- `TaskUpdateView`
  - Task can be edited by:
    - Project editors (Admins/Managers/Owners)
    - Or the original reporter.

- `TaskDeleteView`
  - Limited to project editors (Admins/Managers/Owners).

---

### Task membership management

- `TaskMembersView`
  - Lists task members.
  - Allows adding users as task members using `TaskMemberForm`:
    - Options include only project members and the project owner, excluding users already assigned.

- `TaskMemberDeleteView`
  - Removes a user from the task membership list.

Both views respect project-level permissions, only allowing changes by users who can edit the project.

---

## 📊 8. Kanban Board

The module includes a project-specific Kanban board backed by tasks:

- `ProjectKanbanView`
  - Displays tasks grouped by `Task.Status`:
    - To do, In progress, In review, Verified, Done, Failed.
  - Includes a simple text filter (`KanbanFilterForm`) for quick narrowing.

- `KanbanStatusUpdateView`
  - Endpoint used by drag-and-drop in the UI.
  - Validates:
    - Project access
    - Allowed status values
  - Updates the task’s status in response to board interactions.

This provides a Jira-like experience, directly wired into the task model and Gitea automation.

---

## 📋 9. Project-Scoped Task List

- `ProjectTaskListView`
  - Lists tasks for a specific project.
  - Reuses the same filter form (`KanbanFilterForm`) for quick search.
  - Respects the same project access rules:
    - Admins/Managers
    - Project owners
    - Project members

---

## 🧱 10. Forms & Template Helpers

### Forms

- `TaskForm`
  - Bootstrap-ready.
  - When a project is provided, limits assignee choices to:
    - project members
    - project owner

- `LabelForm`
  - Basic label creation/editing.

- `TaskMemberForm`
  - Limits user choices to project members and owner.
  - Excludes users already assigned as task members.

- `TaskMessageForm`
  - Handles only the message text (author is set in the view).

- `TaskCommitReviewForm`
  - Allows editing:
    - `code_quality_text`
    - `resolution_text`
    - `processed`
  - Designed for human or AI review workflows.

- `KanbanFilterForm`
  - Small search box for both Kanban and project task list views.

### Template tags

- `add_class`
  - Adds CSS classes to form fields.
- `attr`
  - Sets arbitrary HTML attributes on form widgets.

These helpers make it easy to integrate the forms into a Bootstrap-based UI.

---

## 📝 Summary

The **Tasck module** provides:

- A rich task model linked to projects and users.
- Labels, priorities, statuses, and attachments.
- Explicit task membership beyond simple assignees.
- Messaging for discussion and system/Gitea events.
- Commit tracking for future AI-assisted analysis.
- Deep integration with Gitea:
  - Fork awareness
  - Automatic PR creation
  - Automatic merge on verification
- Full set of views:
  - Task list, detail, create, update, delete
  - Task membership management
  - Project Kanban board
  - Project-scoped task lists
  - Commit review UI

It forms the **work execution layer** of the platform, connecting human task tracking, Git activity, and automated workflows into a single, consistent module.
