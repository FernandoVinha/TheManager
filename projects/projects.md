Projects – Project Management and Gitea Repository Integration Module

This module provides the complete system for project management, repository automation, collaboration roles, and synchronization with Gitea.
It connects organizational project structure with Git repositories, ensuring that project membership and repository permissions always stay aligned.

✨ Key Features
✔️ 1. Project Model

The module defines the Project entity, which represents the central workspace for software development activities.
A project contains:

Name and key (used in URLs and task identifiers)

Description and optional thumbnail/cover image

Methodology options:

scrum, kanban, xp

Visibility (private or public)

Git repository settings:

repo_owner, repo_name, default_branch

auto_init

gitea_repo_url (synced after repo creation)

Workflow configuration:

Sprint length

WIP limits

XP pair-programming settings

Each project is fully integrated with its own Git repository and collaboration rules.

🔄 2. Automatic Gitea Repository Provisioning

Using Django signals (post_save), the module automatically creates and configures a repository in Gitea whenever a new project is created.

On project creation:

Validates that the specified repo_owner (user or org) exists in Gitea.

Creates the repository via Gitea’s /user/repos endpoint using Sudo: <repo_owner>.

Applies:

visibility

default branch

auto-init

description

Stores the resulting:

normalized repository name

public web URL

Safety:

All remote repository operations run after the database commit, ensuring that failures never corrupt the Django state.

👥 3. Project Membership & Roles

The module defines a granular and Git-compatible role system via ProjectMember:

owner

maintainer

developer

reporter

guest

Roles determine what users can do inside the project and directly affect Gitea permissions.

A project always guarantees:

an owner exists

the project creator becomes owner automatically

Projects support multiple members, each with different responsibilities and access levels.

🔗 4. Automatic Member Synchronization with Gitea

The module keeps project membership perfectly aligned with repository collaborators using signals (post_save and post_delete).

On member creation:

Adds the user as a collaborator in the Gitea repository.

On role updates:

Updates the collaborator’s Git permission level.

On member removal:

Removes the collaborator from the repository.

Permission mapping is automatic:

Project Role	Gitea Permission
owner	admin
maintainer	admin
developer	write
reporter	read
guest	read

All synchronization happens after the DB commit, making the process safe and resilient.

🛡️ 5. Permission Logic (Owners, Managers, Admins)

Project access is enforced through two permission layers:

Global project permissions (from accounts)

Users may have:

can_create_projects

can_manage_projects

Project-level permissions

Even without global permissions, the Project Owner is always allowed to:

Edit the project

Delete the project

Manage project members

Regular members can view the project and collaborate but cannot change settings.

This dual system ensures both centralized control (Admins/Managers) and distributed autonomy (Project Owners).

🧭 6. Main Views

The module includes full UI views for project management:

Project list (ProjectListView)

Project creation (ProjectCreateView)

Project editing (ProjectUpdateView)

Project deletion (ProjectDeleteView)

Member management (ProjectMembersView)

Project detail + integrated Kanban board (ProjectDetailView)

Project visibility automatically adapts:

Admin/Manager → sees all projects

Other users → see only projects where they are owner or member

📦 7. Task Board Integration

The project detail page includes a complete Kanban workflow populated by the Task module:

To do

In progress

In review

Verified

Done

Failed

Tasks are grouped automatically, enabling high-level project monitoring and team coordination.

🧱 8. Utility Components
Gitea service layer (projects/services/gitea.py)

Abstracts all remote Git operations:

Repository creation

Collaborator management

Owner validation

URL helpers

This keeps all repository operations cleanly separated from views and models.

Signal-driven synchronization

Ensures:

Automatic repository creation

Automatic collaborator updates

Reliable, transaction-safe behavior

📝 Summary

The Projects module provides:

A structured, Jira-like project entity

Automatic creation and management of Git repositories

Real-time synchronization between project membership and Gitea collaborators

A complete role system aligned with repository permissions

Safe, transaction-bound operations

A detailed project workspace with Kanban board

A balanced permission model allowing Admins/Managers to oversee everything and Owners to manage their own projects

It forms the backbone of project coordination, repository automation, and future AI-driven code navigation inside the platform.