"""
eval/prompts.py
---------------
The 20 evaluation prompts used by eval/runner.py.

REAL_PROMPTS  — 10 realistic product descriptions
EDGE_PROMPTS  — 10 edge cases (vague, incomplete, conflicting, etc.)

Do not edit prompt text — ids and exact strings are referenced in reports.
"""

from __future__ import annotations

REAL_PROMPTS: list[dict] = [
    {
        "id": "crm_01",
        "category": "real",
        "prompt": (
            "Build a CRM where admins manage contacts (name, email, phone, company) "
            "and sales reps view and update their assigned contacts. Include activity logging."
        ),
    },
    {
        "id": "todo_01",
        "category": "real",
        "prompt": (
            "A simple personal todo list app. Users can create tasks with titles, "
            "due dates, and priority levels. Tasks can be marked complete or deleted."
        ),
    },
    {
        "id": "ecommerce_01",
        "category": "real",
        "prompt": (
            "An e-commerce platform where customers browse products, add to cart, "
            "and checkout. Admins manage inventory and view orders. Support discount codes."
        ),
    },
    {
        "id": "blog_01",
        "category": "real",
        "prompt": (
            "A blogging platform where authors can write and publish posts with tags "
            "and categories. Readers can comment and like posts. Admins moderate comments."
        ),
    },
    {
        "id": "lms_01",
        "category": "real",
        "prompt": (
            "A learning management system where instructors create courses with video "
            "lessons and quizzes. Students enroll, track progress, and earn certificates."
        ),
    },
    {
        "id": "hr_01",
        "category": "real",
        "prompt": (
            "An HR portal where employees submit leave requests and view payslips. "
            "Managers approve requests. HR admins manage employee records and run reports."
        ),
    },
    {
        "id": "inventory_01",
        "category": "real",
        "prompt": (
            "An inventory management system for a warehouse. Staff scan items in/out. "
            "Managers get low-stock alerts and can generate purchase orders."
        ),
    },
    {
        "id": "booking_01",
        "category": "real",
        "prompt": (
            "A room booking system for an office. Employees reserve meeting rooms by "
            "time slot. Admins see utilisation reports and manage room configurations."
        ),
    },
    {
        "id": "finance_01",
        "category": "real",
        "prompt": (
            "A personal finance tracker where users log income and expenses by category, "
            "set monthly budgets, and view spending charts. Premium users get export to CSV."
        ),
    },
    {
        "id": "saas_01",
        "category": "real",
        "prompt": (
            "A multi-tenant SaaS analytics dashboard. Each company has its own workspace. "
            "Admins invite team members, connect data sources, and view charts. "
            "Billing is per seat."
        ),
    },
]

EDGE_PROMPTS: list[dict] = [
    {
        "id": "edge_01",
        "category": "edge",
        "edge_type": "vague",
        "prompt": "Build me an app.",
    },
    {
        "id": "edge_02",
        "category": "edge",
        "edge_type": "vague",
        "prompt": "I need something for my business.",
    },
    {
        "id": "edge_03",
        "category": "edge",
        "edge_type": "incomplete",
        "prompt": "A dashboard with charts and login.",
    },
    {
        "id": "edge_04",
        "category": "edge",
        "edge_type": "incomplete",
        "prompt": "Users should be able to manage their stuff.",
    },
    {
        "id": "edge_05",
        "category": "edge",
        "edge_type": "conflicting",
        "prompt": (
            "All users are both admins and regular users at the same time. "
            "Admins can see everything but regular users also see everything."
        ),
    },
    {
        "id": "edge_06",
        "category": "edge",
        "edge_type": "conflicting",
        "prompt": (
            "The app has no database but users need to save and retrieve "
            "their data between sessions."
        ),
    },
    {
        "id": "edge_07",
        "category": "edge",
        "edge_type": "ambiguous_roles",
        "prompt": (
            "There are managers and employees but managers are also employees "
            "and can do everything employees can plus more."
        ),
    },
    {
        "id": "edge_08",
        "category": "edge",
        "edge_type": "overspecified",
        "prompt": (
            "Build a CRM with 47 custom fields per contact, 12 user roles with "
            "different permissions for each of 200 specific actions, webhook integrations "
            "to 15 external services, and real-time collaboration with conflict resolution."
        ),
    },
    {
        "id": "edge_09",
        "category": "edge",
        "edge_type": "contradictory",
        "prompt": (
            "The app must be completely offline but also sync in real-time across all devices."
        ),
    },
    {
        "id": "edge_10",
        "category": "edge",
        "edge_type": "minimal",
        "prompt": "Todo app.",
    },
]

ALL_PROMPTS: list[dict] = REAL_PROMPTS + EDGE_PROMPTS
