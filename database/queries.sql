-- =============================================================
--  SkillSwap NSU  —  CSE311L Database Systems Lab
--  File   : queries.sql
--  Purpose: Demonstration of every SQL feature required by the lab.
--           Safe to run any number of times — the write queries at
--           the end run inside transactions that are ROLLED BACK.
-- =============================================================

USE `skillexchange`;

-- =============================================================
--  A. SIMPLE SELECT / WHERE / ORDER BY / LIMIT
-- =============================================================

-- A1. All students of the CSE department, newest first
SELECT user_id, name, email, department
FROM   users
WHERE  department = 'CSE'
ORDER  BY created_at DESC;

-- A2. Skills whose name starts with 'P' (pattern matching)
SELECT skill_id, skill_name, category
FROM   skills
WHERE  skill_name LIKE 'P%'
ORDER  BY skill_name;

-- A3. Top 10 longest sessions (ORDER BY + LIMIT)
SELECT session_id, session_date, session_time, duration, mode
FROM   sessions
ORDER  BY duration DESC, session_date DESC
LIMIT  10;

-- =============================================================
--  B. INNER JOIN
-- =============================================================

-- B1. Every skill a student can teach, with proficiency
SELECT u.name, s.skill_name, s.category, us.proficiency
FROM        userskills us
INNER JOIN  users  u ON u.user_id  = us.user_id
INNER JOIN  skills s ON s.skill_id = us.skill_id
WHERE       us.skill_type = 'Teach'
ORDER  BY   u.name, s.skill_name
LIMIT  20;

-- B2. Readable exchange request list (4-table join)
SELECT er.request_id,
       sender.name   AS sender,
       receiver.name AS receiver,
       offered.skill_name   AS offers,
       wanted.skill_name    AS wants,
       er.status
FROM        exchangerequests er
INNER JOIN  users  sender   ON sender.user_id   = er.sender_id
INNER JOIN  users  receiver ON receiver.user_id = er.receiver_id
INNER JOIN  skills offered  ON offered.skill_id = er.teach_skill
INNER JOIN  skills wanted   ON wanted.skill_id  = er.learn_skill
ORDER  BY   er.created_at DESC
LIMIT  15;

-- B3. Completed sessions with both partner names and the skill taught
SELECT se.session_id, se.session_date, se.duration,
       t.name AS teacher, l.name AS learner, sk.skill_name
FROM        sessions se
INNER JOIN  exchangerequests er ON er.request_id = se.request_id
INNER JOIN  users  t  ON t.user_id  = er.sender_id
INNER JOIN  users  l  ON l.user_id  = er.receiver_id
INNER JOIN  skills sk ON sk.skill_id = er.teach_skill
WHERE       se.status = 'Completed'
ORDER  BY   se.session_date DESC;

-- =============================================================
--  C. LEFT JOIN  /  RIGHT JOIN
-- =============================================================

-- C1. LEFT JOIN — every student, even those who received no review yet
SELECT u.user_id, u.name, u.department,
       COUNT(r.review_id)      AS reviews_received,
       IFNULL(ROUND(AVG(r.rating),2), 0) AS avg_rating
FROM        users   u
LEFT JOIN   reviews r ON r.reviewee_id = u.user_id
GROUP  BY   u.user_id, u.name, u.department
ORDER  BY   avg_rating DESC, reviews_received DESC
LIMIT  20;

-- C2. LEFT JOIN — skills nobody has picked up yet (unused skills)
SELECT s.skill_id, s.skill_name, s.category
FROM        skills     s
LEFT JOIN   userskills us ON us.skill_id = s.skill_id
WHERE       us.user_skill_id IS NULL;

-- C3. RIGHT JOIN — every skill in the catalogue with how many students teach it
SELECT s.skill_name, s.category, COUNT(us.user_skill_id) AS teachers
FROM        userskills us
RIGHT JOIN  skills     s ON s.skill_id = us.skill_id AND us.skill_type = 'Teach'
GROUP  BY   s.skill_id, s.skill_name, s.category
ORDER  BY   teachers DESC, s.skill_name
LIMIT  20;

