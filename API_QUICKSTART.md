Base URL: Your public Render URL (e.g., https://scrapr-iq-api.onrender.com).
Key Endpoint: /scrapr-iq/ (POST) - Your primary lead scraping endpoint.
Batch Endpoint: /batch-scrape-leads/ (POST) - For multiple URLs.
Retrieve Leads: /leads/ (GET) - To get all stored leads.
Health Check: /health (GET) - To confirm API and DB connectivity.
Create Tables: /create-tables (POST) - Use with caution. Only for initial DB setup or if tables are dropped.