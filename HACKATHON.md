# Project Name: StudyGrid

## 1. One-liner: 
An AI-powered study and review planner that helps students turn their course materials and available time into an adaptive study schedule using spaced repetition. 

## 2. Problem
University students need to learn and retain a large amount of knowledge across multiple subjects, often within limited time before exams.

However, there are two major problems:


### 2.1 Ineffective Study Methods

Students often rely on methods such as highlighting, rereading, or passively reviewing materials. These approaches can create a sense of familiarity without necessarily supporting strong long-term retention.

More effective learning techniques, such as retrieval practice and spaced practice, require students to deliberately plan when and how they should review information.

### 2.2 Difficult and Rigid Study Planning

Creating an effective study plan manually requires students to:

- Read through materials from multiple subjects
- Break materials into manageable topics
- Estimate how much time each topic requires
- Decide when each topic should be reviewed
- Balance different subjects according to their priorities
- Adjust the plan when their actual progress differs from the original schedule

A schedule that looks optimal on paper can quickly become unrealistic when a student misses a session, needs more time on a difficult topic, or has a change in available study time.

Core Problem: Students need an effective way to plan not only what to study, but also when to review it — while keeping the schedule flexible enough to adapt to real-life study behavior.

## 3. Target Users
Primary Users: College and university students who:
- Study multiple subjects simultaneously
- Have a large volume of course material
- Have limited or changing study time
- Need to prepare for multiple exams or assessments
- Struggle to maintain a manually created study schedule

## 4. Current Solutions / Existing Problems

### Traditional Planning

Students commonly use:

- To-do lists
- Paper planners
- Google Calendar
- Notion
- Generic scheduling apps

Problem: These tools help students organize time, but generally require students to decide for themselves what to study and when to review it.

### AI Chatbots

Students can ask AI tools to:

- Summarize materials
- Generate study plans
- Create quizzes
- Explain concepts

Problem: The interaction is often session-based rather than a persistent, structured study system. Students still need to manually organize the generated information into a schedule and maintain it over time.

### Spaced-Repetition Tools

Tools such as flashcard applications can support spaced review.

Problem: Students usually need to manually create or organize learning content and manage what should be reviewed.

### The Gap: 
Existing tools tend to solve planning, content generation, or review separately.

## 5. Our Solution
StudyGrid transforms a student's learning materials, exam deadlines, available study time, and priorities into a personalized study and review schedule. 

### Basic Workflow 


## 6. Core Features
### 6.1 AI Material Analysis

Students provide their course materials.

StudyGrid analyzes the material and identifies:
- Main topics
- Subtopics
- Relationships between concepts
- Estimated difficulty / learning effort

### 6.2 Personalized Study Plan

The student provides:

- Exam date
- Available study time (Amount of time in one semester)
- Current fixed schedule
- Subjects
- Subject priorities
- Other learning preferences

Availability is entered as hours for each day. The weekly total is derived for
visibility, not entered as a separate target. A non-zero day shorter than the
selected session duration cannot host that session and is reported clearly in
the intake rather than silently treated as usable time.

Study sessions use 30, 60, 90, or 120-minute presets, with a custom-duration
mode when needed. The default is 60 minutes. Every completed session reserves a
short recovery equal to 10% of its duration, rounded up to a whole minute.
After approximately four cumulative study hours in a day, the short recovery
is replaced by a longer break: 45 minutes by default, configurable by the
student from 30 to 180 minutes. These breaks consume clock time but do not count
toward the student's daily study-minute budget.

### 6.3 Spaced Review Scheduling

StudyGrid schedules future review sessions based on spaced repetition principles rather than requiring students to manually decide when to review each topic.

The initial calendar uses expanding review offsets such as 1, 3, 7, 14, 30,
and 60 days as provisional placeholders, adjusted for topic difficulty and the
time remaining before the exam. This sequence is a practical starting policy,
not a universal claim about an optimal interval.

