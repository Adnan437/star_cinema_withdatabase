# star_cinema_withdatabase

Star Cinema is a Streamlit ticket-booking app that now uses Supabase Postgres for all application data.

## Setup

1. Add your Supabase credentials to Streamlit secrets or environment variables.

   Example `.streamlit/secrets.toml` nested format:

   ```toml
   [supabase]
   url = "https://sxvzmyjwxjldqrzcqzju.supabase.co"
   key = "sb_publishable_rQxKrFKr4RuU-z0Pfs8fUg_FG2yKPHh"
   ```

   Or top-level secrets:

   ```toml
   NEXT_PUBLIC_SUPABASE_URL = "https://sxvzmyjwxjldqrzcqzju.supabase.co"
   NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY = "sb_publishable_rQxKrFKr4RuU-z0Pfs8fUg_FG2yKPHh"
   ```

   Or environment variables:

   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_KEY`

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Run the app:

   ```bash
   python -m streamlit run app.py
   ```

## Database schema

Use the `schema.sql` file in Supabase SQL editor to create `shows`, `seats`, and `bookings` tables.

## Notes

The app is built to run live on Streamlit and uses Supabase as the backend database service.
