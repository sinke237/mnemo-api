# Mnemo Mobile — Flutter Application Specification

**Document version:** 1.0.0  
**Date:** 2026-03-25  
**Author:** Principal Systems Architect  
**Status:** Implementation-Ready  
**Target directory:** `/home/vlageboi/opensource/mnemo-api/apiApp`

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Product Goals](#2-product-goals)
3. [Clarifying Questions & Answers](#3-clarifying-questions--answers)
4. [Assumptions](#4-assumptions)
5. [User Personas](#5-user-personas)
6. [User Journeys](#6-user-journeys)
7. [Functional Requirements](#7-functional-requirements)
8. [Non-Functional Requirements](#8-non-functional-requirements)
9. [System Architecture](#9-system-architecture)
10. [Flutter Project Structure](#10-flutter-project-structure)
11. [API Integration Specification](#11-api-integration-specification)
12. [Data Models (Dart)](#12-data-models-dart)
13. [State Management Design](#13-state-management-design)
14. [AI / Recommendation Engine Design](#14-ai--recommendation-engine-design)
15. [OS-Level Constraints (Android vs iOS)](#15-os-level-constraints-android-vs-ios)
16. [Security & Privacy Considerations](#16-security--privacy-considerations)
17. [Scalability Strategy](#17-scalability-strategy)
18. [Extensibility Strategy](#18-extensibility-strategy)
19. [UX/UI Design Guidelines](#19-uxui-design-guidelines)
20. [Edge Cases & Failure Handling](#20-edge-cases--failure-handling)
21. [Future Enhancements](#21-future-enhancements)

---

## 1. Executive Summary

**Mnemo Mobile** is a personal productivity and learning Flutter application built on top of the Mnemo spaced-repetition API. It combines flashcard-based active recall study sessions with an Android-native digital wellness layer: real-time device usage tracking across all installed apps, configurable daily per-app limits, focus/study mode with full notification suppression, and an on-device TensorFlow Lite model that detects overuse patterns and generates personalised reduction targets.

The app is designed for a single user (personal utility), targets Android (primary) and iOS (secondary, with graceful feature degradation on restricted OS capabilities), and is distributed via Google Play and the App Store.

All application code, assets, and configuration reside under:
```
/home/vlageboi/opensource/mnemo-api/apiApp/
```

---

## 2. Product Goals

| ID | Goal |
|----|------|
| G-01 | Deliver a frictionless spaced-repetition study experience driven by the Mnemo API |
| G-02 | Provide accurate, whole-device app usage telemetry on Android using `UsageStatsManager` |
| G-03 | Allow users to set daily time-budgets per installed app and enforce hard blocks on Android |
| G-04 | Enable a Focus Mode that suppresses all device notifications during study sessions on Android |
| G-05 | Surface AI-driven insights (overuse detection, reduction targets) purely on-device via TFLite |
| G-06 | Keep the architecture API-agnostic so additional services can be plugged in without refactoring core UI |
| G-07 | Keep iOS feature set fully functional for all API features; gracefully degrade OS-restricted features |

---

## 3. Clarifying Questions & Answers

| # | Question | Answer |
|---|----------|--------|
| A1 | App name / branding | Personal utility — name **Mnemo**; architect to define Material3 design token palette |
| A2 | Minimum OS versions | Android API 26 (Oreo, 2017); iOS 15 — accepted |
| A3 | Distribution | Google Play + App Store |
| B4 | API key provisioning | Self-registration screen → admin-backed provisioning endpoint |
| B5 | Multi-account | Single account per install |
| C6 | Usage tracking scope | Android only; all installed apps via `UsageStatsManager` |
| C7 | Usage limiting enforcement | Android: hard block. iOS: warning only (OS restriction acknowledged) |
| C8 | Notification blocking | Android only; all notifications blocked during Focus Mode |
| D9 | AI backend | Fully client-side |
| D10 | AI model format | TensorFlow Lite on-device model |
| E11 | Offline | Fully online MVP; offline planned for future |
| F12 | CSV import | Device storage via file picker |
| F13 | Existing design work | None; spec defines UX from scratch |
| F14 | Production API URL | None defined; `https://api.mnemo.app` suggested as default (configurable) |
| F15 | State management | Architecture chooses: **Riverpod 2.x** (justified in §13) |

---

## 4. Assumptions

These assumptions are locked based on the answers above. Changing any of them requires a revision of the affected sections.

| ID | Assumption |
|----|------------|
| AS-01 | The Mnemo API base URL defaults to `https://api.mnemo.app` and is overridable at build time via a Dart `--dart-define` |
| AS-02 | A "provisioning" admin endpoint exists (or will be created) at `POST /v1/admin/provision` that accepts `{display_name, country, timezone?}` and returns `{user_id, api_key}`. Until that endpoint is built, onboarding should guide the user to receive the key out-of-band and enter it manually |
| AS-03 | JWT tokens expire after 3600 s; the app silently re-exchanges the stored API key + user ID for a fresh token whenever a 401 is received |
| AS-04 | Android minimum API level is 26, which is the minimum for `UsageStatsManager` granular queries |
| AS-05 | `PACKAGE_USAGE_STATS`, `BIND_NOTIFICATION_LISTENER_SERVICE`, and `SYSTEM_ALERT_WINDOW` permissions are declared and explained to the user; the app handles the case where the user denies them |
| AS-06 | The TFLite model is bundled in the app assets at first release; a background-download path is reserved for model updates |
| AS-07 | The app is always-online for MVP; network errors surface as toasts/dialogs, not cached fallback data |
| AS-08 | Rate limit defaults from the API: read 600/min, write 120/min, auth 30/min, import 10/hr, session 60/min |
| AS-09 | Idempotency keys are generated client-side as `uuid_v4` strings and used for deck/card creation to prevent duplicates on retry |

---

## 5. User Personas

### Persona 1 — The Daily Learner
- **Name:** Kofi, 24, undergraduate
- **Goals:** Review flashcard decks daily, hit streak goals, track academic progress
- **Pain points:** Gets distracted by social media while studying; forgets to review decks
- **Relevant features:** Study sessions, streak tracking, Focus Mode, usage limiting

### Persona 2 — The Content Creator
- **Name:** Amara, 30, professional
- **Goals:** Build large custom decks, import from CSV, maintain multiple subject areas
- **Pain points:** Card creation is tedious without bulk import; hard to spot weak areas
- **Relevant features:** CSV import, deck management, weak-spot detection, study plans

### Persona 3 — The Wellness-Focused User
- **Name:** Lena, 19, secondary school
- **Goals:** Reduce time on entertainment apps, build healthy digital habits
- **Pain points:** Unaware of how much time is spent in apps; no enforcement mechanism
- **Relevant features:** Usage tracking dashboard, per-app limits, Focus Mode, AI insights

---

## 6. User Journeys

### Journey 1 — First Launch & Onboarding

```
App Launch
   │
   ├─ Check: credentials stored in SecureStorage?
   │     └─ NO ──► Onboarding Screen
   │                   │
   │                   ├─ Option A: Enter existing API key + user ID manually
   │                   └─ Option B: Register (calls admin provisioning endpoint)
   │                           ├─ Display Name, Country, Locale inputs
   │                           └─ On success: store api_key + user_id → SecureStorage
   │
   └─ YES ──► Attempt token exchange (POST /v1/auth/token)
                 ├─ 200: store JWT in memory → navigate to Home
                 └─ 401: clear credentials → Onboarding Screen
```

### Journey 2 — Daily Study Session

```
Home Screen (shows due count badge)
   │
   └─ Tap "Start Review" for a deck
         │
         ├─ Configure: mode (REVIEW/QUIZ/EXAM), card_limit (1-100), due_only, focus_weak
         ├─ Optional: enable Focus Mode → request DND permission (Android) → block notifications
         ├─ POST /v1/sessions → receive session_id + first card
         │
         └─ Session Loop:
               ├─ Display card question (countdown timer overlay visible)
               ├─ User submits answer → POST /v1/sessions/{id}/answer
               │     └─ Receive: score, is_correct, feedback, next_card
               ├─ User may tap "Skip" → POST /v1/sessions/{id}/skip
               └─ When next_card is null OR user ends:
                     ├─ POST /v1/sessions/{id}/end  (if early termination)
                     ├─ GET /v1/sessions/{id}/summary
                     ├─ Disable Focus Mode (restore notifications)
                     └─ Show summary screen (accuracy, time, cards done)
```

### Journey 3 — Usage Tracking & Limits

```
Home Screen → "Digital Wellness" tab
   │
   ├─ If PACKAGE_USAGE_STATS not granted:
   │     └─ Permission rationale dialog → open Settings → Usage Access
   │
   ├─ Dashboard: today's top apps by time (bar chart)
   ├─ Tap app → set daily limit (1 min – 6 hr) → stored in local DB (Drift)
   │
   └─ Background UsageMonitorService (Android Foreground Service)
         ├─ Polls UsageStatsManager every 60 s
         ├─ Checks: current usage vs. limit for each app
         ├─ 80% of limit: sends local notification warning
         └─ 100% of limit: launches overlay (SYSTEM_ALERT_WINDOW) blocking the app
```

### Journey 4 — CSV Import

```
Decks Screen → "Import CSV" button
   │
   ├─ File picker (device storage) → select .csv file
   ├─ Choose target: existing deck (select) or new deck (name field)
   ├─ Choose mode: MERGE or REPLACE
   └─ POST /v1/import/csv (multipart/form-data)
         ├─ 202 Accepted: show job_id and poll GET /v1/import/{job_id} every 2 s
         │     └─ status transitions: queued → processing → completed/failed
         └─ On completion: show cards_imported, cards_skipped, errors list
```

### Journey 5 — AI Insights

```
Wellness Tab → "Insights" section
   │
   ├─ App reads last 14 days of usage data from local Drift DB
   ├─ Runs TFLite inference model (input: 14-day time series per app)
   ├─ Model outputs: overuse_score (0.0-1.0), suggested_reduction_pct per app
   └─ Display: "You've used Instagram 47% more than your 7-day average this week.
                Consider reducing by 30 min/day."
```

---

## 7. Functional Requirements

### FR-01 Authentication & Account

| ID | Requirement |
|----|-------------|
| FR-01.1 | App stores `api_key` and `user_id` in Android Keystore / iOS Secure Enclave backed secure storage |
| FR-01.2 | App exchanges `api_key` + `user_id` for a JWT via `POST /v1/auth/token` at startup and after every 401 response |
| FR-01.3 | JWT is kept in-memory only (never persisted to disk) |
| FR-01.4 | Onboarding supports manual key entry (always) and registration (when provisioning endpoint is available) |
| FR-01.5 | Single account per install; switching accounts requires sign-out and re-onboarding |

### FR-02 Decks

| ID | Requirement |
|----|-------------|
| FR-02.1 | List all user decks with pagination (page, per_page up to 100), sorting, and tag filtering |
| FR-02.2 | Create, view, edit (PUT/PATCH), and delete decks |
| FR-02.3 | View deck stats (`GET /v1/decks/{id}/stats`) including mastery %, due count, accuracy |
| FR-02.4 | Deck create/update operations use an `Idempotency-Key` header (uuid_v4) to prevent duplicates on retry |
| FR-02.5 | Deck names are unique per user (max 128 chars); tags max 32 chars each |

### FR-03 Flashcards

| ID | Requirement |
|----|-------------|
| FR-03.1 | List cards in a deck with pagination |
| FR-03.2 | Create, view, replace (PUT), partially update (PATCH), and delete cards |
| FR-03.3 | Card fields: question (max 1000), answer (max 2000), source_ref (max 255), tags, difficulty (1–5) |
| FR-03.4 | Card creation uses `Idempotency-Key` header |

### FR-04 Study Sessions

| ID | Requirement |
|----|-------------|
| FR-04.1 | Start session: `POST /v1/sessions` with deck_id, mode (review/quiz/exam), card_limit (1–100), due_only, focus_weak, time_limit_s (≥60) |
| FR-04.2 | Submit answer: `POST /v1/sessions/{id}/answer` with answer string (max 2000), time_taken_s, confidence (1–3) |
| FR-04.3 | Skip card: `POST /v1/sessions/{id}/skip` |
| FR-04.4 | End session early: `POST /v1/sessions/{id}/end` |
| FR-04.5 | View session summary: `GET /v1/sessions/{id}/summary` |
| FR-04.6 | Session progress (cards_total, cards_done) displayed persistently during session |

### FR-05 Memory States & Spaced Repetition

| ID | Requirement |
|----|-------------|
| FR-05.1 | View memory state for a card: `GET /v1/cards/{id}/memory` (interval_days, ease_factor, repetitions, due_at, streak) |
| FR-05.2 | Direct answer submission (outside session): `POST /v1/cards/{id}/answer` with score (0–5) |
| FR-05.3 | Due cards list: `GET /v1/users/{id}/due` (sorted by urgency, includes overdue_by_seconds) |
| FR-05.4 | Weak spots: `GET /v1/users/{id}/weak-spots?limit=10` (cards with lowest ease_factor) |

### FR-06 Progress & Study Plans

| ID | Requirement |
|----|-------------|
| FR-06.1 | User overall progress: `GET /v1/users/{id}/progress` (total_cards, mastered_cards, due_today, accuracy_rate, streak, total_sessions, deck_summaries) |
| FR-06.2 | Per-deck progress: `GET /v1/users/{id}/progress/{deck_id}` |
| FR-06.3 | Streak: `GET /v1/users/{id}/streak` |
| FR-06.4 | Generate study plan: `POST /v1/users/{id}/plan` with deck_id, goal, days (1–365), daily_minutes (1–1440) |
| FR-06.5 | Retrieve active plan: `GET /v1/users/{id}/plan` (returns schedule with per-day cards_to_study and focus description) |

### FR-07 CSV Import

| ID | Requirement |
|----|-------------|
| FR-07.1 | File picker opens device storage; accepts `.csv` files UTF-8 encoded, max 5 MB |
| FR-07.2 | User selects import mode: MERGE (add new, skip duplicates) or REPLACE (wipe and re-import) |
| FR-07.3 | App polls job status every 2 s until status is `completed` or `failed` |
| FR-07.4 | Import result screen shows: cards_imported, cards_skipped, list of errors |

### FR-08 User Profile

| ID | Requirement |
|----|-------------|
| FR-08.1 | View and update: display_name, locale, timezone, education_level, preferred_language, daily_goal_cards |
| FR-08.2 | Country selection populates from `GET /v1/countries`; timezone dropdown shown for multi-timezone countries |
| FR-08.3 | daily_goal_cards range: 1–200 |

### FR-09 Focus Mode (Android Only)

| ID | Requirement |
|----|-------------|
| FR-09.1 | Toggle before/during session; requests `android.permission.ACCESS_NOTIFICATION_POLICY` |
| FR-09.2 | On enable: sets DND mode to `INTERRUPTION_FILTER_NONE` via `NotificationManager` |
| FR-09.3 | On session end or app foreground loss: restores previous DND state |
| FR-09.4 | On iOS: UI toggle visible but non-functional with explanatory tooltip "Not available on iOS" |

### FR-10 Usage Tracking (Android Only)

| ID | Requirement |
|----|-------------|
| FR-10.1 | Upon first launch of Wellness tab, checks `AppOpsManager.OP_GET_USAGE_STATS`; if denied, opens `Settings.ACTION_USAGE_ACCESS_SETTINGS` |
| FR-10.2 | `UsageStatsMonitorService` (foreground service) reads `UsageStatsManager.queryUsageStats` with `INTERVAL_DAILY` each minute at minimum; persists to local Drift DB |
| FR-10.3 | Dashboard shows today's top-10 apps by screen time (app icon, name, duration bar) |
| FR-10.4 | Weekly and daily aggregated views available |
| FR-10.5 | On iOS: Wellness tab is visible; tracking section shows "Usage tracking is not available on iOS" |

### FR-11 Usage Limiting (Android Only)

| ID | Requirement |
|----|-------------|
| FR-11.1 | User sets per-app daily limit (minimum 1 min, maximum 6 hr) stored in Drift DB |
| FR-11.2 | At 80% of limit: system notification warning issued via `NotificationCompat` |
| FR-11.3 | At 100% of limit: overlay window (`TYPE_APPLICATION_OVERLAY`, requires `SYSTEM_ALERT_WINDOW`) launched in front of the blocked app; user can dismiss for "5 more minutes" (snooze, maximum 3× per day per app) |
| FR-11.4 | Overlay cannot be permanently dismissed for the day once the limit is reached |
| FR-11.5 | On iOS: limit setting UI is visible; enforcement is "notification only" with explicit label |

### FR-12 Study / Quiz Timer

| ID | Requirement |
|----|-------------|
| FR-12.1 | Persistent overlay widget displayed on all session screens showing elapsed or countdown time |
| FR-12.2 | When `time_limit_s` is set: counts down; at 0 calls `POST /v1/sessions/{id}/end` automatically |
| FR-12.3 | When no limit: counts up (elapsed time) |
| FR-12.4 | Timer widget is a compact floating chip (non-intrusive), tappable to expand/collapse detail |

### FR-13 Health Check

| ID | Requirement |
|----|-------------|
| FR-13.1 | App calls `GET /v1/health` on startup; if `status != "ok"`, shows degraded-state banner |

---

## 8. Non-Functional Requirements

| ID | Category | Requirement |
|----|----------|-------------|
| NFR-01 | Performance | API calls must display a loading skeleton within 100 ms of tap; no unhandled ANR on Android |
| NFR-02 | Responsiveness | UI renders at ≥60 fps on mid-range devices (Snapdragon 665 class) |
| NFR-03 | Startup time | Cold start to Home screen ≤ 3 s on mid-range Android device |
| NFR-04 | Security | credentials stored in encrypted storage only; JWT never written to disk; no API key in logs |
| NFR-05 | Reliability | All API calls implement exponential backoff (max 3 retries, base delay 500 ms) |
| NFR-06 | Offline handling | Network errors produce user-facing messages, never silent failures |
| NFR-07 | Accessibility | All interactive elements have semantic labels; text scales with system font size |
| NFR-08 | Battery | Foreground service polls at ≤ 60 s intervals; uses `JobScheduler` for non-critical background tasks |
| NFR-09 | Privacy | No usage data leaves the device; TFLite inference runs fully on-device |
| NFR-10 | Localization | App structure supports `flutter_localizations`; English is the sole locale for MVP |
| NFR-11 | Code quality | All Dart code passes `dart analyze` with zero errors; formatted with `dart format` |
| NFR-12 | Test coverage | ≥ 70% unit test coverage for service layer and repositories |

---

## 9. System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FLUTTER APP (apiApp/)                        │
│                                                                     │
│  ┌──────────────┐   ┌──────────────────┐   ┌────────────────────┐  │
│  │  Presentation│   │   Domain Layer    │   │  Infrastructure    │  │
│  │   (Screens / │   │  (UseCases /      │   │  (Repositories /   │  │
│  │   Widgets)   │   │   Entities /      │   │   Services /       │  │
│  │              │   │   Abstractions)   │   │   DataSources)     │  │
│  │  Riverpod    │◄──│                   │──►│                    │  │
│  │  Providers   │   │  Pure Dart        │   │  Dio HTTP Client   │  │
│  │  Go Router   │   │  No Flutter deps  │   │  Drift (SQLite)    │  │
│  └──────────────┘   └──────────────────┘   │  FlutterSecureStorage│ │
│                                            │  TFLite Runtime    │  │
│                                            │  Android Platform  │  │
│                                            │  Channels          │  │
│                                            └────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
             │                                        │
             │  HTTPS (Bearer JWT)                    │  Local
             ▼                                        ▼
┌────────────────────┐                  ┌─────────────────────────┐
│   Mnemo REST API   │                  │  Android OS APIs         │
│   /v1/*            │                  │  UsageStatsManager       │
│   (FastAPI)        │                  │  NotificationManager     │
│                    │                  │  SYSTEM_ALERT_WINDOW     │
└────────────────────┘                  └─────────────────────────┘
```

### Layer Responsibilities

| Layer | Dart package location | Responsibility |
|-------|-----------------------|----------------|
| Presentation | `lib/features/*/presentation/` | Widgets, screens, Riverpod `ConsumerWidget` |
| Providers | `lib/features/*/providers/` | Riverpod `NotifierProvider`, `AsyncNotifierProvider` |
| Domain | `lib/core/domain/` | Abstract repository interfaces, entity classes, use-case functions |
| Infrastructure | `lib/core/infrastructure/` | Concrete repository impls, Dio client, Drift DB, platform channels |
| Platform Channel | `android/app/src/main/kotlin/` | Kotlin code for `UsageStats`, DND, overlay |

---

## 10. Flutter Project Structure

All paths are rooted at `/home/vlageboi/opensource/mnemo-api/apiApp/`.

```
apiApp/
├── android/
│   └── app/src/main/kotlin/com/mnemo/app/
│       ├── MainActivity.kt
│       ├── UsageStatsChannel.kt          ← MethodChannel: usage_stats
│       ├── DndChannel.kt                 ← MethodChannel: dnd_control
│       ├── OverlayService.kt             ← Foreground service for overlay
│       └── UsageMonitorService.kt        ← Foreground service for polling
├── ios/
│   └── Runner/
│       ├── AppDelegate.swift
│       └── StubChannels.swift            ← No-op stubs for usage/dnd channels
├── assets/
│   ├── models/
│   │   └── usage_classifier.tflite      ← Bundled TFLite model
│   └── icons/                           ← App icons (generated)
├── lib/
│   ├── main.dart                        ← Entry point; ProviderScope root
│   ├── app.dart                         ← MaterialApp.router + GoRouter setup
│   │
│   ├── core/
│   │   ├── config/
│   │   │   ├── app_config.dart          ← Base URL, env flags (--dart-define)
│   │   │   └── constants.dart           ← Timeout, retry, limits
│   │   ├── domain/
│   │   │   ├── entities/                ← Pure Dart entity classes (no JSON)
│   │   │   └── repositories/            ← Abstract interfaces
│   │   ├── infrastructure/
│   │   │   ├── http/
│   │   │   │   ├── api_client.dart      ← Dio instance + interceptors
│   │   │   │   ├── auth_interceptor.dart← JWT injection + 401 refresh
│   │   │   │   └── retry_interceptor.dart
│   │   │   ├── storage/
│   │   │   │   ├── secure_storage.dart  ← flutter_secure_storage wrapper
│   │   │   │   └── local_db.dart        ← Drift database definition
│   │   │   └── platform/
│   │   │       ├── usage_stats_channel.dart  ← Dart side of MethodChannel
│   │   │       └── dnd_channel.dart
│   │   ├── error/
│   │   │   ├── api_error.dart           ← Typed error sealed class
│   │   │   └── error_handler.dart
│   │   └── routing/
│   │       ├── app_router.dart          ← GoRouter configuration
│   │       └── routes.dart              ← Route name constants
│   │
│   ├── features/
│   │   ├── auth/
│   │   │   ├── data/
│   │   │   │   ├── auth_repository_impl.dart
│   │   │   │   └── auth_remote_source.dart
│   │   │   ├── domain/
│   │   │   │   └── auth_repository.dart
│   │   │   ├── providers/
│   │   │   │   └── auth_provider.dart
│   │   │   └── presentation/
│   │   │       ├── onboarding_screen.dart
│   │   │       └── login_screen.dart
│   │   │
│   │   ├── decks/
│   │   │   ├── data/
│   │   │   │   ├── deck_repository_impl.dart
│   │   │   │   └── deck_remote_source.dart
│   │   │   ├── domain/
│   │   │   │   └── deck_repository.dart
│   │   │   ├── models/
│   │   │   │   ├── deck.dart            ← Freezed model + json_serializable
│   │   │   │   └── deck_list_response.dart
│   │   │   ├── providers/
│   │   │   │   └── deck_provider.dart
│   │   │   └── presentation/
│   │   │       ├── decks_screen.dart
│   │   │       ├── deck_detail_screen.dart
│   │   │       └── widgets/
│   │   │
│   │   ├── cards/
│   │   │   ├── data/
│   │   │   ├── domain/
│   │   │   ├── models/
│   │   │   │   └── flashcard.dart
│   │   │   ├── providers/
│   │   │   └── presentation/
│   │   │
│   │   ├── sessions/
│   │   │   ├── data/
│   │   │   ├── domain/
│   │   │   ├── models/
│   │   │   │   ├── session.dart
│   │   │   │   ├── answer_result.dart
│   │   │   │   └── session_summary.dart
│   │   │   ├── providers/
│   │   │   │   └── session_provider.dart
│   │   │   └── presentation/
│   │   │       ├── session_config_screen.dart
│   │   │       ├── session_screen.dart
│   │   │       ├── session_summary_screen.dart
│   │   │       └── widgets/
│   │   │           ├── timer_chip.dart       ← Persistent countdown widget
│   │   │           └── card_flip_widget.dart
│   │   │
│   │   ├── memory/
│   │   │   ├── data/
│   │   │   ├── domain/
│   │   │   ├── models/
│   │   │   │   ├── memory_state.dart
│   │   │   │   ├── due_card.dart
│   │   │   │   └── weak_spot.dart
│   │   │   ├── providers/
│   │   │   └── presentation/
│   │   │
│   │   ├── progress/
│   │   │   ├── data/
│   │   │   ├── domain/
│   │   │   ├── models/
│   │   │   │   ├── progress.dart
│   │   │   │   ├── deck_progress.dart
│   │   │   │   └── streak.dart
│   │   │   ├── providers/
│   │   │   └── presentation/
│   │   │       └── progress_screen.dart
│   │   │
│   │   ├── plans/
│   │   │   ├── data/
│   │   │   ├── domain/
│   │   │   ├── models/
│   │   │   │   └── study_plan.dart
│   │   │   ├── providers/
│   │   │   └── presentation/
│   │   │       └── plan_screen.dart
│   │   │
│   │   ├── imports/
│   │   │   ├── data/
│   │   │   ├── domain/
│   │   │   ├── models/
│   │   │   │   └── import_job.dart
│   │   │   ├── providers/
│   │   │   └── presentation/
│   │   │       └── import_screen.dart
│   │   │
│   │   ├── profile/
│   │   │   ├── data/
│   │   │   ├── domain/
│   │   │   ├── models/
│   │   │   │   └── user_profile.dart
│   │   │   ├── providers/
│   │   │   └── presentation/
│   │   │       └── profile_screen.dart
│   │   │
│   │   └── wellness/                        ← Android-primary feature module
│   │       ├── data/
│   │       │   ├── usage_repository_impl.dart
│   │       │   └── usage_local_source.dart   ← Reads Drift DB
│   │       ├── domain/
│   │       │   ├── usage_repository.dart
│   │       │   └── usage_limit_repository.dart
│   │       ├── models/
│   │       │   ├── app_usage_record.dart
│   │       │   └── app_limit.dart
│   │       ├── providers/
│   │       │   ├── usage_provider.dart
│   │       │   └── ai_insights_provider.dart
│   │       ├── ml/
│   │       │   ├── usage_classifier.dart     ← TFLite wrapper
│   │       │   └── usage_feature_extractor.dart
│   │       └── presentation/
│   │           ├── wellness_screen.dart
│   │           ├── app_limit_screen.dart
│   │           └── insights_screen.dart
│   │
│   └── shared/
│       ├── widgets/
│       │   ├── loading_skeleton.dart
│       │   ├── error_banner.dart
│       │   ├── paginated_list.dart
│       │   └── confirm_dialog.dart
│       └── utils/
│           ├── idempotency_key.dart      ← uuid_v4 generator
│           └── date_formatter.dart
│
├── test/
│   ├── unit/
│   │   ├── repositories/
│   │   ├── providers/
│   │   └── ml/
│   └── integration/
│       └── api_client_test.dart
│
├── pubspec.yaml
└── analysis_options.yaml
```

---

## 11. API Integration Specification

### 11.1 Base Configuration

| Parameter | Value |
|-----------|-------|
| Base URL | `https://api.mnemo.app` (overridable via `--dart-define=API_BASE_URL=...`) |
| API version prefix | `/v1` |
| Content-Type | `application/json` |
| Auth header | `Authorization: Bearer <jwt>` |
| Connect timeout | 10 s |
| Receive timeout | 30 s |
| Send timeout | 30 s |

### 11.2 Authentication Flow

**Step 1 — Token Exchange**

```
POST /v1/auth/token
Content-Type: application/json

{
  "user_id": "usr_<16 hex chars>",        // pattern: ^usr_[a-f0-9]{16}$
  "api_key": "mnm_live_<64 hex chars>"    // pattern: ^mnm_(live|test)_[a-f0-9]{64}$
}
```

**Success Response (200):**
```json
{
  "access_token": "<JWT>",
  "expires_in": 3600,
  "token_type": "Bearer"
}
```

**Error Responses:**
| Status | Error Code | Trigger |
|--------|------------|---------|
| 401 | `INVALID_API_KEY` | Bad or revoked API key |
| 401 | `USER_NOT_FOUND` | user_id does not exist |
| 403 | `API_KEY_OWNER_MISMATCH` | API key does not belong to user_id |
| 429 | `RATE_LIMIT_EXCEEDED` | > 30 auth requests/min |

**Token refresh strategy (Dart):**
- JWT stored in-memory only in a `StateProvider<String?>`
- `AuthInterceptor` detects HTTP 401 on any request, calls `_refreshToken()`, retries the original request exactly once
- If refresh itself returns 401: clear credentials from `FlutterSecureStorage`, redirect to onboarding

**Rate limits to honour client-side:**
| Category | Limit |
|----------|-------|
| Auth | 30 req/min |
| Read (GET) | 600 req/min |
| Write (POST/PUT/PATCH/DELETE, non-session) | 120 req/min |
| Session actions (POST /sessions/*, non-GET) | 60 req/min |
| Import | 10 req/hr |

### 11.3 Endpoint Reference

#### Health

| Method | Path | Auth | Scopes | Description |
|--------|------|------|--------|-------------|
| GET | `/v1/health` | None | None | System health check |

**Response (200):**
```json
{
  "status": "ok",
  "db": "ok",
  "redis": "ok",
  "worker": "ok",
  "version": "1.0.0"
}
```
When `status == "degraded"`, display a non-blocking banner.

---

#### Authentication

| Method | Path | Auth | Scopes |
|--------|------|------|--------|
| POST | `/v1/auth/token` | API Key in body | — |

See §11.2 above.

---

#### Countries

| Method | Path | Auth | Scopes |
|--------|------|------|--------|
| GET | `/v1/countries` | None | None |
| GET | `/v1/countries/{country_code}` | None | None |

**GET /v1/countries response (200):**
```json
{
  "countries": [
    {
      "code": "CM",
      "primary_timezone": "Africa/Douala",
      "has_multiple_timezones": false,
      "all_timezones": ["Africa/Douala"]
    },
    {
      "code": "US",
      "primary_timezone": "America/New_York",
      "has_multiple_timezones": true,
      "all_timezones": ["America/New_York", "America/Chicago", "America/Denver",
                        "America/Los_Angeles", "America/Anchorage", "Pacific/Honolulu"]
    }
  ],
  "total": 195
}
```

**GET /v1/countries/{code} response (200):** returns a single `CountryInfo` object.
**404:** `INVALID_COUNTRY_CODE`

---

#### Users

| Method | Path | Auth | Required Scope |
|--------|------|------|----------------|
| POST | `/v1/users` | API Key | `admin` |
| GET | `/v1/users/{user_id}` | JWT | own user or `admin` |
| PATCH | `/v1/users/{user_id}` | JWT | own user only |

**POST /v1/users request:**
```json
{
  "display_name": "Enow Sinke",          // optional, max 100 chars
  "country": "CM",                        // required, ISO 3166-1 alpha-2 uppercase
  "locale": "fr-CM",                      // optional, BCP47 ^[a-z]{2}-[A-Z]{2}$
  "timezone": "Africa/Douala",            // optional; required for multi-tz countries
  "education_level": "undergraduate",     // optional: none|secondary|undergraduate|postgraduate|professional
  "preferred_language": "fr",             // default "en", ^[a-z]{2}$
  "daily_goal_cards": 25                  // default 20, range 1-200
}
```

**POST /v1/users response (201):** `UserResponse` (see §12)

**PATCH /v1/users/{id} request (all fields optional):**
```json
{
  "display_name": "Enow S.",
  "locale": "fr-CM",
  "timezone": "Africa/Douala",
  "education_level": "postgraduate",
  "preferred_language": "en",
  "daily_goal_cards": 30
}
```
> Note: `country` cannot be changed after creation.

**UserResponse:**
```json
{
  "id": "usr_a1b2c3d4e5f6a7b8",
  "display_name": "Enow Sinke",
  "country": "CM",
  "locale": "fr-CM",
  "timezone": "Africa/Douala",
  "education_level": "undergraduate",
  "preferred_language": "fr",
  "daily_goal_cards": 25,
  "created_at": "2026-03-10T08:30:00Z",
  "local_time": "2026-03-10T09:30:00+01:00",
  "created_at_local": "2026-03-10T09:30:00+01:00"
}
```

**Error responses:**
| Status | Code | Trigger |
|--------|------|---------|
| 400 | `INVALID_COUNTRY_CODE` | Unknown country |
| 400 | `INVALID_TIMEZONE` | Bad/missing timezone for multi-tz country |
| 401 | `INVALID_TOKEN` | Bad JWT |
| 403 | `INSUFFICIENT_SCOPE` | Not own user or not admin |
| 404 | `USER_NOT_FOUND` | user_id doesn't exist |

---

#### Decks

Scope requirements: list/get/list-cards → `decks:read`; create/update/delete → `decks:write`; stats → `progress:read`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/v1/decks` | List decks (paginated) |
| POST | `/v1/decks` | Create deck |
| GET | `/v1/decks/{deck_id}` | Get deck |
| PUT | `/v1/decks/{deck_id}` | Replace deck |
| PATCH | `/v1/decks/{deck_id}` | Partial update |
| DELETE | `/v1/decks/{deck_id}` | Delete deck |
| GET | `/v1/decks/{deck_id}/stats` | Deck stats |
| GET | `/v1/decks/{deck_id}/cards` | List cards in deck |

**GET /v1/decks query params:**
```
?page=1&per_page=20&tag=chemistry&sort=created_at&order=desc
```
- `sort`: `created_at` | `updated_at` | `name`
- `order`: `asc` | `desc`

**DeckListResponse:**
```json
{
  "data": [
    {
      "id": "dck_0521fbee640de0df",
      "name": "Organic Chemistry",
      "card_count": 142,
      "tags": ["chemistry", "science"],
      "created_at": "2026-01-15T10:00:00Z",
      "updated_at": "2026-03-20T14:30:00Z"
    }
  ],
  "pagination": { "page": 1, "per_page": 20, "total": 1, "total_pages": 1 }
}
```

**POST /v1/decks request:**
```json
{
  "name": "Organic Chemistry",     // required, 1-128 chars, unique per user
  "description": "CHEM 301",       // optional
  "tags": ["chemistry", "science"] // optional; each tag max 32 chars
}
```
Headers: `Idempotency-Key: <uuid_v4>` (strongly recommended)

**DeckResponse (201/200):**
```json
{
  "id": "dck_0521fbee640de0df",
  "name": "Organic Chemistry",
  "description": "CHEM 301",
  "tags": ["chemistry"],
  "card_count": 0,
  "version": 1,
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-01-15T10:00:00Z",
  "source_file": null
}
```

**DeckProgressResponse (stats endpoint):**
```json
{
  "deck_id": "dck_0521fbee640de0df",
  "name": "Organic Chemistry",
  "total_cards": 142,
  "mastered_cards": 98,
  "mastery_pct": 69.0,
  "due_count": 12,
  "accuracy_rate": 0.82,
  "total_sessions": 34,
  "last_studied_at": "2026-03-24T18:00:00Z",
  "last_studied_at_local": "2026-03-24T19:00:00+01:00"
}
```

**Error codes:** `DECK_NOT_FOUND` (404), `DECK_NAME_CONFLICT` (409)

---

#### Cards (Flashcards)

Scope: read → `decks:read`; write → `decks:write`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/decks/{deck_id}/cards` | Create card |
| GET | `/v1/cards/{card_id}` | Get card |
| PUT | `/v1/cards/{card_id}` | Replace card |
| PATCH | `/v1/cards/{card_id}` | Partial update |
| DELETE | `/v1/cards/{card_id}` | Delete card |

**POST /v1/decks/{deck_id}/cards request:**
```json
{
  "question": "What is the IUPAC name for CH3-CH2-OH?",  // required, 1-1000 chars
  "answer": "Ethanol",                                     // required, 1-2000 chars
  "source_ref": "CHEM301 Lecture 4",                       // optional, max 255 chars
  "tags": ["nomenclature"],                                 // optional
  "difficulty": 3                                           // optional, 1-5, default 3
}
```
Headers: `Idempotency-Key: <uuid_v4>`

**FlashcardResponse (201/200):**
```json
{
  "id": "fcd_abc123def456ab12",
  "deck_id": "dck_0521fbee640de0df",
  "question": "What is the IUPAC name for CH3-CH2-OH?",
  "answer": "Ethanol",
  "source_ref": "CHEM301 Lecture 4",
  "tags": ["nomenclature"],
  "difficulty": 3,
  "created_at": "2026-03-01T09:00:00Z",
  "updated_at": "2026-03-01T09:00:00Z"
}
```

**FlashcardListResponse (GET /v1/decks/{deck_id}/cards):**
```json
{
  "data": [ /* array of FlashcardResponse */ ],
  "pagination": { "page": 1, "per_page": 20, "total": 142, "total_pages": 8 }
}
```

**Error codes:** `CARD_NOT_FOUND` (404), `DECK_NOT_FOUND` (404)

---

#### Sessions

Scope: `sessions:run` (JWT required for all)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/sessions/` | Start session |
| GET | `/v1/sessions/{session_id}` | Get session state |
| POST | `/v1/sessions/{session_id}/answer` | Submit answer |
| POST | `/v1/sessions/{session_id}/skip` | Skip current card |
| POST | `/v1/sessions/{session_id}/end` | End session early |
| GET | `/v1/sessions/{session_id}/summary` | Get session summary |

**POST /v1/sessions/ request:**
```json
{
  "deck_id": "dck_0521fbee640de0df",  // required
  "mode": "review",                    // review | quiz | exam; default review
  "card_limit": 10,                    // optional, 1-100
  "due_only": false,                   // optional, default false
  "focus_weak": false,                 // optional, default false; prioritise low ease_factor cards
  "time_limit_s": 3600                 // optional, minimum 60 seconds
}
```

**Session response (201):**
```json
{
  "session_id": "ses_deadbeef1234abcd",
  "status": "active",
  "cards_total": 10,
  "cards_done": 0,
  "current_card": {
    "id": "fcd_abc123def456ab12",
    "deck_id": "dck_0521fbee640de0df",
    "question": "What is the IUPAC name for CH3-CH2-OH?",
    "answer": null,    // answer hidden in quiz/exam mode
    "source_ref": null,
    "tags": [],
    "difficulty": 3
  },
  "expires_at": "2026-03-25T20:00:00Z",
  "expires_at_local": "2026-03-25T21:00:00+01:00"
}
```

**POST /v1/sessions/{id}/answer request:**
```json
{
  "answer": "Ethanol",    // required, max 2000 chars
  "time_taken_s": 12,     // optional
  "confidence": 2         // optional, 1-3
}
```

**AnswerResult response (200):**
```json
{
  "score": 5,
  "is_correct": true,
  "canonical_answer": "Ethanol",
  "feedback": "Correct! Ethanol is indeed the IUPAC name.",
  "next_card": { /* FlashcardInSession or null if session complete */ },
  "session_progress": { "cards_done": 1, "cards_total": 10 }
}
```

**POST /v1/sessions/{id}/skip response (200):**
```json
{ "next_card": /* FlashcardInSession or null */ }
```

**POST /v1/sessions/{id}/end response (200):**
```json
{ "status": "ended" }
```

**SessionSummary (GET /v1/sessions/{id}/summary, 200):**
```json
{
  "session_id": "ses_deadbeef1234abcd",
  "deck_id": "dck_0521fbee640de0df",
  "mode": "review",
  "status": "ended",
  "started_at": "2026-03-25T19:00:00Z",
  "ended_at": "2026-03-25T19:15:00Z",
  "total_cards": 10,
  "cards_answered": 9,
  "correct_answers": 7,
  "accuracy": 0.78,
  "time_taken_s": 900
}
```

**Session error codes:**
| Status | Code | Trigger |
|--------|------|---------|
| 404 | `SESSION_NOT_FOUND` | Bad session_id |
| 409 | `SESSION_ALREADY_ENDED` | Action on a closed session |
| 409 | `NO_CARDS_AVAILABLE` | Deck has no eligible cards |
| 422 | `ANSWER_TOO_LONG` | Answer > 2000 chars |

---

#### Memory States

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/v1/cards/{card_id}/memory` | JWT | Get SM-2 state for card |
| POST | `/v1/cards/{card_id}/answer` | JWT | Submit standalone answer (score 0-5) |
| GET | `/v1/users/{user_id}/due` | JWT | Get due cards for today |
| GET | `/v1/users/{user_id}/weak-spots` | JWT | Get weakest cards |

**CardMemoryStateResponse:**
```json
{
  "card_id": "fcd_abc123def456ab12",
  "user_id": "usr_a1b2c3d4e5f6a7b8",
  "interval_days": 6.0,
  "ease_factor": 2.5,
  "repetitions": 3,
  "due_at": "2026-03-31T00:00:00Z",
  "due_at_local": "2026-03-31T01:00:00+01:00",
  "last_score": 4,
  "streak": 3
}
```

**POST /v1/cards/{id}/answer request:**
```json
{ "score": 4 }   // 0-5 per SM-2: 0=blackout, 1=wrong, 2=wrong+familiar, 3=correct+hard, 4=correct, 5=perfect
```

**DueCardListResponse (GET /v1/users/{id}/due):**
```json
{
  "due_count": 3,
  "cards": [
    {
      "id": "fcd_abc123",
      "deck_id": "dck_xxx",
      "question": "...",
      "due_at": "2026-03-25T00:00:00Z",
      "due_at_local": "2026-03-25T01:00:00+01:00",
      "overdue_by": "1 day, 3:00:00",
      "overdue_by_seconds": 97200,
      "ease_factor": 1.8
    }
  ]
}
```

**WeakSpotListResponse (GET /v1/users/{id}/weak-spots?limit=10):**
```json
{
  "count": 5,
  "cards": [
    {
      "id": "fcd_abc123",
      "deck_id": "dck_xxx",
      "question": "...",
      "ease_factor": 1.3,
      "last_score": 1,
      "repetitions": 7
    }
  ]
}
```

---

#### Progress

Scope: `progress:read`

| Method | Path |
|--------|------|
| GET | `/v1/users/{user_id}/progress` |
| GET | `/v1/users/{user_id}/progress/{deck_id}` |
| GET | `/v1/users/{user_id}/streak` |

**ProgressResponse:**
```json
{
  "user_id": "usr_a1b2c3d4e5f6a7b8",
  "total_cards": 350,
  "mastered_cards": 212,
  "due_today": 18,
  "accuracy_rate": 0.84,
  "study_streak_days": 7,
  "total_sessions": 89,
  "last_studied_at": "2026-03-24T18:00:00Z",
  "last_studied_at_local": "2026-03-24T19:00:00+01:00",
  "deck_summaries": [
    { "deck_id": "dck_xxx", "name": "Organic Chemistry", "mastery_pct": 69.0, "due_count": 12 }
  ]
}
```

**StreakResponse:**
```json
{
  "streak": 7,
  "last_studied_at": "2026-03-24T18:00:00Z",
  "last_studied_at_local": "2026-03-24T19:00:00+01:00"
}
```

---

#### Study Plans

Scope: generate → `sessions:run`; retrieve → `progress:read`

| Method | Path |
|--------|------|
| POST | `/v1/users/{user_id}/plan` |
| GET | `/v1/users/{user_id}/plan` |

**POST /v1/users/{id}/plan request:**
```json
{
  "deck_id": "dck_0521fbee640de0df",
  "goal": "Master all cards before the exam",  // optional
  "days": 30,                                   // 1-365
  "daily_minutes": 30                           // 1-1440, default 30
}
```

**PlanResponse:**
```json
{
  "plan_id": "pln_abc123def456ab12",
  "deck_id": "dck_0521fbee640de0df",
  "goal": "Master all cards before the exam",
  "days": 30,
  "daily_target": 12,
  "daily_minutes": 30,
  "schedule": [
    { "day": 1, "date": "2026-03-26", "cards_to_study": 12, "focus": "New cards" },
    { "day": 2, "date": "2026-03-27", "cards_to_study": 10, "focus": "Review + new" }
  ],
  "created_at": "2026-03-25T12:00:00Z"
}
```

---

#### CSV Import

Scope: `import:write`

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/import/csv` | Upload CSV; returns 202 immediately |
| GET | `/v1/import/{job_id}` | Poll job status |

**POST /v1/import/csv** — multipart/form-data:
```
file:      <CSV file bytes, UTF-8, max 5 MB>
deck_id:   dck_xxx           (mutually exclusive with deck_name)
deck_name: "New Deck"        (mutually exclusive with deck_id; creates new deck)
mode:      merge | replace   (default: merge)
```

**ImportJobCreateResponse (202):**
```json
{
  "job_id": "imp_deadbeefcafe1234",
  "status": "queued",
  "deck_id": "dck_0521fbee640de0df"
}
```

**ImportJobStatusResponse (GET /v1/import/{job_id}, 200):**
```json
{
  "job_id": "imp_deadbeefcafe1234",
  "status": "completed",            // queued | processing | completed | failed
  "cards_imported": 87,
  "cards_skipped": 3,
  "errors": ["Row 12: missing answer column"],
  "completed_at": "2026-03-25T12:05:00Z",
  "completed_at_local": "2026-03-25T13:05:00+01:00"
}
```

**CSV format constraints:**
- Must be UTF-8 (BOM accepted)
- Maximum size: 5 MB
- Filename max 255 chars
- Must not be empty

---

### 11.4 Standard Error Format

All errors from the API follow this envelope:

```json
{
  "error": {
    "code": "DECK_NOT_FOUND",
    "message": "Deck not found.",
    "status": 404,
    "request_id": "req_7f3a9c12",
    "details": null,
    "resource": {
      "type": "deck",
      "id": "dck_x9y8z7w6",
      "name": null
    }
  }
}
```

**Dart sealed class for error handling:**
```dart
sealed class ApiError {
  const ApiError();
}
class ValidationError extends ApiError { final String message; final Map<String,dynamic>? details; const ValidationError(this.message, {this.details}); }
class AuthError extends ApiError { final String code; const AuthError(this.code); }
class NotFoundError extends ApiError { final String resourceType; final String? resourceId; const NotFoundError(this.resourceType, {this.resourceId}); }
class ConflictError extends ApiError { final String code; const ConflictError(this.code); }
class RateLimitError extends ApiError { const RateLimitError(); }
class ServerError extends ApiError { final int status; const ServerError(this.status); }
class NetworkError extends ApiError { final Object cause; const NetworkError(this.cause); }
```

### 11.5 Retry & Timeout Strategy

```dart
// lib/core/infrastructure/http/retry_interceptor.dart
// Settings:
const int maxRetries = 3;
const Duration baseDelay = Duration(milliseconds: 500);
// Retry on: DioException (connection timeout, receive timeout, network error)
// Do NOT retry on: 401, 403, 404, 409, 422, 429
// Exponential backoff: delay = baseDelay * 2^attempt
// Jitter: add Random().nextInt(200) ms to avoid thundering herd
```

### 11.6 Idempotency Key Generation

```dart
// lib/shared/utils/idempotency_key.dart
import 'package:uuid/uuid.dart';
String generateIdempotencyKey() => const Uuid().v4();
// Usage: include as 'Idempotency-Key' header on POST /v1/decks and POST /v1/decks/{id}/cards
```

---

## 12. Data Models (Dart)

All models use `freezed` + `json_serializable`. Files live in `lib/features/<feature>/models/`.

### 12.1 UserProfile

```dart
// lib/features/profile/models/user_profile.dart
import 'package:freezed_annotation/freezed_annotation.dart';
part 'user_profile.freezed.dart';
part 'user_profile.g.dart';

enum EducationLevel { none, secondary, undergraduate, postgraduate, professional }

@freezed
class UserProfile with _$UserProfile {
  const factory UserProfile({
    required String id,
    String? displayName,
    required String country,
    String? locale,
    required String timezone,
    EducationLevel? educationLevel,
    required String preferredLanguage,
    required int dailyGoalCards,
    required DateTime createdAt,
    String? localTime,
    String? createdAtLocal,
  }) = _UserProfile;

  factory UserProfile.fromJson(Map<String, dynamic> json) => _$UserProfileFromJson(json);
}
```

### 12.2 Deck & DeckListItem

```dart
// lib/features/decks/models/deck.dart
@freezed
class Deck with _$Deck {
  const factory Deck({
    required String id,
    required String name,
    String? description,
    required List<String> tags,
    required int cardCount,
    required int version,
    required DateTime createdAt,
    required DateTime updatedAt,
    String? sourceFile,
  }) = _Deck;
  factory Deck.fromJson(Map<String, dynamic> json) => _$DeckFromJson(json);
}

@freezed
class DeckListItem with _$DeckListItem {
  const factory DeckListItem({
    required String id,
    required String name,
    required int cardCount,
    required List<String> tags,
    required DateTime createdAt,
    required DateTime updatedAt,
  }) = _DeckListItem;
  factory DeckListItem.fromJson(Map<String, dynamic> json) => _$DeckListItemFromJson(json);
}

@freezed
class DeckListResponse with _$DeckListResponse {
  const factory DeckListResponse({
    required List<DeckListItem> data,
    required PaginationMeta pagination,
  }) = _DeckListResponse;
  factory DeckListResponse.fromJson(Map<String, dynamic> json) => _$DeckListResponseFromJson(json);
}
```

### 12.3 Flashcard

```dart
// lib/features/cards/models/flashcard.dart
@freezed
class Flashcard with _$Flashcard {
  const factory Flashcard({
    required String id,
    required String deckId,
    required String question,
    required String answer,
    String? sourceRef,
    required List<String> tags,
    required int difficulty,   // 1-5
    required DateTime createdAt,
    required DateTime updatedAt,
  }) = _Flashcard;
  factory Flashcard.fromJson(Map<String, dynamic> json) => _$FlashcardFromJson(json);
}
```

### 12.4 Session

```dart
// lib/features/sessions/models/session.dart
enum SessionMode { review, quiz, exam }
enum SessionStatus { active, ended }

@freezed
class FlashcardInSession with _$FlashcardInSession {
  const factory FlashcardInSession({
    required String id,
    required String deckId,
    String? question,
    String? answer,            // null in quiz/exam until revealed
    String? sourceRef,
    List<String>? tags,
    int? difficulty,
  }) = _FlashcardInSession;
  factory FlashcardInSession.fromJson(Map<String, dynamic> json) => _$FlashcardInSessionFromJson(json);
}

@freezed
class Session with _$Session {
  const factory Session({
    required String sessionId,
    required SessionStatus status,
    required int cardsTotal,
    required int cardsDone,
    FlashcardInSession? currentCard,
    required DateTime expiresAt,
    required String expiresAtLocal,
  }) = _Session;
  factory Session.fromJson(Map<String, dynamic> json) => _$SessionFromJson(json);
}

@freezed
class AnswerResult with _$AnswerResult {
  const factory AnswerResult({
    required int score,
    required bool isCorrect,
    required String canonicalAnswer,
    required String feedback,
    FlashcardInSession? nextCard,
    required Map<String, int> sessionProgress,
  }) = _AnswerResult;
  factory AnswerResult.fromJson(Map<String, dynamic> json) => _$AnswerResultFromJson(json);
}

@freezed
class SessionSummary with _$SessionSummary {
  const factory SessionSummary({
    required String sessionId,
    required String deckId,
    required SessionMode mode,
    required SessionStatus status,
    required DateTime startedAt,
    DateTime? endedAt,
    required int totalCards,
    required int cardsAnswered,
    required int correctAnswers,
    required double accuracy,
    required int timeTakenS,
  }) = _SessionSummary;
  factory SessionSummary.fromJson(Map<String, dynamic> json) => _$SessionSummaryFromJson(json);
}
```

### 12.5 MemoryState

```dart
// lib/features/memory/models/memory_state.dart
@freezed
class CardMemoryState with _$CardMemoryState {
  const factory CardMemoryState({
    required String cardId,
    required String userId,
    double? intervalDays,
    required double easeFactor,   // default 2.5, min 1.3
    required int repetitions,
    DateTime? dueAt,
    String? dueAtLocal,
    int? lastScore,               // 0-5
    required int streak,
  }) = _CardMemoryState;
  factory CardMemoryState.fromJson(Map<String, dynamic> json) => _$CardMemoryStateFromJson(json);
}

@freezed
class DueCard with _$DueCard {
  const factory DueCard({
    required String id,
    required String deckId,
    required String question,
    required DateTime dueAt,
    String? dueAtLocal,
    String? overdueBy,
    int? overdueBySeconds,
    required double easeFactor,
  }) = _DueCard;
  factory DueCard.fromJson(Map<String, dynamic> json) => _$DueCardFromJson(json);
}
```

### 12.6 Progress & Streak

```dart
// lib/features/progress/models/progress.dart
@freezed
class DeckSummary with _$DeckSummary { ... }

@freezed
class UserProgress with _$UserProgress {
  const factory UserProgress({
    required String userId,
    required int totalCards,
    required int masteredCards,
    required int dueToday,
    required double accuracyRate,
    required int studyStreakDays,
    required int totalSessions,
    DateTime? lastStudiedAt,
    String? lastStudiedAtLocal,
    required List<DeckSummary> deckSummaries,
  }) = _UserProgress;
  factory UserProgress.fromJson(Map<String, dynamic> json) => _$UserProgressFromJson(json);
}

@freezed
class Streak with _$Streak {
  const factory Streak({
    required int streak,
    DateTime? lastStudiedAt,
    String? lastStudiedAtLocal,
  }) = _Streak;
  factory Streak.fromJson(Map<String, dynamic> json) => _$StreakFromJson(json);
}
```

### 12.7 StudyPlan

```dart
// lib/features/plans/models/study_plan.dart
@freezed
class ScheduleDay with _$ScheduleDay {
  const factory ScheduleDay({
    required int day,
    required String date,         // YYYY-MM-DD in user's local timezone
    required int cardsToStudy,
    required String focus,
  }) = _ScheduleDay;
  factory ScheduleDay.fromJson(Map<String, dynamic> json) => _$ScheduleDayFromJson(json);
}

@freezed
class StudyPlan with _$StudyPlan {
  const factory StudyPlan({
    required String planId,
    required String deckId,
    String? goal,
    required int days,
    required int dailyTarget,
    required int dailyMinutes,
    required List<ScheduleDay> schedule,
    required DateTime createdAt,
  }) = _StudyPlan;
  factory StudyPlan.fromJson(Map<String, dynamic> json) => _$StudyPlanFromJson(json);
}
```

### 12.8 ImportJob

```dart
// lib/features/imports/models/import_job.dart
enum ImportJobStatus { queued, processing, completed, failed }

@freezed
class ImportJobStatus_ with _$ImportJobStatus_ { ... }

@freezed
class ImportJobResult with _$ImportJobResult {
  const factory ImportJobResult({
    required String jobId,
    required ImportJobStatus status,
    required int cardsImported,
    required int cardsSkipped,
    required List<String> errors,
    DateTime? completedAt,
    String? completedAtLocal,
  }) = _ImportJobResult;
  factory ImportJobResult.fromJson(Map<String, dynamic> json) => _$ImportJobResultFromJson(json);
}
```

### 12.9 Pagination

```dart
// lib/core/domain/entities/pagination.dart
@freezed
class PaginationMeta with _$PaginationMeta {
  const factory PaginationMeta({
    required int page,
    required int perPage,
    required int total,
    required int totalPages,
  }) = _PaginationMeta;
  factory PaginationMeta.fromJson(Map<String, dynamic> json) => _$PaginationMetaFromJson(json);
}
```

### 12.10 Wellness / Usage (Local-only, Drift tables)

```dart
// lib/features/wellness/models/app_usage_record.dart
// Stored in Drift SQLite DB, NOT sent to any server

class AppUsageRecord {
  final String packageName;    // e.g. com.instagram.android
  final String appLabel;       // display name
  final DateTime date;         // UTC date truncated to day
  final int totalForegroundMs; // total milliseconds in foreground
}

class AppLimit {
  final String packageName;
  final int dailyLimitSeconds; // user-configured limit
  final int snoozeCountToday;  // max 3
}
```

---

## 13. State Management Design

### Choice: Riverpod 2.x with code generation (`riverpod_generator`)

**Justification:**
- **Compile-safe**: providers are generated, eliminating runtime type errors
- **Granular rebuild control**: `select()` prevents unnecessary widget rebuilds
- **Testable without BuildContext**: providers are plain Dart objects, injectable in unit tests
- **No boilerplate overhead vs. Bloc**: Bloc requires Event/State/Bloc triplets per feature; Riverpod `AsyncNotifier` handles the same patterns in one class
- **First-class async support**: `AsyncValue<T>` models loading/data/error states naturally, mapping directly onto API call lifecycle

**Rejected alternatives:**
- *Bloc*: excellent for complex event-driven flows but over-engineered for this CRUD-oriented app with straightforward async data
- *GetX*: opinionated global state anti-pattern; poor testability
- *Provider (v6)*: predecessor to Riverpod; lacks code generation and type safety improvements

### Provider Pattern

```dart
// Example: Deck list provider
@riverpod
class DeckList extends _$DeckList {
  @override
  Future<DeckListResponse> build({int page = 1, int perPage = 20}) async {
    return ref.watch(deckRepositoryProvider).listDecks(page: page, perPage: perPage);
  }

  Future<void> refresh() => ref.refresh(deckListProvider().future);
}

// Example: Session state (complex, long-lived)
@riverpod
class ActiveSession extends _$ActiveSession {
  @override
  Session? build() => null;  // null = no active session

  Future<void> start(SessionStart params) async {
    state = await ref.read(sessionRepositoryProvider).startSession(params);
  }

  Future<AnswerResult> submitAnswer(SessionAnswer answer) async {
    final result = await ref.read(sessionRepositoryProvider)
        .submitAnswer(state!.sessionId, answer);
    state = state!.copyWith(
      cardsDone: result.sessionProgress['cards_done']!,
      currentCard: result.nextCard,
    );
    return result;
  }
}
```

### Auth Provider

```dart
@riverpod
class AuthState extends _$AuthState {
  @override
  FutureOr<String?> build() async {  // returns JWT or null
    return ref.watch(secureStorageProvider).loadCredentials()
        .then((creds) => creds != null
            ? ref.read(authRepositoryProvider).exchangeToken(creds)
            : null);
  }
}
```

### Dependency Injection

All repositories and services are provided via `@riverpod` providers:

```
secureStorageProvider     → FlutterSecureStorage
apiClientProvider         → Dio instance (singleton)
authRepositoryProvider    → AuthRepositoryImpl(apiClient)
deckRepositoryProvider    → DeckRepositoryImpl(apiClient)
sessionRepositoryProvider → SessionRepositoryImpl(apiClient)
...
```

No external DI container (get_it, injectable) is needed; Riverpod's provider graph is the DI container.

---

## 14. AI / Recommendation Engine Design

### 14.1 Overview

The AI engine runs fully on-device. It consumes per-app usage time series from the local Drift DB and outputs overuse signals and reduction targets. No data is transmitted off-device.

### 14.2 Input Feature Vector

For each app, the model receives a **14-day rolling window** of daily screen-time values (in minutes):

```
Input tensor: float32[1, 14]   (batch=1, timesteps=14)
```

The `UsageFeatureExtractor` class computes:
- `last_14_days[i]` = `totalForegroundMs / 60000` for each of the last 14 days (0 if no record)
- Values are normalised: `x_norm = x / max(x, 1)` (to range 0–1)

### 14.3 Output

```
Output tensor: float32[1, 2]
  [0]: overuse_score    ∈ [0.0, 1.0]  — 0 = normal, 1 = severe overuse
  [1]: reduction_ratio  ∈ [0.0, 1.0]  — suggested reduction as fraction of current usage
```

### 14.4 TFLite Model

**File:** `assets/models/usage_classifier.tflite`

The model is a simple 1D convolutional network:
- Input: 14 timesteps of normalised daily usage
- Conv1D(8 filters, kernel=3, relu) → GlobalAveragePooling → Dense(16, relu) → Dense(2, sigmoid)
- Total parameters: < 500; inference time: < 5 ms on mid-range device

**Training note:** The bundled model is pre-trained on synthetic usage data with known overuse patterns. It must be replaced with a model trained on real usage data before production. The Dart model file path and loading logic is decoupled from training.

### 14.5 Dart Wrapper

```dart
// lib/features/wellness/ml/usage_classifier.dart
import 'package:tflite_flutter/tflite_flutter.dart';

class UsageClassifier {
  late Interpreter _interpreter;

  Future<void> load() async {
    _interpreter = await Interpreter.fromAsset('assets/models/usage_classifier.tflite');
  }

  UsageInsight classify(List<double> last14DaysMinutes) {
    final input = [last14DaysMinutes.map((v) => v / (last14DaysMinutes.reduce(max) + 1)).toList()];
    final output = List.filled(2, 0.0).reshape([1, 2]);
    _interpreter.run(input, output);
    return UsageInsight(
      overuseScore: output[0][0],
      reductionRatio: output[0][1],
    );
  }
}

class UsageInsight {
  final double overuseScore;    // 0.0-1.0
  final double reductionRatio;  // 0.0-1.0
}
```

### 14.6 Insight Copy Generation

The `InsightsProvider` translates model output into human-readable strings:

```dart
String generateInsightCopy(String appLabel, double overuseScore,
    double reductionRatio, double averageDailyMinutes) {
  if (overuseScore < 0.4) return '$appLabel usage is within normal range.';
  final reduceByMin = (averageDailyMinutes * reductionRatio).round();
  final severity = overuseScore > 0.7 ? 'significantly' : 'moderately';
  return 'You\'ve been using $appLabel $severity more than usual. '
      'Consider reducing by $reduceByMin min/day this week.';
}
```

### 14.7 Model Update Strategy

- Bundled model version stored in `SharedPreferences` as `tflite_model_version`
- A reserved future endpoint (`GET /v1/models/latest`) can return a signed model URL
- `ModelUpdateService` compares versions on app launch; downloads via background isolate if update available
- Downloaded model stored in app's private directory; falls back to bundled model on failure

---

## 15. OS-Level Constraints (Android vs iOS)

### 15.1 Feature Matrix

| Feature | Android (API 26+) | iOS (15+) |
|---------|-------------------|-----------|
| App usage tracking (all apps) | ✅ `UsageStatsManager` + `PACKAGE_USAGE_STATS` | ❌ Not available to third-party apps |
| Per-app daily limits (hard enforcement) | ✅ `SYSTEM_ALERT_WINDOW` overlay | ❌ Warning notification only |
| Focus Mode (block all notifications) | ✅ `NotificationManager.setInterruptionFilter(NONE)` | ❌ Cannot control system DND programmatically |
| CSV file picker | ✅ `file_picker` package | ✅ `file_picker` package |
| Secure storage | ✅ Android Keystore | ✅ Secure Enclave (Keychain) |
| Background service for usage polling | ✅ Foreground Service | ❌ Background App Refresh (limited, no equivalent) |
| Push notifications (future) | ✅ FCM | ✅ APNs |
| JWT in-memory (no disk) | ✅ | ✅ |

### 15.2 Android Implementation Details

#### Required Permissions (`AndroidManifest.xml`)

```xml
<!-- Usage stats — requires user to grant in Settings > Apps > Special app access > Usage access -->
<uses-permission android:name="android.permission.PACKAGE_USAGE_STATS"
    tools:ignore="ProtectedPermissions"/>

<!-- DND control — requires user to grant via notification policy access settings -->
<uses-permission android:name="android.permission.ACCESS_NOTIFICATION_POLICY"/>

<!-- Overlay — requires user to grant "Appear on top" in Settings -->
<uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW"/>

<!-- Foreground service for usage monitoring -->
<uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC"/>

<!-- Network -->
<uses-permission android:name="android.permission.INTERNET"/>
<uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>
```

#### UsageStatsManager (Kotlin — `UsageStatsChannel.kt`)

```kotlin
// MethodChannel: "com.mnemo.app/usage_stats"
// Method: "queryDailyUsage" → Map<String, Long> { packageName: foregroundMs }
fun queryDailyUsage(context: Context): Map<String, Long> {
    val usm = context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
    if (!hasUsagePermission(context)) return emptyMap()
    val end = System.currentTimeMillis()
    val start = end - 24 * 60 * 60 * 1000L  // last 24h
    return usm.queryUsageStats(UsageStatsManager.INTERVAL_DAILY, start, end)
        .filter { it.totalTimeInForeground > 0 }
        .associate { it.packageName to it.totalTimeInForeground }
}

fun hasUsagePermission(context: Context): Boolean {
    val appOps = context.getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
    val mode = appOps.checkOpNoThrow(AppOpsManager.OPSTR_GET_USAGE_STATS,
        Process.myUid(), context.packageName)
    return mode == AppOpsManager.MODE_ALLOWED
}
```

#### DND Control (Kotlin — `DndChannel.kt`)

```kotlin
// MethodChannel: "com.mnemo.app/dnd_control"
// Methods: "enableDnd" → void, "disableDnd" → void, "hasPermission" → Boolean
fun enableDnd(context: Context) {
    val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    if (nm.isNotificationPolicyAccessGranted) {
        nm.setInterruptionFilter(NotificationManager.INTERRUPTION_FILTER_NONE)
    }
}
fun disableDnd(context: Context, previousFilter: Int) {
    val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
    nm.setInterruptionFilter(previousFilter)  // restore saved state
}
```

#### Overlay Window (Kotlin — `OverlayService.kt`)

```kotlin
// Launched when app usage exceeds limit
// Displays a blocking View (TYPE_APPLICATION_OVERLAY) with:
//   - App name + time overrun
//   - "I'm done" button (dismisses overlay for the session)
//   - "5 more minutes" snooze button (max 3× per day stored in SharedPreferences)
// Cannot be fully dismissed for the rest of the day
```

### 15.3 iOS Implementation Details

The Flutter app compiles and runs on iOS with the following behaviour differences:

- `UsageStatsChannel` and `DndChannel` are stubbed in `ios/Runner/StubChannels.swift` to return empty maps / false / no-op
- The Wellness tab shows an informational banner: *"Advanced usage tracking and Focus Mode are not available on iOS due to system restrictions."*
- `usage_provider.dart` checks `Platform.isAndroid` before calling the MethodChannel; on iOS it returns empty `UsageData`
- Per-app limits are stored in Drift but enforcement is a notification only (via `flutter_local_notifications`)

### 15.4 Permission Request Flow (Android)

```
App startup
  │
  ├─ PACKAGE_USAGE_STATS granted?
  │     └─ NO: Show rationale dialog on first Wellness tab open
  │            → "Allow" → Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS)
  │            → App resumes → re-check
  │
  ├─ ACCESS_NOTIFICATION_POLICY granted?
  │     └─ NO: Show rationale dialog when Focus Mode is first toggled
  │            → "Allow" → Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS)
  │
  └─ SYSTEM_ALERT_WINDOW granted?
        └─ NO: Show rationale dialog when limit is first reached
               → "Allow" → Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION)
```

---

## 16. Security & Privacy Considerations

### 16.1 Credential Storage

| Data | Storage | Encryption |
|------|---------|------------|
| `api_key` | `flutter_secure_storage` | Android Keystore AES-256; iOS Keychain |
| `user_id` | `flutter_secure_storage` | Same as above |
| JWT | In-memory Riverpod `StateProvider` only | Never persisted to disk |
| Usage data | Drift SQLite (device private dir) | SQLite file not additionally encrypted in MVP; plan encrypted Drift for v2 |
| App limits | Drift SQLite | Same as above |

### 16.2 Transport Security

- All API calls use HTTPS. `Dio` is configured with `BaseOptions` requiring TLS; no http:// domains are allowed in production builds
- Certificate pinning is **not** implemented in MVP (acceptable for personal utility); it is reserved as a future enhancement
- On Android, `network_security_config.xml` disables cleartext traffic:
  ```xml
  <base-config cleartextTrafficPermitted="false" />
  ```

### 16.3 Data Minimisation

- No usage data (other apps' activity) leaves the device. The Drift DB is local-only
- TFLite inference runs synchronously on the UI isolate or a compute isolate; no network call involved
- No analytics SDK (Firebase Analytics, Crashlytics) is included in MVP to avoid accidental data egress

### 16.4 API Key Exposure Prevention

- API key is never logged; `ApiClient` strips `Authorization` headers before writing to any log sink
- Pattern validation `^mnm_(live|test)_[a-f0-9]{64}$` is enforced before storage to catch accidental clipboard pastes of wrong values

### 16.5 Input Validation

- All user-supplied text is length-capped in the UI before submission (matching server-side limits):
  - Question: 1000 chars
  - Answer: 2000 chars
  - Deck name: 128 chars
  - Tags: 32 chars each
- CSV file size capped at 5 MB client-side before upload (matching `csv_max_size_bytes` server limit)
- No eval/exec of user-supplied content anywhere in the app

### 16.6 OWASP Mobile Top 10 Mitigations

| Risk | Mitigation |
|------|-----------|
| M1: Improper Credential Usage | API key in Keystore/Keychain; JWT in memory only |
| M2: Inadequate Supply Chain Security | `pub.dev` packages only; `dart pub audit` run in CI |
| M3: Insecure Authentication | Token-based; re-auth on 401; no biometric bypass |
| M4: Insufficient Input/Output Validation | Client-side length guards on all text inputs |
| M5: Insecure Communication | HTTPS-only; cleartext disabled |
| M6: Inadequate Privacy Controls | No PII leaves device except what user explicitly submits to API |
| M7: Insufficient Binary Protections | Android: `minifyEnabled true`, `shrinkResources true` in release builds |
| M8: Security Misconfiguration | No debug flags in release; `android:debuggable="false"` |
| M9: Insecure Data Storage | No sensitive data in SharedPreferences plain text |
| M10: Insufficient Cryptography | Keystore/Keychain for credentials; no custom crypto |

---

## 17. Scalability Strategy

This section addresses the app's ability to handle growing data and usage over time.

### 17.1 Pagination

All list endpoints use cursor-compatible pagination (`page` + `per_page`). The `PaginatedList<T>` widget handles infinite scroll by appending pages. The Riverpod `DeckListNotifier` tracks current page and total_pages to prevent over-fetching.

### 17.2 Local Database Growth

The Drift SQLite DB accumulates usage records (one row per app per day). A background `DataRetentionJob` runs weekly via `WorkManager` to prune records older than 90 days.

### 17.3 Session State Isolation

Session state is held in a scoped `Riverpod` provider that is disposed when the session screen is popped. There is no global session store accumulation.

### 17.4 Lazy Loading

- Deck card lists are loaded on demand (only when the user opens a deck)
- Session cards are served one at a time by the API; no pre-fetching is needed
- The TFLite model is loaded once at `WellnessScreen` init and stays resident while the screen is alive

### 17.5 Foreground Service Efficiency

`UsageMonitorService` polls at 60 s intervals using an `AlarmManager` with `setExactAndAllowWhileIdle`. Between polls the service is idle (no CPU wakelock held). If battery saver mode is active, polling interval doubles to 120 s.

---

## 18. Extensibility Strategy

### 18.1 Service Abstraction Layer

Every external data source is accessed through an abstract Dart interface in `lib/core/domain/repositories/`. No feature widget or provider imports a concrete implementation directly.

```
Widget → Provider → Repository (abstract) → RepositoryImpl (concrete) → ApiRemoteSource / LocalSource
```

Adding a new API (e.g., a vocabulary service) requires:
1. Define new abstract repository in `lib/core/domain/repositories/`
2. Implement concrete class reading from the new API
3. Register a new `@riverpod` provider
4. No changes to existing features

### 18.2 Feature Module Pattern

Each feature in `lib/features/` is a self-contained vertical slice:
- `data/` — remote and local data sources
- `domain/` — abstract interfaces and entity logic
- `models/` — Freezed data classes
- `providers/` — Riverpod providers
- `presentation/` — screens and widgets

New features can be added as complete new directories without touching existing code. The router in `lib/core/routing/app_router.dart` is the single registration point.

### 18.3 Platform Channel Abstraction

The `usage_stats_channel.dart` and `dnd_channel.dart` Dart wrappers are accessed only through abstract interfaces:

```dart
abstract class UsageStatsService {
  Future<Map<String, int>> queryDailyUsage();
  Future<bool> hasPermission();
}
```

To add Huawei HMS support or iOS ScreenTime API (if it ever opens up), only the concrete implementation needs to change.

### 18.4 Feature Flags

A `FeatureFlags` class in `lib/core/config/` controls which features render:

```dart
class FeatureFlags {
  static const bool usageTracking = bool.fromEnvironment('FEATURE_USAGE_TRACKING', defaultValue: true);
  static const bool focusMode = bool.fromEnvironment('FEATURE_FOCUS_MODE', defaultValue: true);
  static const bool aiInsights = bool.fromEnvironment('FEATURE_AI_INSIGHTS', defaultValue: true);
  static const bool csvImport = bool.fromEnvironment('FEATURE_CSV_IMPORT', defaultValue: true);
}
```

Flags are set at build time via `--dart-define`; no runtime network toggle needed for MVP.

### 18.5 API Version Isolation

The Dio `ApiClient` injects `/v1` as a path segment. When the API introduces `/v2`, a new `ApiClientV2` can be instantiated with the new prefix; old and new can coexist during the migration window.

---

## 19. UX/UI Design Guidelines

### 19.1 Design System

- **Framework:** Flutter Material Design 3 (`useMaterial3: true`)
- **Color scheme:** Generated from seed color `Color(0xFF4A90D9)` (calm blue — conducive to learning)
- **Typography:** `GoogleFonts.inter` for body text; `GoogleFonts.interTight` for headings
- **Icon set:** `material_symbols_outlined` package (filled on selected state)
- **Theme:** Supports light and dark modes; follows system preference by default

### 19.2 Navigation Structure

```
BottomNavigationBar (4 tabs):
  1. Home        — due cards count badge, streak chip, quick-start buttons
  2. Decks       — paginated deck list, search, import
  3. Progress    — stats, streak calendar, deck summaries
  4. Wellness    — usage dashboard, limits, AI insights (Android badge if perms needed)
  
Floating: Settings (top-right AppBar action)
```

### 19.3 Session Screen Layout

```
┌─────────────────────────────────┐
│  [←] Deck: Organic Chemistry    │  AppBar (semi-transparent)
│                          [09:42]│  ← TimerChip (top-right, compact)
├─────────────────────────────────┤
│                                 │
│  Card 3 / 10                    │  Progress indicator
│  ●●●○○○○○○○                     │  Dot row
│                                 │
│ ┌─────────────────────────────┐ │
│ │                             │ │
│ │  What is the IUPAC name     │ │  Card widget (tappable to flip)
│ │  for CH3-CH2-OH?            │ │
│ │                             │ │
│ └─────────────────────────────┘ │
│                                 │
│  Type your answer...            │  TextField (auto-focus)
│                                 │
│  [Skip]    [Confidence: ●●○]  [Submit]  │  Action row
└─────────────────────────────────┘
```

### 19.4 StudyTimer Widget

The `TimerChip` widget (`lib/features/sessions/presentation/widgets/timer_chip.dart`):
- Default state: compact pill showing `MM:SS` (countdown) or `MM:SS elapsed`
- On tap: expands to show full details + pause button (if mode allows)
- Auto-collapses after 3 s of inactivity
- Color transitions: green (>50% time left) → amber (<30%) → red (<10%)
- Implemented as a Stack overlay positioned using `Align(Alignment.topRight)` within the session Scaffold

### 19.5 Wellness Dashboard

```
┌─────────────────────────────────┐
│  Today's Screen Time            │
│  4h 23m     ↑12% vs yesterday  │
├─────────────────────────────────┤
│  Top apps                       │
│  📱 TikTok       ██████  1h 47m │  ← red if near/over limit
│  📸 Instagram    ████    58m    │
│  🌐 Chrome       ██      28m    │
│  [See all apps]                 │
├─────────────────────────────────┤
│  AI Insight ✨                  │
│  "You've been using TikTok      │
│   significantly more than usual.│
│   Consider reducing by 30 min." │
├─────────────────────────────────┤
│  Focus Mode                     │
│  [ Toggle ]  ← Android only     │
└─────────────────────────────────┘
```

### 19.6 Error & Empty State Design

- **Network error:** Snackbar with "Retry" action for transient errors; full-screen error widget with retry button for initial load failures
- **Empty deck list:** Illustrated empty state (`assets/icons/empty_decks.svg`) with "Create your first deck" CTA
- **Degraded API:** Yellow banner at top of Home screen: "Some services are temporarily unavailable"
- **Loading:** `Shimmer`-style skeletons matching the shape of the content they replace

### 19.7 Accessibility

- Minimum touch target: 48 × 48 dp (Material3 default)
- All icons have `Semantics(label: ...)` wrappers
- Colour is never the sole indicator of state (shapes and text always accompany colour)
- `MediaQuery.textScaleFactor` is respected; no hardcoded font sizes below 12 sp

---

## 20. Edge Cases & Failure Handling

### 20.1 Authentication Edge Cases

| Scenario | Handling |
|----------|----------|
| Token expires mid-session | `AuthInterceptor` catches 401, refreshes token, retries original request once |
| Token refresh returns 401 | Clear all credentials from SecureStorage; redirect to Onboarding |
| API key pattern invalid (user typo) | Client-side regex validation before submit; show inline error |
| API key belongs to different user | Server returns `API_KEY_OWNER_MISMATCH` (403); show clear error message |
| Network unreachable at startup | Show retry screen; do not crash or loop token exchange |

### 20.2 Session Edge Cases

| Scenario | Handling |
|----------|----------|
| `current_card` is null in response | Session is complete; auto-navigate to summary screen |
| Session has already ended (409) | Dismiss session screen; show "Session already ended" snackbar; fetch summary |
| Answer too long (422) | Client-side TextField `maxLength: 2000`; this should never reach the server |
| No cards available (409) | Show "No eligible cards in this deck for this session type" dialog |
| Device lost network mid-session | `NetworkError` caught; show "No connection" banner with "Retry last action" button |
| Time limit expires | Timer triggers `endSession()` automatically; navigate to summary |
| Focus Mode DND permission revoked mid-session | On Android `BroadcastReceiver` detects change; update Focus Mode toggle to off state |

### 20.3 Usage Tracking Edge Cases

| Scenario | Handling |
|----------|----------|
| `PACKAGE_USAGE_STATS` denied | Wellness tab shows permission prompt; all tracking features gated behind it |
| `UsageStatsManager` returns no data | Empty state in dashboard; no crash |
| App is uninstalled by user (limit was set) | Drift record remains; `AppLimit` screen shows "(app removed)" label; orphaned record pruned after 30 days |
| Usage data collected for >1000 apps | Dashboard shows top 30 only; "See all" leads to searchable full list |
| Snooze count maxed (3× per day) | "5 more minutes" button disabled; only "I'm done" remains |
| Device rebooted (Foreground Service killed) | `StartForegroundService` called again in `BootCompletedReceiver` |

### 20.4 Import Edge Cases

| Scenario | Handling |
|----------|----------|
| File > 5 MB | `file_picker` returns path; app reads size before upload and rejects with dialog |
| Non-UTF-8 CSV | Server returns `INVALID_CSV_FORMAT` 400; surface error with "Re-save as UTF-8" hint |
| Job stuck in `processing` >5 min | Polling times out after 300 s; show "Import taking longer than expected; check status later" |
| Network drops during polling | `RetryInterceptor` handles; polling continues from last status |
| `deck_id` and `deck_name` both provided | Client-side validation prevents this before submission |

### 20.5 SM-2 / Memory State Edge Cases

| Scenario | Handling |
|----------|----------|
| Card has never been answered | `GET /v1/cards/{id}/memory` returns default state (ease_factor: 2.5, repetitions: 0) |
| Invalid score (client bug) | Client enforces score ∈ {0,1,2,3,4,5}; segmented control UI prevents invalid values |
| `due_at` is null | Card is newly created; display "Not yet scheduled" in memory state screen |
| Timezone changes globally | `due_at_local` recalculated on next API fetch; no local recalculation |

---

## 21. Future Enhancements

Listed in priority order for post-MVP roadmap planning:

| Priority | Enhancement | Notes |
|----------|-------------|-------|
| P1 | **Offline mode** — full read access and answer queueing | Requires Drift as offline store + sync queue; API idempotency keys already support this |
| P1 | **Rich notifications** — daily review reminders | Android FCM / iOS APNs; `firebase_messaging` package |
| P2 | **TFLite model update OTA** | `GET /v1/models/latest` endpoint + background download service |
| P2 | **Encrypted local database** | `drift_encryption` or SQLCipher via `sqflite_sqlcipher` |
| P2 | **iOS Screen Time** — read-only (Apple ScreenTime API) | Available only via MDM / Family Sharing entitlement; not open to App Store apps as of 2026 |
| P3 | **Card image support** — attach images to questions | API extension required; local image handling with `image_picker` |
| P3 | **Markdown rendering** — questions/answers in Markdown | `flutter_markdown` package; no API change needed |
| P3 | **Biometric lock** — unlock app with fingerprint/FaceID | `local_auth` package; wraps SecureStorage retrieval |
| P3 | **Export decks to CSV** | Client-side CSV generation from `GET /v1/decks/{id}/cards` |
| P4 | **Gamification** — badges, leaderboards | New API domain; extensibility architecture supports this without touching existing features |
| P4 | **Widget (Android home screen)** — due card count | `home_widget` package |
| P4 | **Apple Watch / Wear OS companion** — quick card review | Separate Flutter app target |
| P5 | **Certificate pinning** | Add `dio_http2_adapter` + pinned certificate for production hardening |

---

## Appendix A — pubspec.yaml (Recommended Dependencies)

```yaml
name: mnemo
description: Personal spaced-repetition and digital wellness app
publish_to: none
version: 1.0.0+1

environment:
  sdk: ">=3.3.0 <4.0.0"

dependencies:
  flutter:
    sdk: flutter

  # HTTP
  dio: ^5.4.0
  dio_smart_retry: ^6.0.0

  # State management
  flutter_riverpod: ^2.5.0
  riverpod_annotation: ^2.3.0

  # Data models
  freezed_annotation: ^2.4.0
  json_annotation: ^4.9.0

  # Navigation
  go_router: ^13.2.0

  # Secure storage
  flutter_secure_storage: ^9.0.0

  # Local database
  drift: ^2.18.0
  sqlite3_flutter_libs: ^0.5.0
  path_provider: ^2.1.0
  path: ^1.9.0

  # UI
  google_fonts: ^6.2.0
  fl_chart: ^0.67.0           # bar charts for usage dashboard
  shimmer: ^3.0.0              # loading skeletons
  flutter_animate: ^4.5.0

  # File handling
  file_picker: ^8.0.0

  # ML
  tflite_flutter: ^0.10.4

  # Utilities
  uuid: ^4.4.0
  intl: ^0.19.0
  share_plus: ^9.0.0           # future CSV export

dev_dependencies:
  flutter_test:
    sdk: flutter
  build_runner: ^2.4.0
  freezed: ^2.5.0
  json_serializable: ^6.8.0
  riverpod_generator: ^2.4.0
  drift_dev: ^2.18.0
  mocktail: ^1.0.0
  flutter_lints: ^4.0.0

flutter:
  uses-material-design: true
  assets:
    - assets/models/usage_classifier.tflite
    - assets/icons/
```

---

## Appendix B — analysis_options.yaml

```yaml
include: package:flutter_lints/flutter.yaml

analyzer:
  errors:
    missing_required_param: error
    missing_return: error
  exclude:
    - "**/*.g.dart"
    - "**/*.freezed.dart"

linter:
  rules:
    - prefer_const_constructors
    - prefer_final_fields
    - avoid_print
    - cancel_subscriptions
    - close_sinks
    - avoid_slow_async_io
```

---

## Appendix C — Android Manifest Skeleton

```xml
<!-- android/app/src/main/AndroidManifest.xml -->
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">

  <uses-permission android:name="android.permission.INTERNET"/>
  <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE"/>
  <uses-permission android:name="android.permission.PACKAGE_USAGE_STATS"
      tools:ignore="ProtectedPermissions"/>
  <uses-permission android:name="android.permission.ACCESS_NOTIFICATION_POLICY"/>
  <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW"/>
  <uses-permission android:name="android.permission.FOREGROUND_SERVICE"/>
  <uses-permission android:name="android.permission.FOREGROUND_SERVICE_DATA_SYNC"/>
  <uses-permission android:name="android.permission.RECEIVE_BOOT_COMPLETED"/>

  <application
      android:label="Mnemo"
      android:networkSecurityConfig="@xml/network_security_config"
      android:debuggable="false">

    <activity android:name=".MainActivity" .../>

    <service
        android:name=".UsageMonitorService"
        android:foregroundServiceType="dataSync"
        android:exported="false"/>

    <service
        android:name=".OverlayService"
        android:exported="false"/>

    <receiver
        android:name=".BootCompletedReceiver"
        android:exported="true">
      <intent-filter>
        <action android:name="android.intent.action.BOOT_COMPLETED"/>
      </intent-filter>
    </receiver>

  </application>
</manifest>
```

---

*End of Specification — Mnemo Mobile v1.0.0*
