-- =============================================================
--  SkillSwap NSU  —  CSE311L Database Systems Lab
--  File   : schema.sql
--  Engine : MySQL / MariaDB (XAMPP)
--  Purpose: Full database structure (tables, keys, constraints,
--           indexes, views). Run this FIRST, then seed.sql
-- =============================================================

DROP DATABASE IF EXISTS `skillexchange`;
CREATE DATABASE `skillexchange`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;
USE `skillexchange`;

SET FOREIGN_KEY_CHECKS = 1;

-- NOTE ON REFERENTIAL RULES
--   ON DELETE CASCADE  -> child rows that are meaningless without the
--                         parent (a user's skills, requests, sessions,
--                         reviews) are removed automatically.
--   ON DELETE RESTRICT -> a skill cannot be deleted while an exchange
--                         request still points at it.
--   ON UPDATE RESTRICT -> every primary key here is a surrogate
--                         AUTO_INCREMENT id that is never edited, so
--                         cascading updates are not needed. MariaDB also
--                         rejects CHECK constraints on columns that use
--                         ON UPDATE CASCADE, and we want the CHECKs.

-- -------------------------------------------------------------
-- 1. users
--    One row per NSU student using the platform.
-- -------------------------------------------------------------
CREATE TABLE `users` (
  `user_id`         INT(11)      NOT NULL AUTO_INCREMENT,
  `name`            VARCHAR(100) NOT NULL,
  `email`           VARCHAR(255) NOT NULL,
  `password`        VARCHAR(255) NOT NULL,          -- Werkzeug pbkdf2 hash, never plain text
  `department`      VARCHAR(100) NOT NULL,
  `bio`             VARCHAR(255) DEFAULT NULL,
  `profile_picture` VARCHAR(255) DEFAULT 'default.png',
  `created_at`      TIMESTAMP    NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`user_id`),
  UNIQUE KEY `uq_users_email` (`email`),
  KEY `idx_users_department` (`department`),
  KEY `idx_users_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- -------------------------------------------------------------
-- 2. skills
--    Master list of skills that can be taught / learned.
-- -------------------------------------------------------------
CREATE TABLE `skills` (
  `skill_id`    INT(11)      NOT NULL AUTO_INCREMENT,
  `skill_name`  VARCHAR(100) NOT NULL,
  `category`    VARCHAR(50)  NOT NULL,
  `description` VARCHAR(255) DEFAULT NULL,
  PRIMARY KEY (`skill_id`),
  UNIQUE KEY `uq_skills_name` (`skill_name`),
  KEY `idx_skills_category` (`category`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- -------------------------------------------------------------
-- 3. userskills
--    Bridge table (M:N) between users and skills.
--    skill_type tells us whether the user TEACHES it or wants to LEARN it.
-- -------------------------------------------------------------
CREATE TABLE `userskills` (
  `user_skill_id` INT(11) NOT NULL AUTO_INCREMENT,
  `user_id`       INT(11) NOT NULL,
  `skill_id`      INT(11) NOT NULL,
  `skill_type`    ENUM('Teach','Learn') NOT NULL,
  `proficiency`   ENUM('Beginner','Intermediate','Advanced','Expert') NOT NULL DEFAULT 'Beginner',
  PRIMARY KEY (`user_skill_id`),
  -- the same user cannot list the same skill twice under the same type
  UNIQUE KEY `uq_userskills` (`user_id`,`skill_id`,`skill_type`),
  KEY `idx_userskills_skill` (`skill_id`),
  KEY `idx_userskills_type` (`skill_type`),
  CONSTRAINT `fk_userskills_user`
    FOREIGN KEY (`user_id`)  REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_userskills_skill`
    FOREIGN KEY (`skill_id`) REFERENCES `skills` (`skill_id`)
    ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- -------------------------------------------------------------