-- =============================================================
--  D. GROUP BY / HAVING / AGGREGATE FUNCTIONS
--     COUNT, SUM, AVG, MIN, MAX
-- =============================================================

-- D1. Students per department
SELECT department, COUNT(*) AS total_students
FROM   users
GROUP  BY department
ORDER  BY total_students DESC;

-- D2. Full aggregate summary of session durations by mode
SELECT mode,
       COUNT(*)             AS total_sessions,
       SUM(duration)        AS total_minutes,
       ROUND(AVG(duration)) AS avg_minutes,
       MIN(duration)        AS shortest,
       MAX(duration)        AS longest
FROM   sessions
GROUP  BY mode;

-- D3. HAVING — skill categories that have more than 3 skills
SELECT category, COUNT(*) AS skills_in_category
FROM   skills
GROUP  BY category
HAVING COUNT(*) > 3
ORDER  BY skills_in_category DESC;

-- D4. HAVING — students rated 4.5 or above with at least 2 reviews
SELECT u.name, u.department,
       COUNT(r.review_id)      AS total_reviews,
       ROUND(AVG(r.rating), 2) AS avg_rating
FROM        reviews r
INNER JOIN  users   u ON u.user_id = r.reviewee_id
GROUP  BY   u.user_id, u.name, u.department
HAVING      COUNT(r.review_id) >= 2 AND AVG(r.rating) >= 4.5
ORDER  BY   avg_rating DESC, total_reviews DESC;

-- D5. Request pipeline — how many requests sit in each status
SELECT status, COUNT(*) AS total,
       ROUND(100 * COUNT(*) / (SELECT COUNT(*) FROM exchangerequests), 1) AS percentage
FROM   exchangerequests
GROUP  BY status
ORDER  BY total DESC;

-- D6. Total teaching minutes delivered by each student (SUM over a join)
SELECT u.name, COUNT(se.session_id) AS sessions_taught,
       SUM(se.duration) AS total_minutes_taught
FROM        sessions se
INNER JOIN  exchangerequests er ON er.request_id = se.request_id
INNER JOIN  users u ON u.user_id = er.sender_id
WHERE       se.status = 'Completed'
GROUP  BY   u.user_id, u.name
ORDER  BY   total_minutes_taught DESC
LIMIT  10;

-- =============================================================
--  E. NESTED / SUB QUERIES
-- =============================================================

-- E1. Scalar subquery — students who joined before the average join date
SELECT name, department, created_at
FROM   users
WHERE  created_at < (SELECT AVG(created_at) FROM users)
ORDER  BY created_at
LIMIT  10;

-- E2. IN subquery — students who teach a Programming skill
SELECT DISTINCT u.user_id, u.name, u.department
FROM        users u
INNER JOIN  userskills us ON us.user_id = u.user_id AND us.skill_type = 'Teach'
WHERE       us.skill_id IN (SELECT skill_id FROM skills WHERE category = 'Programming')
ORDER  BY   u.name
LIMIT  15;

-- E3. NOT EXISTS — students who have never sent a single request
SELECT u.user_id, u.name, u.department
FROM   users u
WHERE  NOT EXISTS (SELECT 1 FROM exchangerequests er WHERE er.sender_id = u.user_id)
ORDER  BY u.name
LIMIT  15;

-- E4. Correlated subquery — each student with their own best rating
SELECT u.name,
       (SELECT MAX(r.rating) FROM reviews r WHERE r.reviewee_id = u.user_id) AS best_rating,
       (SELECT COUNT(*)      FROM reviews r WHERE r.reviewee_id = u.user_id) AS review_count
FROM   users u
WHERE  EXISTS (SELECT 1 FROM reviews r WHERE r.reviewee_id = u.user_id)
ORDER  BY best_rating DESC, review_count DESC
LIMIT  15;

-- E5. Derived table (subquery in FROM) — the single most demanded skill
SELECT skill_name, learners
FROM (
    SELECT s.skill_name, COUNT(*) AS learners
    FROM        userskills us
    INNER JOIN  skills s ON s.skill_id = us.skill_id
    WHERE       us.skill_type = 'Learn'
    GROUP  BY   s.skill_id, s.skill_name
) AS demand
ORDER  BY learners DESC
LIMIT  5;