Each logged retrieval recalculates the next review:

- Poor recall targets the next day.
- Difficult or partial recall targets about three days.
- Strong recall expands through 7, 14, 30, 60, and 120 days across successful
  spaced reviews.
- No review may be placed on or after the exam; a longer interval is compressed
  to the final study day when possible.

Future review sessions remain provisional. StudyGrid can move or prune them as
recall evidence arrives, while still respecting availability, fixed
commitments, daily study limits, and the exam deadline.

StudyGrid also uses controlled interleaving across subjects. Explicit subject
priority and exam urgency determine how frequently each subject receives a
slot. When multiple subjects still have ready work, no subject receives more
than two consecutive sessions. This prevents long monotonous blocks without
randomizing the plan: topic input order and prerequisite relationships remain
intact inside each subject.

### 6.4 Adaptive Schedule

When the student's actual behavior differs from the original schedule, StudyGrid recalculates the remaining plan.

### 6.5 Time-Use Insights

Completed sessions sync into an owner-scoped time log. Students can also record
work, entertainment, illness, unexpected events, rest, or a custom label.
Progress shows real 7/30-day stacked charts alongside missed-session reasons,
so the planner explains both scheduled study and the rest of the week.

### 6.6 Progress Tracking

Students can mark sessions/topics as:

- Completed
- Partially completed
- Not completed

and how the sessions/ topic are done:

- Well done (Mostly recall the material)
- Medium (Recall about 50% of the material)
- Poorly done (Recall very little to no information)

This information can be used to update future scheduling.

### 6.7 Plan-Aware Study Coach

Students can ask a chatbot about their current plan, including what to study
next, how much work remains, why a session was placed where it is, and how to
recover after falling behind. The coach receives the persisted plan, recent
conversation turns, and the currently selected session when applicable.

The coach is advisory and cannot mutate calendar timestamps. Schedule changes
still require explicit progress input and pass through the deterministic
scheduler. Provider failures use a deterministic, plan-aware fallback so the
chat remains useful during a demo without network access.

## 7. User Journey

StudyGrid supports different student situations rather than assuming every student starts at the beginning of a semester.

The product can be understood through three core operations:
CREATE 
Create a study plan from inputs from users 
    ↓
OPTIMIZE 
Improve an existing plan for a new goal 
    ↓ 
ADAPT 
Re-optimize the plan when circumstances change

### User Entry Point 1: Fresh start of new semester 

Student situation: Student has no study plan yet.

Goal: Generates a study + review schedule from materials, deadlines, available time, and priorities.

### User Entry Point 2: Mid-Semester: Make the Most of the Remaining Time
Student situation: The semester is already halfway through and students has already made progress on certain aspects. 
Goal: Generate a revised study roadmap optimized for the student's remaining time.

### User Entry Point 3: Exam-Rusher
Student situation: An exam is approaching soon and the student has a large amount of material remaining. 

Goal: Generate a focused exam-preparation plan that maximizes learning within the remaining time.

## 8. Product Logic & User Scenarios

### 8.1 Initial Study Plan Generation

#### Situation:
Students create study plan. 

Example: 
- Students create study plan for new semester 
- Students half way through the semester want to optimize current schedule 
- Students preparing for the examination 

#### Inputs:

- Course materials
- Exam date
- Available study time
- Subject priority
- Existing schedule / constraints

#### What StudyGrid do: 
StudyGrid creates a schedule containing:

- Initial learning sessions
- Review sessions
- Topic allocation
- Estimated study duration

### 8.2 Respond to Changes

#### Situation: 
Students don't finished studying task according to plan 

#### Examples:

- Missed study session
- Student progresses faster or slower than expected

#### What StudyGrid do: 
- Mark the session as incomplete.
- Identify the unfinished topic.
- Check remaining available study time.
- Check the upcoming exam deadline.
- Reassess the topic's priority.
- Find appropriate future time slots.
- Reschedule the unfinished work.
- Adjust affected review sessions if necessary.

