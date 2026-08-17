"""HTTP API — locked Step 49, built on locked Steps 38, 43 and 47.

The API is the *only* way into the domain (38.22): the frontend never reaches the
database, and every request is authorized server-side (43.23) regardless of what
the UI chose to display.
"""
