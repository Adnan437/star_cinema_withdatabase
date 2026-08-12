-- Star Cinema Database Schema
-- Run this once in MySQL (phpMyAdmin / MySQL CLI) before running the app.

CREATE DATABASE IF NOT EXISTS star_cinema;
USE star_cinema;

CREATE TABLE IF NOT EXISTS shows (
    show_id       VARCHAR(20)  PRIMARY KEY,
    movie_name    VARCHAR(100) NOT NULL,
    show_time     VARCHAR(20)  NOT NULL,
    total_rows    INT          NOT NULL,
    total_cols    INT          NOT NULL,
    ticket_price  INT          NOT NULL,
    poster_color  VARCHAR(10)  DEFAULT '#1f6fb2',
    created_at    TIMESTAMP    DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS seats (
    id         INT AUTO_INCREMENT PRIMARY KEY,
    show_id    VARCHAR(20) NOT NULL,
    row_num    INT NOT NULL,
    col_num    INT NOT NULL,
    is_booked  BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (show_id) REFERENCES shows(show_id) ON DELETE CASCADE,
    UNIQUE KEY unique_seat (show_id, row_num, col_num)
);

CREATE TABLE IF NOT EXISTS bookings (
    ticket_no      INT AUTO_INCREMENT PRIMARY KEY,
    show_id        VARCHAR(20)  NOT NULL,
    customer_name  VARCHAR(100) NOT NULL,
    phone          VARCHAR(20)  NOT NULL,
    seat_labels    VARCHAR(255) NOT NULL,
    total_price    INT          NOT NULL,
    booked_at      TIMESTAMP    DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (show_id) REFERENCES shows(show_id)
);

-- Sample demo data (optional -- delete these and add your own shows
-- through the Admin -> Add Show page instead, if you prefer to start empty)
INSERT IGNORE INTO shows (show_id, movie_name, show_time, total_rows, total_cols, ticket_price, poster_color) VALUES
('abc', 'Finding Nemo', '03:50 PM', 5, 8, 150, '#1f6fb2'),
('asd', 'Ice Age',      '10:00 AM', 5, 8, 150, '#2a9d8f'),
('bcd', 'Avatar',       '05:00 PM', 5, 8, 200, '#6a4c93');

INSERT IGNORE INTO seats (show_id, row_num, col_num, is_booked)
SELECT s.show_id, r.n, c.n, FALSE
FROM shows s
JOIN (SELECT 0 AS n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4) r
JOIN (SELECT 0 AS n UNION SELECT 1 UNION SELECT 2 UNION SELECT 3 UNION SELECT 4 UNION SELECT 5 UNION SELECT 6 UNION SELECT 7) c
WHERE r.n < s.total_rows AND c.n < s.total_cols;
