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

### 6.3 Spaced Review Scheduling

StudyGrid schedules future review sessions based on spaced repetition principles rather than requiring students to manually decide when to review each topic.

### 6.4 Adaptive Schedule

When the student's actual behavior differs from the original schedule, StudyGrid recalculates the remaining plan.

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

## 7. User Journey

StudyGrid supports different student situations rather than assuming every student starts at the beginning of a semester.

The product can be understood through three core operations:
CREATE 
Create a study plan from scratch 
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
#### Trigger:
Student submits their study information.

#### Inputs:

- Course materials
- Exam date
- Available study time
- Subject priority
- Existing schedule / constraints

#### Expected behavior:
StudyGrid creates a schedule containing:

- Initial learning sessions
- Review sessions
- Topic allocation
- Estimated study duration


## 9. AI Component

## 10. MVP Scope

### Must Have
### Should Have
### Could Have

## 11. Prototype Status

## 12. Demo Flow

## 13. Future Development