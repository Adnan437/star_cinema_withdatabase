"""
database.py
Database access layer for Star Cinema.

This version uses Supabase Postgres as the backend so the Streamlit app can be
hosted live and read/write data in a cloud database.
"""

import os
import streamlit as st
from supabase import create_client, Client


def get_supabase_client() -> Client:
    """Return an authenticated Supabase client using Streamlit secrets or env vars."""
    url = None
    key = None
    url_source = None
    key_source = None

    # Nested secret section: [supabase]
    if "supabase" in st.secrets and isinstance(st.secrets["supabase"], dict):
        url = st.secrets["supabase"].get("url")
        key = st.secrets["supabase"].get("key")
        if url:
            url_source = "st.secrets[supabase].url"
        if key:
            key_source = "st.secrets[supabase].key"

    # Top-level secrets
    if not url:
        for name in ["SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL", "supabase_url"]:
            if name in st.secrets:
                url = st.secrets[name]
                url_source = f"st.secrets[{name}]"
                break
    if not key:
        for name in ["SUPABASE_KEY", "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "supabase_key"]:
            if name in st.secrets:
                key = st.secrets[name]
                key_source = f"st.secrets[{name}]"
                break

    # Environment variables
    if not url:
        for name in ["SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_URL", "supabase_url"]:
            value = os.environ.get(name)
            if value:
                url = value
                url_source = f"env:{name}"
                break
    if not key:
        for name in ["SUPABASE_KEY", "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", "supabase_key"]:
            value = os.environ.get(name)
            if value:
                key = value
                key_source = f"env:{name}"
                break

    if not url or not key:
        raise RuntimeError(
            "Supabase credentials are missing. Set them in Streamlit secrets or environment variables. "
            "Supported names are:\n"
            "  - [supabase] section: supabase.url, supabase.key\n"
            "  - top-level secrets: SUPABASE_URL, SUPABASE_KEY\n"
            "  - top-level secrets: NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY\n"
            "  - environment vars: SUPABASE_URL, SUPABASE_KEY, NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY\n"
            f"\n\nTried URL source: {url_source or 'none'}, KEY source: {key_source or 'none'}."
        )

    return create_client(url, key)


def _count(response):
    return response.count if getattr(response, "count", None) is not None else len(response.data or [])


class StarCinema:
    """Base class. hall_list is a class attribute shared by every Hall object."""
    hall_list = []

    def entry_hall(self, hall_no):
        StarCinema.hall_list.append(hall_no)


class Hall(StarCinema):
    """Represents one cinema hall. All data lives in Supabase Postgres."""

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
        supabase = get_supabase_client()

        show_resp = supabase.table("shows").insert({
            "show_id": show_id,
            "movie_name": movie_name,
            "show_time": show_time,
            "total_rows": rows,
            "total_cols": cols,
            "ticket_price": price,
            "poster_color": color,
        }).execute()

        if show_resp.error:
            if "duplicate key" in str(show_resp.error.message).lower() or "already exists" in str(show_resp.error.message).lower():
                return False, "A show with that ID already exists. Choose a different ID."
            return False, f"Could not add show: {show_resp.error.message}"

        seat_rows = [
            {"show_id": show_id, "row_num": r, "col_num": c, "is_booked": False}
            for r in range(rows)
            for c in range(cols)
        ]
        seats_resp = supabase.table("seats").insert(seat_rows).execute()
        if seats_resp.error:
            supabase.table("shows").delete().eq("show_id", show_id).execute()
            return False, f"Could not add show seats: {seats_resp.error.message}"

        return True, "Show added successfully."

    def get_shows(self):
        supabase = get_supabase_client()
        resp = supabase.table("shows").select("*").order("show_time", {"ascending": True}).execute()
        return resp.data or []

    def get_show(self, show_id):
        supabase = get_supabase_client()
        resp = supabase.table("shows").select("*").eq("show_id", show_id).execute()
        return (resp.data or [None])[0]

    # ------------------------------------------------------------------
    # SEATS
    # ------------------------------------------------------------------
    def get_seat_grid(self, show_id, rows, cols):
        """Returns a rows x cols grid of True (free) / False (booked)."""
        supabase = get_supabase_client()
        resp = supabase.table("seats").select("row_num,col_num,is_booked").eq("show_id", show_id).execute()
        grid = [[True for _ in range(cols)] for _ in range(rows)]
        for seat in resp.data or []:
            grid[seat["row_num"]][seat["col_num"]] = not bool(seat["is_booked"])
        return grid

    def available_seat_count(self, show_id):
        supabase = get_supabase_client()
        resp = (
            supabase.table("seats")
            .select("id", count="exact")
            .eq("show_id", show_id)
            .eq("is_booked", False)
            .execute()
        )
        return _count(resp)

    # ------------------------------------------------------------------
    # BOOKING
    # ------------------------------------------------------------------
    def book_seats(self, show_id, name, phone, seat_list, price_per_seat):
        supabase = get_supabase_client()
        updated = []

        for r, c in seat_list:
            seat_resp = (
                supabase.table("seats")
                .update({"is_booked": True})
                .eq("show_id", show_id)
                .eq("row_num", r)
                .eq("col_num", c)
                .eq("is_booked", False)
                .execute()
            )
            if seat_resp.error or not (seat_resp.data and len(seat_resp.data) > 0):
                for ur, uc in updated:
                    supabase.table("seats").update({"is_booked": False}).eq("show_id", show_id).eq("row_num", ur).eq("col_num", uc).execute()
                label = Hall.seat_label(r, c)
                return False, f"Seat {label} is already booked. Please choose another seat.", None
            updated.append((r, c))

        seat_labels = ", ".join(Hall.seat_label(r, c) for r, c in seat_list)
        total = len(seat_list) * price_per_seat
        booking_resp = (
            supabase.table("bookings")
            .insert({
                "show_id": show_id,
                "customer_name": name,
                "phone": phone,
                "seat_labels": seat_labels,
                "total_price": total,
            })
            .execute()
        )

        if booking_resp.error or not (booking_resp.data and len(booking_resp.data) > 0):
            for ur, uc in updated:
                supabase.table("seats").update({"is_booked": False}).eq("show_id", show_id).eq("row_num", ur).eq("col_num", uc).execute()
            error_message = booking_resp.error.message if booking_resp.error else "Unknown booking error."
            return False, f"Booking failed: {error_message}", None

        ticket_no = booking_resp.data[0].get("ticket_no")
        return True, "ok", {"ticket_no": ticket_no, "total": total, "seat_labels": seat_labels}

    def cancel_booking(self, ticket_no):
        """Admin action: cancel a booking and free up its seats."""
        supabase = get_supabase_client()
        resp = supabase.table("bookings").select("*").eq("ticket_no", ticket_no).execute()
        booking = (resp.data or [None])[0]
        if not booking:
            return False, "Booking not found."

        for label in booking["seat_labels"].split(", "):
            r = ord(label[0]) - 65
            c = int(label[1:])
            supabase.table("seats").update({"is_booked": False}).eq("show_id", booking["show_id"]).eq("row_num", r).eq("col_num", c).execute()

        delete_resp = supabase.table("bookings").delete().eq("ticket_no", ticket_no).execute()
        if delete_resp.error:
            return False, f"Could not cancel booking: {delete_resp.error.message}"
        return True, "Booking cancelled and seats released."

    def get_all_bookings(self):
        """Admin action: full list of booked seats / tickets, newest first."""
        supabase = get_supabase_client()
        bookings_resp = supabase.table("bookings").select("*").order("booked_at", {"ascending": False}).execute()
        show_lookup = {show["show_id"]: show for show in self.get_shows()}
        rows = []
        for booking in bookings_resp.data or []:
            show = show_lookup.get(booking["show_id"], {})
            rows.append(
                {
                    "ticket_no": booking["ticket_no"],
                    "customer_name": booking["customer_name"],
                    "phone": booking["phone"],
                    "seat_labels": booking["seat_labels"],
                    "total_price": booking["total_price"],
                    "booked_at": booking["booked_at"],
                    "movie_name": show.get("movie_name", "Unknown"),
                    "show_time": show.get("show_time", ""),
                    "show_id": booking["show_id"],
                }
            )
        return rows
