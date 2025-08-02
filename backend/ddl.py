# create table if not exists public.company_detail
# (
#     id             serial
#         primary key,
#     full_name      varchar(100),
#     company_number integer
# );
#
# create index if not exists idx_company_number
#     on public.company_detail (company_number);
# create table public.company_overview
# (
#     company_number integer      not null
#         primary key,
#     company_name   varchar(255) not null
#         unique,
#     overview_text  text
# );
#
#
# create table if not exists public.profit_and_loss
# (
#     id          serial
#         primary key,
#     company_id  integer
#         references public.company_detail,
#     report_date date,
#     parameter   varchar(255) not null,
#     value       numeric,
#     created_at  timestamp default CURRENT_TIMESTAMP,
#     updated_at  timestamp default CURRENT_TIMESTAMP,
#     unique (company_id, report_date, parameter)
# );
#
# create trigger update_profit_and_loss_timestamp
#     before update
#     on public.profit_and_loss
#     for each row
# execute procedure public.update_timestamp_column();
#
# create table if not exists public.balance_sheet
# (
#     id          serial
#         primary key,
#     company_id  integer
#         references public.company_detail,
#     report_date date,
#     parameter   varchar(255) not null,
#     value       numeric,
#     created_at  timestamp default CURRENT_TIMESTAMP,
#     updated_at  timestamp default CURRENT_TIMESTAMP,
#     unique (company_id, report_date, parameter)
# );
#
# create trigger update_balance_sheet_timestamp
#     before update
#     on public.balance_sheet
#     for each row
# execute procedure public.update_timestamp_column();
#
# create table if not exists public.cashflow
# (
#     id          serial
#         primary key,
#     company_id  integer
#         references public.company_detail,
#     report_date date,
#     parameter   varchar(255) not null,
#     value       numeric,
#     created_at  timestamp default CURRENT_TIMESTAMP,
#     updated_at  timestamp default CURRENT_TIMESTAMP,
#     unique (company_id, report_date, parameter)
# );
#
#
# create trigger update_cashflow_timestamp
#     before update
#     on public.cashflow
#     for each row
# execute procedure public.update_timestamp_column();
#
# create table if not exists public.quarterly_results
# (
#     id          serial
#         primary key,
#     company_id  integer
#         references public.company_detail,
#     report_date date,
#     parameter   varchar(255) not null,
#     value       numeric,
#     created_at  timestamp default CURRENT_TIMESTAMP,
#     updated_at  timestamp default CURRENT_TIMESTAMP,
#     unique (company_id, report_date, parameter)
# );
#
# create trigger update_quarterly_results_timestamp
#     before update
#     on public.quarterly_results
#     for each row
# execute procedure public.update_timestamp_column();
#
# postgres: public, extensions> -- CREATE TABLE profile_metrics (
#                               --     id INT PRIMARY KEY, -- Unique ID for each metric entry
#                               --     company_number INT, -- Foreign key to link to company_overview
#                               --     metric VARCHAR(100), -- e.g., 'Market Cap', 'Employees'
#                               --     value DECIMAL(18, 4), -- Using DECIMAL for numerical values
#                               --     unit VARCHAR(20), -- e.g., 'Crore INR', 'People'
#                               --     source VARCHAR(100), -- e.g., 'Yahoo Finance', 'Company Website'
#                               --     as_of DATE, -- Date the metric is valid as of
#                               --     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                               --     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                               --     FOREIGN KEY (company_number) REFERENCES company_overview(company_number)
#                               --     ON UPDATE CASCADE -- Optional: uncomment if you want company_number updates to cascade
#                               --     ON DELETE CASCADE -- Optional: uncomment if you want deleting a company to delete its metrics
#                               -- );
#                               --
#                               -- -- Table for Margins metrics
#                               -- CREATE TABLE margins_metrics (
#                               --     id INT  PRIMARY KEY,
#                               --     company_number INT,
#                               --     metric VARCHAR(100), -- e.g., 'Gross', 'EBITDA'
#                               --     value DECIMAL(18, 4),
#                               --     unit VARCHAR(20), -- e.g., '%'
#                               --     source VARCHAR(100), -- e.g., 'Yahoo Finance', 'Calculated'
#                               --     as_of DATE,
#                               --     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                               --     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                               --     FOREIGN KEY (company_number) REFERENCES company_overview(company_number)
#                               --     ON UPDATE CASCADE
#                               --     ON DELETE CASCADE
#                               -- );
#                               --
#                               -- -- Table for Returns (5Yr Avg) metrics
#                               -- CREATE TABLE returns_5yr_avg_metrics (
#                               --     id INT PRIMARY KEY,
#                               --     company_number INT,
#                               --     metric VARCHAR(100), -- e.g., 'ROA', 'ROE'
#                               --     value DECIMAL(18, 4),
#                               --     unit VARCHAR(20), -- e.g., '%'
#                               --     source VARCHAR(100), -- e.g., 'Calculated'
#                               --     as_of DATE, -- Represents the end date of the 5-year period
#                               --     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                               --     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                               --     FOREIGN KEY (company_number) REFERENCES company_overview(company_number)
#                               --     ON UPDATE CASCADE
#                               --     ON DELETE CASCADE
#                               -- );
#                               --
#                               -- -- Table for Valuation (TTM) metrics
#                               -- CREATE TABLE valuation_ttm_metrics (
#                               --     id INT  PRIMARY KEY,
#                               --     company_number INT,
#                               --     metric VARCHAR(100), -- e.g., 'P/E', 'EV/Sales'
#                               --     value DECIMAL(18, 4),
#                               --     unit VARCHAR(20), -- e.g., 'Times', 'INR'
#                               --     source VARCHAR(100), -- e.g., 'Yahoo Finance', 'Calculated'
#                               --     as_of DATE, -- Date the TTM valuation is based on
#                               --     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                               --     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                               --     FOREIGN KEY (company_number) REFERENCES company_overview(company_number)
#                               --     -- ON UPDATE CASCADE
#                               --     -- ON DELETE CASCADE
#                               -- );
#                               --
#                               -- -- Table for Valuation (NTM) metrics
#                               -- CREATE TABLE valuation_ntm_metrics (
#                               --     id INT PRIMARY KEY,
#                               --     company_number INT,
#                               --     metric VARCHAR(100), -- e.g., 'Price Target', 'PEG'
#                               --     value DECIMAL(18, 4),
#                               --     unit VARCHAR(20), -- e.g., 'INR', 'Times'
#                               --     source VARCHAR(100), -- e.g., 'Analysts Estimates'
#                               --     as_of DATE, -- Date the NTM valuation is based on
#                               --     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                               --     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                               --     FOREIGN KEY (company_number) REFERENCES company_overview(company_number)
#                               --     ON UPDATE CASCADE
#                               --     ON DELETE CASCADE
#                               -- );
#                               --
#                               --
#                               --     -- ON UPDATE CASCADE
#                               --
#                               --     -- ON DELETE CASCADE
#                               -- -- Table for Financial Health metrics
#                               -- CREATE TABLE financial_health_metrics (
#                               --     id INT PRIMARY KEY,
#                               --     company_number INT,
#                               --     metric VARCHAR(100), -- e.g., 'Cash', 'Debt/Equity'
#                               --     value DECIMAL(18, 4),
#                               --     unit VARCHAR(20), -- e.g., 'Crore INR', 'Times'
#                               --     source VARCHAR(100), -- e.g., 'Company Filings'
#                               --     as_of DATE,
#                               --     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                               --     updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
#                               --     FOREIGN KEY (company_number) REFERENCES company_overview(company_number)
#                               --     -- ON UPDATE CASCADE
#                               --     -- ON DELETE CASCADE
#                               --
#                               -- );
#                               create trigger update_financial_health_timestamp
#                                   before update
#                                   on financial_health_metrics
#                                   for each row
#                               execute procedure update_timestamp_column()
# [2025-05-19 10:26:09] completed in 39 ms
# postgres: public, extensions> create trigger update_margins_timestamp
#                                   before update
#                                   on margins_metrics
#                                   for each row
#                               execute procedure update_timestamp_column()
# [2025-05-19 10:26:09] completed in 33 ms
#  create trigger update_returns_5yr_avg_timestamp
#                                   before update
#                                   on returns_5yr_avg_metrics
#                                   for each row
#                               execute procedure update_timestamp_column()
# [2025-05-19 10:26:09] completed in 37 ms
# postgres: public, extensions> create trigger update_valuation_ttm_timestamp
#                                   before update
#                                   on valuation_ttm_metrics
#                                   for each row
#                               execute procedure update_timestamp_column()
# [2025-05-19 10:26:09] completed in 33 ms
# postgres: public, extensions> create trigger update_valuation_ntm_timestamp
#                                   before update
#                                   on valuation_ntm_metrics
#                                   for each row
#                               execute procedure update_timestamp_column()
# [2025-05-19 10:26:09] completed in 34 ms
# postgres: public, extensions> create trigger update_growth_cagr_timestamp
#                                   before update
#                                   on growth_cagr_metrics
#                                   for each row
#                               execute procedure update_timestamp_column()
# [2025-05-19 10:26:10] completed in 33 ms
# postgres: public, extensions> create trigger update_profile_metrics_timestamp
#                                   before update
#                                   on profile_metrics
#                                   for each row
#                               execute procedure update_timestamp_column()