-- 4. exchangerequests
--    sender offers `teach_skill` and wants `learn_skill` from receiver.
-- -------------------------------------------------------------
CREATE TABLE `exchangerequests` (
  `request_id`   INT(11) NOT NULL AUTO_INCREMENT,
  `sender_id`    INT(11) NOT NULL,
  `receiver_id`  INT(11) NOT NULL,
  `teach_skill`  INT(11) NOT NULL,
  `learn_skill`  INT(11) NOT NULL,
  `status`       ENUM('Pending','Accepted','Rejected','Cancelled','Completed')
                 NOT NULL DEFAULT 'Pending',
  `created_at`   TIMESTAMP NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`request_id`),
  KEY `idx_req_sender` (`sender_id`),
  KEY `idx_req_receiver` (`receiver_id`),
  KEY `idx_req_teach` (`teach_skill`),
  KEY `idx_req_learn` (`learn_skill`),
  KEY `idx_req_status` (`status`),
  -- a student can never send a request to himself
  CONSTRAINT `chk_req_not_self` CHECK (`sender_id` <> `receiver_id`),
  -- the two skills in one exchange must be different
  CONSTRAINT `chk_req_skills_differ` CHECK (`teach_skill` <> `learn_skill`),
  CONSTRAINT `fk_req_sender`
    FOREIGN KEY (`sender_id`)   REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_req_receiver`
    FOREIGN KEY (`receiver_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_req_teach`
    FOREIGN KEY (`teach_skill`) REFERENCES `skills` (`skill_id`)
    ON DELETE RESTRICT ON UPDATE RESTRICT,
  CONSTRAINT `fk_req_learn`
    FOREIGN KEY (`learn_skill`) REFERENCES `skills` (`skill_id`)
    ON DELETE RESTRICT ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- -------------------------------------------------------------
-- 5. sessions
--    A scheduled meeting that belongs to ONE accepted request.
-- -------------------------------------------------------------
CREATE TABLE `sessions` (
  `session_id`   INT(11) NOT NULL AUTO_INCREMENT,
  `request_id`   INT(11) NOT NULL,
  `session_date` DATE    NOT NULL,
  `session_time` TIME    NOT NULL,
  `duration`     INT(11) NOT NULL DEFAULT 60,       -- minutes
  `mode`         ENUM('Online','Offline') NOT NULL DEFAULT 'Online',
  `location`     VARCHAR(255) DEFAULT NULL,         -- filled when mode = Offline
  `meeting_link` VARCHAR(255) DEFAULT NULL,         -- filled when mode = Online
  `status`       ENUM('Scheduled','Completed','Cancelled') NOT NULL DEFAULT 'Scheduled',
  `created_at`   TIMESTAMP NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`session_id`),
  -- no two sessions for the same request at the exact same date+time
  UNIQUE KEY `uq_session_slot` (`request_id`,`session_date`,`session_time`),
  KEY `idx_sess_request` (`request_id`),
  KEY `idx_sess_status` (`status`),
  KEY `idx_sess_date` (`session_date`),
  CONSTRAINT `chk_sess_duration` CHECK (`duration` BETWEEN 15 AND 480),
  CONSTRAINT `fk_sess_request`
    FOREIGN KEY (`request_id`) REFERENCES `exchangerequests` (`request_id`)
    ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- -------------------------------------------------------------
-- 6. reviews
--    Feedback given after a COMPLETED session.
--    One review per (session, reviewer) pair — so both partners
--    may review each other, but neither can review twice.
-- -------------------------------------------------------------
CREATE TABLE `reviews` (
  `review_id`   INT(11) NOT NULL AUTO_INCREMENT,
  `session_id`  INT(11) NOT NULL,
  `reviewer_id` INT(11) NOT NULL,
  `reviewee_id` INT(11) NOT NULL,
  `rating`      INT(11) NOT NULL,
  `comment`     VARCHAR(200) DEFAULT NULL,
  `created_at`  TIMESTAMP NOT NULL DEFAULT current_timestamp(),
  PRIMARY KEY (`review_id`),
  UNIQUE KEY `uq_review_once` (`session_id`,`reviewer_id`),
  KEY `idx_rev_session` (`session_id`),
  KEY `idx_rev_reviewer` (`reviewer_id`),
  KEY `idx_rev_reviewee` (`reviewee_id`),
  CONSTRAINT `chk_rating_range` CHECK (`rating` BETWEEN 1 AND 5),
  CONSTRAINT `chk_rev_not_self` CHECK (`reviewer_id` <> `reviewee_id`),
  CONSTRAINT `fk_rev_session`
    FOREIGN KEY (`session_id`)  REFERENCES `sessions` (`session_id`)
    ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_rev_reviewer`
    FOREIGN KEY (`reviewer_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE RESTRICT,
  CONSTRAINT `fk_rev_reviewee`
    FOREIGN KEY (`reviewee_id`) REFERENCES `users` (`user_id`)
    ON DELETE CASCADE ON UPDATE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci;

-- =============================================================
--  VIEWS  (demonstrates derived / virtual tables)
-- =============================================================

-- Average rating + review count for every student
CREATE OR REPLACE VIEW `v_user_ratings` AS
SELECT  u.user_id,
        u.name,
        u.department,
        COUNT(r.review_id)              AS total_reviews,
        ROUND(AVG(r.rating), 2)         AS avg_rating
FROM        users   u
LEFT JOIN   reviews r ON r.reviewee_id = u.user_id
GROUP BY    u.user_id, u.name, u.department;

-- Fully expanded request list (IDs replaced by readable names)
CREATE OR REPLACE VIEW `v_request_details` AS
SELECT  er.request_id,
        s.name        AS sender_name,
        rc.name       AS receiver_name,
        st.skill_name AS offered_skill,
        sl.skill_name AS requested_skill,
        er.status,
        er.created_at
FROM       exchangerequests er
INNER JOIN users  s  ON s.user_id  = er.sender_id
INNER JOIN users  rc ON rc.user_id = er.receiver_id
INNER JOIN skills st ON st.skill_id = er.teach_skill
INNER JOIN skills sl ON sl.skill_id = er.learn_skill;

-- Every scheduled/completed session with both partner names
CREATE OR REPLACE VIEW `v_session_overview` AS
SELECT  se.session_id,
        se.session_date,
        se.session_time,
        se.duration,
        se.mode,
        se.status,
        s.name  AS teacher_name,
        rc.name AS learner_name,
        sk.skill_name AS skill_taught
FROM       sessions se
INNER JOIN exchangerequests er ON er.request_id = se.request_id
INNER JOIN users  s  ON s.user_id  = er.sender_id
INNER JOIN users  rc ON rc.user_id = er.receiver_id
INNER JOIN skills sk ON sk.skill_id = er.teach_skill;

-- =============================================================
--  END OF schema.sql
-- =============================================================
