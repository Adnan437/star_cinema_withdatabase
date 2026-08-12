"""
database.py
Database access layer for Star Cinema.

Keeps the same OOP idea as the original console project:
  StarCinema (base class)  ->  Hall (child class)
but now every read/write goes through MySQL instead of an in-memory list,
so data survives restarts and multiple people can book at the same time.
"""

import mysql.connector
import streamlit as st


def get_connection():
    """
    Opens a MySQL connection.
    - On Streamlit Cloud: reads credentials from st.secrets["mysql"]
      (set these in the app's Settings -> Secrets).
    - On your own PC (e.g. XAMPP): falls back to local defaults.
    """
    try:
        cfg = st.secrets["mysql"]
        return mysql.connector.connect(
            host=cfg["host"],
            port=int(cfg.get("port", 3306)),
            user=cfg["user"],
            password=cfg["password"],
            database=cfg["database"],
        )
    except Exception:
        # Local development fallback (default XAMPP / MySQL settings)
        return mysql.connector.connect(
            host="localhost",
            port=3306,
            user="root",
            password="",
            database="star_cinema",
        )


class StarCinema:
    """Base class. hall_list is a class attribute shared by every Hall object,
    same concept as the original console project."""
    hall_list = []

    def entry_hall(self, hall_no):
        StarCinema.hall_list.append(hall_no)


class Hall(StarCinema):
    """Represents one cinema hall. All data lives in MySQL."""

    def __init__(self, hall_no="Hall 1"):
        self.hall_no = hall_no
        self.entry_hall(hall_no)

    @staticmethod
    def seat_label(r, c):
        return f"{chr(65 + r)}{c}"

    # ------------------------------------------------------------------
    # SHOWS
    # ------------------------------------------------------------------
    def add_show(self, show_id, movie_name, show_time, rows, cols, price, color="#1f6fb2"):
        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO shows (show_id, movie_name, show_time, total_rows, "
                "total_cols, ticket_price, poster_color) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (show_id, movie_name, show_time, rows, cols, price, color),
            )
            seat_rows = [(show_id, r, c) for r in range(rows) for c in range(cols)]
            cur.executemany(
                "INSERT INTO seats (show_id, row_num, col_num, is_booked) VALUES (%s,%s,%s,FALSE)",
                seat_rows,
            )
            conn.commit()
            return True, "Show added successfully."
        except mysql.connector.IntegrityError:
            conn.rollback()
            return False, "A show with that ID already exists. Choose a different ID."
        except Exception as e:
            conn.rollback()
            return False, f"Could not add show: {e}"
        finally:
            cur.close()
            conn.close()

    def get_shows(self):
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM shows ORDER BY show_time")
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows

    def get_show(self, show_id):
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute("SELECT * FROM shows WHERE show_id = %s", (show_id,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row

    # ------------------------------------------------------------------
    # SEATS
    # ------------------------------------------------------------------
    def get_seat_grid(self, show_id, rows, cols):
        """Returns a rows x cols grid of True (free) / False (booked)."""
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT row_num, col_num, is_booked FROM seats WHERE show_id = %s",
            (show_id,),
        )
        data = cur.fetchall()
        cur.close()
        conn.close()

        grid = [[True for _ in range(cols)] for _ in range(rows)]
        for d in data:
            grid[d["row_num"]][d["col_num"]] = not bool(d["is_booked"])
        return grid

    def available_seat_count(self, show_id):
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM seats WHERE show_id=%s AND is_booked=FALSE", (show_id,)
        )
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return count

    # ------------------------------------------------------------------
    # BOOKING
    # ------------------------------------------------------------------
    def book_seats(self, show_id, name, phone, seat_list, price_per_seat):
        """
        seat_list: list of (row, col) tuples.
        Locks the rows being booked (FOR UPDATE) so two people can't grab
        the same seat at the same time, checks availability, then books
        everything in a single transaction (all-or-nothing).
        """
        conn = get_connection()
        cur = conn.cursor()
        try:
            for r, c in seat_list:
                cur.execute(
                    "SELECT is_booked FROM seats WHERE show_id=%s AND row_num=%s "
                    "AND col_num=%s FOR UPDATE",
                    (show_id, r, c),
                )
                result = cur.fetchone()
                if result is None or result[0]:
                    conn.rollback()
                    label = Hall.seat_label(r, c)
                    return False, f"Seat {label} is already booked. Please choose another seat.", None

            for r, c in seat_list:
                cur.execute(
                    "UPDATE seats SET is_booked=TRUE WHERE show_id=%s AND row_num=%s AND col_num=%s",
                    (show_id, r, c),
                )

            seat_labels = ", ".join(Hall.seat_label(r, c) for r, c in seat_list)
            total = len(seat_list) * price_per_seat
            cur.execute(
                "INSERT INTO bookings (show_id, customer_name, phone, seat_labels, total_price) "
                "VALUES (%s,%s,%s,%s,%s)",
                (show_id, name, phone, seat_labels, total),
            )
            ticket_no = cur.lastrowid
            conn.commit()
            return True, "ok", {"ticket_no": ticket_no, "total": total, "seat_labels": seat_labels}
        except Exception as e:
            conn.rollback()
            return False, f"Booking failed: {e}", None
        finally:
            cur.close()
            conn.close()

    def cancel_booking(self, ticket_no):
        """Admin action: cancel a booking and free up its seats."""
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        try:
            cur.execute(
                "SELECT show_id, seat_labels FROM bookings WHERE ticket_no=%s", (ticket_no,)
            )
            booking = cur.fetchone()
            if not booking:
                return False, "Booking not found."

            for label in booking["seat_labels"].split(", "):
                r = ord(label[0]) - 65
                c = int(label[1:])
                cur.execute(
                    "UPDATE seats SET is_booked=FALSE WHERE show_id=%s AND row_num=%s AND col_num=%s",
                    (booking["show_id"], r, c),
                )

            cur.execute("DELETE FROM bookings WHERE ticket_no=%s", (ticket_no,))
            conn.commit()
            return True, "Booking cancelled and seats released."
        except Exception as e:
            conn.rollback()
            return False, f"Could not cancel booking: {e}"
        finally:
            cur.close()
            conn.close()

    def get_all_bookings(self):
        """Admin action: full list of booked seats / tickets, newest first."""
        conn = get_connection()
        cur = conn.cursor(dictionary=True)
        cur.execute(
            "SELECT b.ticket_no, b.customer_name, b.phone, b.seat_labels, b.total_price, "
            "b.booked_at, s.movie_name, s.show_time, s.show_id "
            "FROM bookings b JOIN shows s ON b.show_id = s.show_id "
            "ORDER BY b.booked_at DESC"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
