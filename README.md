# SkillSwap NSU

A student skill-exchange platform for North South University. Students list what
they can teach and what they want to learn; the platform finds two-way matches,
they book a session, and afterwards they rate each other. No money is involved
anywhere in the system.

**CSE311L — Database Systems Lab**

| | |
| --- | --- |
| Live interface (GitHub Pages) | <https://mdroman0.github.io/SkillSwapNSU/> |
| Repository | <https://github.com/MDROMAN0/SkillSwapNSU> |
| Database script to import | `database/skillexchange_full.sql` |
| Demo login | `roman.ahmed01@northsouth.edu` / `password123` |

The GitHub Pages link above is the static preview — it shows every screen with
the real seeded data but cannot write, because Pages serves static files only.
The Flask build in this repository runs the same interface against MySQL for
real; see [Running the Flask build](#running-the-flask-build-the-full-working-version).

---

## Repository layout

```
SkillSwapNSU/
│
├── app.py                  Flask application factory + dev server
├── config.py               Database credentials and app settings
├── db.py                   mysql-connector wrapper: query / execute / transaction
├── helpers.py              Session handling, formatters, shared queries
├── requirements.txt        Flask, mysql-connector-python, Werkzeug
├── 1-IMPORT-DATABASE.bat   One click: import the .sql into XAMPP's MySQL
├── 2-RUN-WEBSITE.bat       One click: install packages and start the server
├── KIVABE-CHALABO.md       Setup guide in Bangla
│
├── routes/                 One blueprint per area of the site
│   ├── auth.py                 sign in, register, sign out
│   ├── main.py                 landing page, dashboard, matching query
│   ├── search.py               parameterised student search
│   ├── profile.py              public profile, edit profile, skills, password
│   ├── exchange.py             exchange requests: send / accept / reject / cancel
│   ├── sessions.py             booking, rescheduling, completing sessions
│   ├── reviews.py              writing and deleting reviews
│   └── admin.py                admin console
│
├── templates/              Jinja templates (the server rendered UI)
│   ├── base.html               shell: top nav, flash toasts, footer
│   ├── macros.html             avatar, pill, stars, swap card, empty state
│   ├── _rail.html              left rail profile card + section nav
│   └── index / login / register / dashboard / search / profile /
│       edit_profile / requests / sessions / reviews / admin / error
│
├── database/
│   ├── schema.sql              Tables, keys, constraints, indexes, views
│   ├── seed.sql                Sample data for every table
│   ├── queries.sql             Demonstration of every required SQL feature
│   └── skillexchange_full.sql  schema + seed in one file (easiest import)
│
├── static/
│   ├── css/style.css       The design system: dark + light tokens, components
│   ├── vendor/             Bootstrap 5.3.3, Bootstrap Icons, Chart.js — all local
│   └── js/
│       ├── app.js          Theme switch, command palette, counters, modals
│       ├── charts.js       Draws the analytics tab from the SQL aggregates
│       ├── data.js         Export of seed.sql, used only by the static preview
│       └── ui.js           Render helpers, used only by the static preview
│
├── uploads/                Profile pictures uploaded through Edit profile
│
└── index.html, login.html, register.html, dashboard.html, search.html,
    profile.html, edit-profile.html, requests.html, sessions.html,
    reviews.html, admin.html
        The STATIC PREVIEW that GitHub Pages serves. Same markup, same data,
        but read from static/js/data.js because Pages cannot run Python.
```

---

## Setting up the database (XAMPP)

1. Start **Apache** and **MySQL** from the XAMPP Control Panel.
2. Open <http://localhost/phpmyadmin>.
3. Go to the **Import** tab.
4. Choose `database/skillexchange_full.sql` and press **Go**.

That one file drops any old copy of the database, recreates all six tables with
their constraints and indexes, creates the three views, and inserts the sample
data. When it finishes you should see:

| table              | rows |
| ------------------ | ---- |
| `users`            | 50   |
| `skills`           | 50   |
| `userskills`       | 261  |
| `exchangerequests` | 49   |
| `sessions`         | 34   |
| `reviews`          | 36   |

Prefer to run the steps separately? Import `database/schema.sql` first, then
`database/seed.sql`. Either way, `database/queries.sql` can be pasted into the
phpMyAdmin **SQL** tab afterwards — every write query in it is wrapped in a
transaction that rolls back, so the sample data is never disturbed.

### Command line alternative

```bash
cd C:\xampp\mysql\bin
mysql -u root < path\to\database\skillexchange_full.sql
```

---

## Running the Flask build (the full, working version)

Everything writes to MySQL here — sign in, send a request, accept it, book a
session, mark it completed, leave a review.

1. Start **MySQL** from the XAMPP Control Panel (Apache is not needed).
2. Import the database — double click **`1-IMPORT-DATABASE.bat`**, or follow
   the phpMyAdmin steps above.
3. Double click **`2-RUN-WEBSITE.bat`**. It installs the three packages on the
   first run and starts the server.
4. Open <http://127.0.0.1:5000>.

Prefer the command line?

```bash
pip install -r requirements.txt
python app.py
```

If the MySQL root user has a password, set it in `config.py` (or in the
`SKILLSWAP_DB_PASSWORD` environment variable).

A Bangla version of these steps is in **`KIVABE-CHALABO.md`**.

### What the interface does beyond the basics

| Feature | What it demonstrates |
| ------- | -------------------- |
| **Dark / light theme** | Two selected palettes on CSS custom properties, remembered in `localStorage` and applied before first paint so nothing flashes. |
| **Command palette** (`Ctrl`/`⌘` + `K`, or `/`) | One JSON endpoint, `/api/search`, running three capped `LIKE` queries — students, skills, departments — with keyboard navigation. |
| **Analytics dashboard** (Admin → Analytics) | Six aggregates charted: supply vs demand per skill, students per department, the exchange funnel, the rating spread, activity per month, and a `GROUP BY … HAVING` leaderboard. Every chart also has a table view. |
| **Sortable, paged tables** | `ORDER BY` and `LIMIT … OFFSET` run in SQL, never in Python. Sort keys go through a whitelist first, because a column name cannot be a bound parameter. |
| **CSV export** | Five downloads, two of them straight off the `v_request_details` and `v_session_overview` views. |
| **Debounced live search** | The Find page re-runs its query 500 ms after you stop typing, so one name is one round trip. |

### Chart colours

The chart palette is not decorative. Series colours were checked with a
palette validator against the exact surfaces they render on — `#151B2E` in
dark, `#FFFFFF` in light — for lightness band, chroma, colour-blind
separation, normal-vision separation and contrast. Nominal categories
(departments) get one hue; ordered scales (the funnel, 1–5 ratings) get one
hue stepped light to dark; only genuine series (teach vs learn, the three
activity lines) use the categorical slots. No chart has two y-axes.

### Seeing the SQL as it runs

Every write action shows a toast in the bottom right corner naming the exact
statement that just executed — `INSERT INTO exchangerequests ...`,
`UPDATE sessions SET status = 'Completed' ...`, and so on. Constraint
violations are reported the same way, so blocking a duplicate review names
`UNIQUE (session_id, reviewer_id)` on screen. Turn it off with
`SHOW_SQL_TOASTS = False` in `config.py`.

## Viewing the static preview

The eleven HTML files in the repository root are a server-free copy of the same
interface, which is what the GitHub Pages link serves. Open `index.html`
directly, or serve the folder:

```bash
python -m http.server 8000
# then open http://localhost:8000
```

### Demo account

Every seeded student shares the same password so any account can be used to look
around.

| Field    | Value                          |
| -------- | ------------------------------ |
| Email    | `roman.ahmed01@northsouth.edu` |
| Password | `password123`                  |

The **Fill demo credentials** button on the sign-in page enters them for you.

> **Why the preview is read-only.** GitHub Pages serves static files only; it
> cannot run Python. The preview therefore reads the seeded rows from
> `static/js/data.js`, a direct export of `seed.sql`, so the screens show exactly
> the records that live in MySQL. Buttons that would write to the database name
> the SQL statement they stand for instead of executing it. The Flask build in
> this same repository renders the identical markup from Jinja templates and runs
> those statements for real against MySQL on XAMPP.

---

## Database design

Six tables, normalised to 3NF.

```
users ──< userskills >── skills
  │                        │
  │  sender / receiver     │  teach_skill / learn_skill
  └──────< exchangerequests >──────┘
                  │
                  └──< sessions ──< reviews >── users
```

### Data dictionary

**users** — one row per student

| Column            | Type         | Notes                                     |
| ----------------- | ------------ | ----------------------------------------- |
| `user_id`         | INT          | PK, AUTO_INCREMENT                        |
| `name`            | VARCHAR(100) | NOT NULL                                  |
| `email`           | VARCHAR(255) | NOT NULL, **UNIQUE** — this is the login   |
| `password`        | VARCHAR(255) | Werkzeug pbkdf2 hash, never plain text    |
| `department`      | VARCHAR(100) | NOT NULL, indexed for department search   |
| `bio`             | VARCHAR(255) | Optional                                  |
| `profile_picture` | VARCHAR(255) | Filename, defaults to `default.png`       |
| `created_at`      | TIMESTAMP    | Defaults to the current time              |

**skills** — the catalogue students choose from

| Column        | Type         | Notes                        |
| ------------- | ------------ | ---------------------------- |
| `skill_id`    | INT          | PK, AUTO_INCREMENT           |
| `skill_name`  | VARCHAR(100) | NOT NULL, **UNIQUE**         |
| `category`    | VARCHAR(50)  | NOT NULL, indexed            |
| `description` | VARCHAR(255) | One line explaining the skill |

**userskills** — bridge table resolving the many-to-many between students and skills

| Column          | Type | Notes                                                  |
| --------------- | ---- | ------------------------------------------------------ |
| `user_skill_id` | INT  | PK, AUTO_INCREMENT                                     |
| `user_id`       | INT  | FK → `users`, ON DELETE CASCADE                        |
| `skill_id`      | INT  | FK → `skills`, ON DELETE CASCADE                       |
| `skill_type`    | ENUM | `Teach` or `Learn`                                     |
| `proficiency`   | ENUM | `Beginner` / `Intermediate` / `Advanced` / `Expert`    |

UNIQUE `(user_id, skill_id, skill_type)` stops a student listing the same skill
twice under the same type.

**exchangerequests** — one proposed trade

| Column        | Type      | Notes                                                             |
| ------------- | --------- | ----------------------------------------------------------------- |
| `request_id`  | INT       | PK, AUTO_INCREMENT                                                |
| `sender_id`   | INT       | FK → `users`                                                      |
| `receiver_id` | INT       | FK → `users`                                                      |
| `teach_skill` | INT       | FK → `skills` — what the sender offers                            |
| `learn_skill` | INT       | FK → `skills` — what the sender wants                             |
| `status`      | ENUM      | `Pending` / `Accepted` / `Rejected` / `Cancelled` / `Completed`   |
| `created_at`  | TIMESTAMP | Defaults to the current time                                      |

CHECK `sender_id <> receiver_id` and CHECK `teach_skill <> learn_skill`.

**sessions** — a booked meeting belonging to one request

| Column         | Type         | Notes                                             |
| -------------- | ------------ | ------------------------------------------------- |
| `session_id`   | INT          | PK, AUTO_INCREMENT                                |
| `request_id`   | INT          | FK → `exchangerequests`, ON DELETE CASCADE        |
| `session_date` | DATE         | NOT NULL                                          |
| `session_time` | TIME         | NOT NULL                                          |
| `duration`     | INT          | Minutes, CHECK between 15 and 480, defaults to 60 |
| `mode`         | ENUM         | `Online` or `Offline`                             |
| `location`     | VARCHAR(255) | Used when the mode is Offline                     |
| `meeting_link` | VARCHAR(255) | Used when the mode is Online                      |
| `status`       | ENUM         | `Scheduled` / `Completed` / `Cancelled`           |
| `created_at`   | TIMESTAMP    | Defaults to the current time                      |

UNIQUE `(request_id, session_date, session_time)` prevents double booking the
same slot.

**reviews** — feedback after a completed session

| Column        | Type         | Notes                                      |
| ------------- | ------------ | ------------------------------------------ |
| `review_id`   | INT          | PK, AUTO_INCREMENT                         |
| `session_id`  | INT          | FK → `sessions`, ON DELETE CASCADE         |
| `reviewer_id` | INT          | FK → `users` — who wrote it                |
| `reviewee_id` | INT          | FK → `users` — who it is about             |
| `rating`      | INT          | CHECK between 1 and 5                      |
| `comment`     | VARCHAR(200) | Optional                                   |
| `created_at`  | TIMESTAMP    | Defaults to the current time               |

UNIQUE `(session_id, reviewer_id)` enforces one review per person per session,
so both partners may review each other but neither can review twice. CHECK
`reviewer_id <> reviewee_id` blocks self-reviews.

### Referential rules

- **ON DELETE CASCADE** — rows that are meaningless without their parent (a
  student's skills, requests, sessions and reviews) are removed automatically.
- **ON DELETE RESTRICT** — a skill cannot be deleted while an exchange request
  still points at it.
- **ON UPDATE RESTRICT** — every primary key is a surrogate AUTO_INCREMENT value
  that is never edited, so cascading updates are unnecessary. MariaDB also
  refuses CHECK constraints on columns that use ON UPDATE CASCADE, and the CHECK
  constraints are worth more here.

### Views

| View                 | Purpose                                                        |
| -------------------- | -------------------------------------------------------------- |
| `v_user_ratings`     | Review count and average rating per student                    |
| `v_request_details`  | Requests with IDs replaced by readable names and skill names   |
| `v_session_overview` | Sessions with both partner names and the skill being taught    |

### Normalisation

- **1NF** — every column holds a single atomic value. A student teaching three
  skills produces three rows in `userskills`, not a comma-separated list.
- **2NF** — no partial dependency exists, because every table has a single-column
  surrogate primary key. Skill details live in `skills` rather than being
  repeated on each `userskills` row.
- **3NF** — no transitive dependency. `skills.category` depends on `skill_id`
  only; a student's average rating is not stored on `users` but derived from
  `reviews` through the `v_user_ratings` view.

---

## SQL features demonstrated

All of these live in `database/queries.sql`, grouped and numbered.

| Feature                             | Where             |
| ----------------------------------- | ----------------- |
| SELECT, WHERE, LIKE, ORDER BY, LIMIT | A1 – A3           |
| INNER JOIN (up to five tables)      | B1 – B3           |
| LEFT JOIN                           | C1, C2            |
| RIGHT JOIN                          | C3                |
| GROUP BY                            | D1 – D6           |
| HAVING                              | D3, D4            |
| COUNT, SUM, AVG, MIN, MAX           | D2                |
| Scalar, IN, NOT EXISTS, correlated, derived-table and ALL subqueries | E1 – E6 |
| Parameterised search queries used by the UI | F1 – F3   |
| Views                               | G1 – G3           |
| Indexes, including EXPLAIN proof    | H1 – H3           |
| INSERT                              | I1                |
| UPDATE                              | I2, I3            |
| DELETE with cascade                 | I4                |
| Transactions (START TRANSACTION / COMMIT / ROLLBACK) | I1 – I5 |
| Reporting queries for the dashboard | J1 – J3           |

---

## Stack

| Layer          | Technology                             |
| -------------- | -------------------------------------- |
| Frontend       | HTML5, CSS3, Bootstrap 5.3, vanilla JS |
| Charts         | Chart.js 4, vendored locally           |
| Backend        | Python 3, Flask with Blueprints        |
| Database       | MySQL on XAMPP                         |
| DB driver      | `mysql-connector-python`, raw SQL only |
| Authentication | Flask sessions, Werkzeug hashing       |

No ORM is used anywhere. Every query is written by hand and parameterised, which
is both the point of a Database Systems Lab project and the defence against SQL
injection.

---

## Team

| Name | NSU ID | Responsibility |
| ---- | ------ | -------------- |
|      |        |                |
|      |        |                |
|      |        |                |
|      |        |                |