-- E6. Subquery with ALL — the longest session(s) in the whole system
SELECT session_id, session_date, duration
FROM   sessions
WHERE  duration >= ALL (SELECT duration FROM sessions);

-- =============================================================
--  F. SEARCH QUERIES USED BY THE WEB UI
-- =============================================================

-- F1. Search by skill name (find teachers of a given skill)
SELECT u.user_id, u.name, u.department, us.proficiency
FROM        userskills us
INNER JOIN  users  u ON u.user_id  = us.user_id
INNER JOIN  skills s ON s.skill_id = us.skill_id
WHERE       us.skill_type = 'Teach' AND s.skill_name LIKE '%Python%'
ORDER  BY   FIELD(us.proficiency,'Expert','Advanced','Intermediate','Beginner');

-- F2. Combined search: skill + department + proficiency (the real UI filter)
SELECT DISTINCT u.user_id, u.name, u.department, s.skill_name, us.proficiency
FROM        users u
INNER JOIN  userskills us ON us.user_id  = u.user_id AND us.skill_type = 'Teach'
INNER JOIN  skills     s  ON s.skill_id  = us.skill_id
WHERE       s.category    = 'Design'
  AND       u.department  = 'CSE'
  AND       us.proficiency IN ('Advanced','Expert')
ORDER  BY   u.name;

-- F3. Search by student name
SELECT user_id, name, department, bio
FROM   users
WHERE  name LIKE '%Rahman%'
ORDER  BY name;

-- =============================================================
--  G. VIEWS  (created in schema.sql, queried here)
-- =============================================================

-- G1. Top rated students from the view
SELECT * FROM v_user_ratings
WHERE  total_reviews > 0
ORDER  BY avg_rating DESC, total_reviews DESC
LIMIT  10;

-- G2. Pending requests from the view
SELECT * FROM v_request_details WHERE status = 'Pending' ORDER BY created_at DESC;

-- G3. Upcoming sessions from the view
SELECT * FROM v_session_overview
WHERE  status = 'Scheduled'
ORDER  BY session_date, session_time;

-- =============================================================
--  H. INDEXES
-- =============================================================

-- H1. List every index on every table
SELECT TABLE_NAME, INDEX_NAME, COLUMN_NAME, NON_UNIQUE
FROM   INFORMATION_SCHEMA.STATISTICS
WHERE  TABLE_SCHEMA = 'skillexchange'
ORDER  BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX;

-- H2. Proof that the index is used (look for idx_users_department in the plan)
EXPLAIN SELECT * FROM users WHERE department = 'CSE';

-- H3. Proof for the status index on exchangerequests
EXPLAIN SELECT * FROM exchangerequests WHERE status = 'Pending';

-- =============================================================
--  I. INSERT / UPDATE / DELETE  +  TRANSACTIONS
--     Every block below is rolled back, so the sample data
--     stays exactly as seeded. Change ROLLBACK to COMMIT to keep it.
-- =============================================================

-- I1. INSERT — register a new student and give him two skills
START TRANSACTION;

INSERT INTO users (name, email, password, department, bio)
VALUES ('Demo Student', 'demo.student99@northsouth.edu',
        'pbkdf2:sha256:260000$demoSaltDemo$0000000000000000000000000000000000000000000000000000000000000000',
        'CSE', 'Temporary row used to demonstrate INSERT.');

SET @new_user = LAST_INSERT_ID();

INSERT INTO userskills (user_id, skill_id, skill_type, proficiency) VALUES
  (@new_user, 2, 'Teach', 'Advanced'),
  (@new_user, 39, 'Learn', 'Beginner');

SELECT u.name, s.skill_name, us.skill_type, us.proficiency
FROM        userskills us
INNER JOIN  users  u ON u.user_id  = us.user_id
INNER JOIN  skills s ON s.skill_id = us.skill_id
WHERE       us.user_id = @new_user;

ROLLBACK;

-- I2. UPDATE — accept a pending request, then schedule a session for it
START TRANSACTION;

SELECT request_id INTO @req
FROM   exchangerequests WHERE status = 'Pending' ORDER BY request_id LIMIT 1;