#### Output:
An updated plan that fits the student's current situation.

### 8.3 Understand Where Study Time Goes

#### Situation:
When a study session is not completed, StudyGrid asks for a quick reason, such as: Club meeting · Exercise · Social activity · Rest · Mood · Emergency

#### What StudyGrid do:
Aggregates this information over time to identify patterns in how the student actually uses their time.

#### Output:
Weekly/monthly insight dashboard showing:

- Where their time goes
- What activities frequently affect study time
- Changes in study habits
- Potential areas for better balance
- Suggestions for the coming weeks

## 9. AI Component

StudyGrid uses AI for two bounded tasks: turning pasted syllabus text into a
validated list of topics, and answering read-only Study Coach questions using
the student's current plan as context. AI never creates or changes calendar
timestamps. A deterministic scheduler places and adapts sessions so they cannot
overlap fixed commitments or extend beyond an exam deadline.

The model provider is isolated behind an `LLMProvider` interface. The MVP uses
the OpenAI Responses API with Pydantic Structured Outputs, and validates every
result against the shared `Topic` model before it reaches the scheduler.

If the API key is missing, the request times out, the provider is unavailable,
or its response is invalid, StudyGrid uses deterministic fallbacks: topic
extraction for course material and plan-derived answers for common coach
questions. Responses report `source: "ai"` or `source: "fallback"` so the UI
can explain which path was used. This keeps the live demo functional without
hiding provider failures.

## 10. MVP Scope

### Must Have
- Paste or upload material and extract editable topics with a visible AI/fallback source.
- Generate a conflict-free study calendar from deadlines and weekly capacity.
- Distinguish first passes from spaced reviews.
- Log completion and recall, then explain every schedule adaptation.
- Keep the complete demo usable when the model provider is unavailable.
- Persist public user-test plans and isolate them by anonymous browser session.
- Show owner-scoped Progress charts from real study and activity logs.

### Should Have
- Custom plan start, daily study window, capacity, and fixed commitments.
- Plan-aware Study Coach with bounded, plan-scoped history.
- Time-use insights based on an append-only outcome history.
- Responsive light/dark UI with keyboard and WCAG checks.

### Could Have
- Named accounts and cross-device plan recovery.
- A concept relationship graph and richer recall exercises.

## 11. Prototype Status

The end-to-end prototype is complete for supervised demos and user testing.
Backend smoke tests cover analysis, scheduler invariants, coach grounding,
adaptation, and insights. The Svelte app passes type checks and production
builds. Playwright covers the complete judge flow, phone layout, dark mode,
keyboard dismissal, field labels, and automated WCAG A/AA checks.

The public user-test deployment uses SQLite and a signed HttpOnly anonymous
session cookie. Plans survive server restarts and are isolated between browser
sessions. There are still no named accounts or cross-device recovery, so
testers must not enter private information and should use the in-product data
deletion control when finished.

## 12. Demo Flow

1. Open the empty calendar and choose **Create study plan**.
2. Set the planning date, daily window, available hours, and commitments.
3. Upload DOCX/TXT/MD/PDF or paste notes, run material analysis, and point out the visible
   OpenAI or offline-fallback source.
4. Generate the calendar and show the first-pass/review distinction.
5. Ask Study Coach what to study next.
6. Open a session, report poor recall, and show what moved and why.
7. Open Progress, log unexpected work, and show the 7/30-day category chart.
8. Report a missed session with a reason and show the time-use insight.
9. Create an intentionally over-capacity custom window and show the honest
   warning for material that cannot fit.

## 13. Future Development

- Add named accounts and optional cross-device plan recovery if testing shows a
  real need beyond anonymous sessions.
- Add timezone-aware calendars and multi-device synchronization.
- Add source-linked excerpts and OCR for image-only PDFs.
- Calibrate spacing policies with longitudinal learner outcomes.
- Add privacy controls, retention settings, and production observability.