UPDATE exchangerequests SET status = 'Accepted' WHERE request_id = @req;

INSERT INTO sessions (request_id, session_date, session_time, duration, mode, meeting_link)
VALUES (@req, '2026-08-10', '16:00:00', 90, 'Online',
        'https://meet.google.com/skillswap-demo');

SELECT * FROM v_session_overview WHERE session_id = LAST_INSERT_ID();

ROLLBACK;

-- I3. UPDATE — mark a scheduled session as completed and finish the request
START TRANSACTION;

SELECT session_id, request_id INTO @sid, @rid
FROM   sessions WHERE status = 'Scheduled' ORDER BY session_date LIMIT 1;

UPDATE sessions         SET status = 'Completed' WHERE session_id = @sid;
UPDATE exchangerequests SET status = 'Completed' WHERE request_id = @rid;

SELECT @sid AS session_id, @rid AS request_id,
       (SELECT status FROM sessions WHERE session_id = @sid)         AS session_status,
       (SELECT status FROM exchangerequests WHERE request_id = @rid) AS request_status;

ROLLBACK;

-- I4. DELETE — cancel a request and watch ON DELETE CASCADE clean up
START TRANSACTION;

SELECT er.request_id INTO @del
FROM        exchangerequests er
INNER JOIN  sessions s ON s.request_id = er.request_id
ORDER  BY   er.request_id LIMIT 1;

SELECT COUNT(*) AS sessions_before FROM sessions WHERE request_id = @del;

DELETE FROM exchangerequests WHERE request_id = @del;

SELECT COUNT(*) AS sessions_after_cascade FROM sessions WHERE request_id = @del;

ROLLBACK;

-- I5. Transaction demonstrating a constraint failure being rolled back
--     (rating 9 violates CHECK rating BETWEEN 1 AND 5)
START TRANSACTION;
SELECT COUNT(*) AS reviews_before FROM reviews;
-- The next line intentionally fails; uncomment to demonstrate live:
-- INSERT INTO reviews (session_id, reviewer_id, reviewee_id, rating, comment)
-- VALUES (1, 1, 2, 9, 'Invalid rating, will be rejected by CHECK constraint.');
SELECT COUNT(*) AS reviews_after FROM reviews;
ROLLBACK;

-- =============================================================
--  J. REPORTING QUERIES FOR THE DASHBOARD
-- =============================================================

-- J1. Platform statistics in a single result set
SELECT
  (SELECT COUNT(*) FROM users)                                       AS total_students,
  (SELECT COUNT(*) FROM skills)                                      AS total_skills,
  (SELECT COUNT(*) FROM exchangerequests)                            AS total_requests,
  (SELECT COUNT(*) FROM exchangerequests WHERE status = 'Completed')  AS completed_exchanges,
  (SELECT COUNT(*) FROM sessions WHERE status = 'Scheduled')          AS upcoming_sessions,
  (SELECT COUNT(*) FROM reviews)                                      AS total_reviews,
  (SELECT ROUND(AVG(rating), 2) FROM reviews)                         AS platform_avg_rating;

-- J2. Most active departments by completed exchanges
SELECT u.department, COUNT(*) AS completed_exchanges
FROM        exchangerequests er
INNER JOIN  users u ON u.user_id = er.sender_id
WHERE       er.status = 'Completed'
GROUP  BY   u.department
ORDER  BY   completed_exchanges DESC;

-- J3. Skill supply vs demand gap
SELECT s.skill_name,
       SUM(CASE WHEN us.skill_type = 'Teach' THEN 1 ELSE 0 END) AS teachers,
       SUM(CASE WHEN us.skill_type = 'Learn' THEN 1 ELSE 0 END) AS learners,
       SUM(CASE WHEN us.skill_type = 'Learn' THEN 1 ELSE -1 END) AS demand_gap
FROM        skills     s
LEFT JOIN   userskills us ON us.skill_id = s.skill_id
GROUP  BY   s.skill_id, s.skill_name
ORDER  BY   demand_gap DESC
LIMIT  10;

-- =============================================================
--  END OF queries.sql
-- =============================================================
