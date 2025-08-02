# h=[('Macrotech Devel', 'Macrotech Developers', 1), ('Adani Green', 'Adani Green Energy', 2), ('Varun Beverages', 'Varun Beverages Limited', 3), ('Jio Financial', 'Reliance Jio Financial Services', 4), ('IndusInd Bank', 'IndusInd Bank', 5), ('Cholaman.Inv.&Fn', 'Cholamandalam Investment & Finance', 7), ('Jindal Steel', 'Jindal Steel & Power', 8), ('ICICI Pru Life', 'ICICI Prudential Life Insurance', 10), ('I O C L', 'Indian Oil Corporation Limited', 11), ('Zomato Ltd', 'Zomato Limited', 16), ('Ambuja Cements', 'Ambuja Cements Limited', 17), ('CG Power & Ind', 'CG Power and Industrial Solutions', 19), ('TVS Motor Co', 'TVS Motor Company', 21), ('Bank of Baroda', 'Bank of Baroda', 22), ('United Spirits', 'United Spirits Limited', 23), ('UltraTech Cem', 'UltraTech Cement', 24), ('Avenue Super', 'Avenue Supermarts', 26), ('Zydus Lifesci', 'Zydus Lifesciences', 28), ('Grasim Inds', 'Grasim Industries', 30), ('Abbott India', 'Abbott India Limited', 31), ('Tata Power Co', 'Tata Power Company Limited', 32), ('Punjab Natl.Bank', 'Punjab National Bank', 33), ('Samvardh. Mothe', 'Samvardhana Motherson', 35), ('Bosch', 'Bosch Limited', 37), ('I R F C', 'Indian Railway Catering and Tourism Corporation', 38), ('Havells India', 'Havells India Limited', 39), ('Shriram Finance', 'Shriram Transport Finance', 41), ('Info Edg.(India)', 'Info Edge (India)', 42), ('Tata Steel', 'Tata Steel Limited', 43), ('JSW Steel', 'JSW Steel Limited', 44), ('Hindalco Inds', 'Hindalco Industries', 45), ('M & M', 'Mahindra & Mahindra', 47), ('SBI Life Insuran', 'SBI Life Insurance', 49), ('Torrent Pharma', 'Torrent Pharmaceuticals', 51), ('Hero Motocorp', 'Hero MotoCorp Limited', 52), ('REC Ltd', 'REC Limited', 53), ('Canara Bank', 'Canara Bank', 54), ('Trent', 'Trent Limited', 56), ('JSW Energy', 'JSW Energy Limited', 57), ('Bajaj Auto', 'Bajaj Auto Limited', 60), ('Power Fin.Corpn', 'Power Finance Corporation', 61), ('Bajaj Finance', 'Bajaj Finance Limited', 62), ('Bharat Electron', 'Bharat Electronics Limited', 63), ('Power Grid Corpn', 'Power Grid Corporation of India', 64), ('Hyundai Motor I', 'Hyundai Motor India', 66), ('Indian Hotels Co', 'Indian Hotels Company Limited', 68), ('B P C L', 'Bharat Petroleum Corporation Limited', 69), ('Shree Cement', 'Shree Cement Limited', 70), ('LTIMindtree', 'L&T Infotech', 71), ('Tata Consumer', 'Tata Consumer Products', 72), ('Bajaj Housing', 'Bajaj Housing Finance', 73), ('ICICI Lombard', 'ICICI Lombard General Insurance', 75), ('Siemens', 'Siemens Limited', 76), ('HDFC Life Insur', 'HDFC Life Insurance', 77), ('Wipro', 'Wipro Limited', 78), ('DLF', 'DLF Limited', 79), ('Nestle India', 'Nestlé India Limited', 80), ('Life Insurance', 'Life Insurance Corporation', 81), ('Pidilite Inds', 'Pidilite Industries', 82), ('Vedanta', 'Vedanta Limited', 83), ('Adani Energy Sol', 'Adani Green Energy', 84), ('GAIL (India)', 'GAIL (India) Limited', 85), ('Godrej Consumer', 'Godrej Consumer Products', 86), ('Bajaj Holdings', 'Bajaj Holdings & Investment', 88), ('Adani Ports', 'Adani Ports and Special Economic Zone', 89), ('Hind.Aeronautics', 'Hindustan Aeronautics Limited', 90), ('Divi', 'Divi’s Laboratories', 91), ('HCL Technologies', 'HCL Technologies Limited', 92), ('Apollo Hospitals', 'Apollo Hospitals Enterprise', 93), ('Swiggy', 'Swiggy', 94), ('Dr Reddy', "Dr. Reddy's Laboratories", 95), ('Bajaj Finserv', 'Bajaj Finserv Limited', 96), ('Dabur India', 'Dabur India Limited', 97), ('Interglobe Aviat', 'InterGlobe Aviation', 98), ('ULTRACEMCO', 'UltraTech Cement', 102), ('HINDALCO', 'Hindalco Industries', 103), ('SBILIFE', 'SBI Life Insurance', 104), ('NESTLEIND', 'Nestlé India Limited', 105), ('WIPRO', 'Wipro Limited', 106), ('JIOFIN', 'Reliance Jio Financial Services', 109), ('ADANIPORTS', 'Adani Ports and Special Economic Zone', 110), ('BAJAJ-AUTO', 'Bajaj Auto Limited', 111), ('POWERGRID', 'Power Grid Corporation of India', 113), ('TRENT', 'Trent Limited', 116), ('TATASTEEL', 'Tata Steel Limited', 118), ('HEROMOTOCO', 'Hero MotoCorp Limited', 120), ('HCLTECH', 'HCL Technologies Limited', 122), ('BAJFINANCE', 'Bajaj Finance Limited', 126), ('APOLLOHOSP', 'Apollo Hospitals Enterprise', 128), ('JSWSTEEL', 'JSW Steel Limited', 129), ('GRASIM', 'Grasim Industries', 130), ('ETERNAL', 'Eternal', 131), ('INDUSINDBK', 'IndusInd Bank', 132), ('SHRIRAMFIN', 'Shriram Finance', 135), ('BAJAJFINSV', 'Bajaj Finserv Limited', 137), ('DRREDDY', "Dr. Reddy's Laboratories", 139), ('M&M', 'Mahindra & Mahindra', 141), ('HDFCLIFE', 'HDFC Life Insurance', 142), ('TATACONSUM', 'Tata Consumer Products', 146), ('BEL', 'Bharat Electronics Limited', 147)]
# full_name_to_id = {}
# current_id = 27
# new_h = []
#
# for alias, full_name, _ in h:
#     if full_name not in full_name_to_id:
#         full_name_to_id[full_name] = current_id
#         current_id += 1
#     new_h.append((alias, full_name, full_name_to_id[full_name]))
#
# # Verify all same full_names have same ID and sequential numbering
# verification = {}
# for alias, full, num in new_h:
#     if full in verification:
#         assert verification[full] == num, f"Conflict: {full}"
#     else:
#         verification[full] = num
#
# assert sorted(set(verification.values())) == list(range(27, current_id)), "Non-sequential IDs"
#
# # Print formatted output
# print("[")
# for entry in new_h:
#     print(f"    {entry},")
# print("]")


# List of parameters extracted from the table
new_parameters = [
    "Accumulated Depreciation", "Acquisition of companies", "Advance from Customers",
    "Application money refund", "Borrowings", "Building", "Capital WIP",
    "Capital Work in Progress", "Cash & Bank", "Cash Equivalents",
    "Cash from Financing Activity", "Cash from Investing Activity",
    "Cash from Operating Activity", "Change in Inventory", "Computers",
    "Corporate loans", "Deposits", "Depreciation", "Direct taxes",
    "Dividend Amount", "Dividends paid", "Dividends received", "Employee Cost",
    "Employee Cost %", "Equipments", "Equity Share Capital", "Estates",
    "Exceptional CF items", "Exceptional items", "Exceptional items AT",
    "Expenses", "Face value", "Financial liabilities",
    "Fixed assets purchased", "Fixed assets sold", "Furniture n fittings",
    "Gross Block", "Intangible Assets", "Inter corporate deposits", "Interest",
    "Interest paid", "Interest paid fin", "Interest received", "Inventories",
    "Inventory", "Invest in subsidiaries", "Investment income",
    "Investment in group cos", "Investments", "Investments purchased",
    "Investments sold", "Investment subsidy", "Issue of shares on acq",
    "Land", "Lease Liabilities", "Loans Advances", "Loans n Advances",
    "Loans to subsidiaries", "Long term Borrowings", "Manufacturing Cost %",
    "Material Cost %", "Minority share", "Net Block", "Net Cash Flow",
    "Net profit", "New Bonus Shares", "Non controlling int",
    "No. of Equity Shares", "Operating borrowings", "Operating investments",
    "Operating Profit", "Other asset items", "Other Assets", "Other Borrowings",
    "Other Cost %", "Other Expenses", "Other financing items",
    "Other fixed assets", "Other Income", "Other income normal",
    "Other investing items", "Other Liabilities", "Other liability items",
    "Other Mfr. Exp", "Other operating items", "Other WC items", "Payables",
    "Plant Machinery", "Power and Fuel", "Preference Capital",
    "Proceeds from borrowings", "Proceeds from debentures",
    "Proceeds from deposits", "Proceeds from shares", "Profit after tax",
    "Profit before tax", "Profit for EPS", "Profit for PE",
    "Profit from Associates", "Profit from operations", "Railway sidings",
    "Raw Material Cost", "Receivables", "Redemp n Canc of Shares",
    "Redemption of debentures", "Repayment of borrowings", "Reported Net Profit",
    "Reserves", "Sales", "Sales Growth %", "Selling and admin",
    "Share application money", "Ships Vessels", "Short term Borrowings",
    "Subsidy received", "Tax", "Total", "Trade Payables", "Trade receivables",
    "Vehicles", "Working capital changes", "YOY Profit Growth %",
    "YOY Sales Growth %"
]

# Previously obtained separated_params list
separated_params = [
'Fixed asset turnover', 'Net profit', 'Equity share capital', 'Raw Material consumption', 'Selling and distribution expenses', 'Cash from operating activities', 'Employee cost', 'Other income', 'Depreciation', 'Cash from investing activities', 'Change in working capital', 'Receivables', 'Exceptional items', 'Profit', 'Net block additions', 'Reported profit', 'Sales growth', 'New bonus issue', 'Dividend amount', 'Profit for the period', 'Market price', 'Interest received', 'Cash & Bank balances', 'Net cash flow', 'Profit before interest and tax', 'Profit before tax', 'Net sales', 'Raw Materials', 'Profit for the year', 'Sales', 'Minority share', 'Other expenses', 'Profit before depreciation', 'Receivables turnover', 'Profit from operations', 'Other cost', 'net block', 'Reserves', 'Net working capital', 'net profit', 'Net cash flow from financing activities', 'Tax', 'Investment activities'
]
metrics = [
    "AUM 3Yr",
    "AUM 5Yr",
    "CASA Ratio",
    "Cash",
    "Cash & Balances",
    "CET1 Ratio",
    "Cost to Income",
    "Cost-to-Income",
    "Cost to Income Ratio",
    "Cost-to-Income Ratio",
    "CRAR",
    "Debt/Equity",
    "Deposit Growth 3Yr",
    "Deposits 5Yr",
    "Dil EPS 10Yr",
    "Dil EPS 10Yr CAGR",
    "Dil EPS 3Yr",
    "Dil EPS 3Yr CAGR",
    "Dil EPS 5Yr",
    "Dil EPS 5Yr CAGR",
    "Dividend Yield",
    "EBITDA",
    "EBITDA Fwd 2Yr",
    "EBIT/Interest",
    "Embedded Value",
    "Employees",
    "EPS 3Yr",
    "EPS 5Yr",
    "EPS Fwd 1Yr",
    "EPS Fwd 2Yr",
    "EPS Fwd 2Yr CAGR",
    "EPS LT Growth Est",
    "Estimated Valuation",
    "EV",
    "EV/EBITDA",
    "EV/Gross Profit",
    "EV/Sales",
    "EV/Sales (Total Income)",
    "EV/Total Income",
    "FCF",
    "Gearing Ratio",
    "Gross",
    "Gross Borrowings",
    "Gross NPA",
    "Gross NPA %",
    "Gross NPA Ratio",
    "Interest Income 3Yr",
    "Interest Income 5Yr",
    "Investments",
    "Loan Growth 3Yr",
    "Loans 5Yr",
    "Market Cap",
    "Net",
    "Net Debt",
    "Net Income",
    "Net Income Margin",
    "Net Interest Income 3Yr",
    "Net Interest Margin",
    "Net Loss (FY23)",
    "Net Margin",
    "Net NPA",
    "Net NPA %",
    "Net NPA Ratio",
    "Net Premium 1Yr",
    "Net Premium 3Yr",
    "Net Premium 5Yr",
    "Net Premium Fwd 2Yr",
    "Net Premium Income",
    "Net Profit 3Yr",
    "Net Profit 5Yr",
    "Net Profit Fwd 2Yr",
    "Net Profit Margin",
    "Net Worth",
    "NII 3Yr",
    "NII 5Yr",
    "NII Fwd 2Yr",
    "Operating",
    "Operating Margin",
    "P/Adjusted Book Value",
    "PAT 3Yr",
    "PAT 5Yr",
    "PAT Margin",
    "P/B",
    "P/E",
    "PEG",
    "P/EV",
    "P/FCF",
    "P/NII",
    "Pre-Tax",
    "Pre-Tax Margin",
    "Price/Embedded Value",
    "Price Target",
    "Provision Coverage Ratio",
    "P/S TTM",
    "P/Total Income",
    "Rev 10Yr",
    "Rev 3Yr",
    "Rev 5Yr",
    "Revenue",
    "Revenue 3Yr",
    "Revenue 5Yr",
    "Revenue Fwd 1Yr",
    "Revenue (FY23)",
    "Revenue (Net Interest Income)",
    "Revenue (NII) 5Yr",
    "Revenue (Total Income)",
    "Rev Fwd 2Yr",
    "ROA",
    "ROCE",
    "ROE",
    "ROIC",
    "ROTA",
    "Shares Out",
    "Solvency Ratio",
    "Tier 1 Capital Ratio",
    "Tier 1 CAR",
    "Tier-1 CRAR",
    "Tier 1 Ratio",
    "Total Assets",
    "Total Capital Ratio",
    "Total Capital Ratio (CRAR)",
    "Total Income",
    "Total Income 10Yr",
    "Total Income 10Yr CAGR",
    "Total Income 3Yr",
    "Total Income 3Yr CAGR",
    "Total Income 5Yr",
    "Total Income 5Yr CAGR",
    "Total Income Fwd 2Yr",
    "Total Income Fwd 2Yr CAGR",
    "VNB 1Yr",
]


# Normalize both lists to lowercase and strip spaces for comparison
new_norm = [p.strip() for p in new_parameters]
metrics = [p.strip() for p in metrics]
new_norm+= metrics

sep_norm = {p.lower().strip() for p in separated_params}
new_norm_lower = {p.lower() for p in new_norm}
without_lower = {p.strip() for p in separated_params}
print(len(new_norm_lower),len(new_norm))

# Find items in separated_params not in new_parameters
not_in_new = [p for p in without_lower if p not in new_norm]
not_in_new2 = [p for p in sep_norm if p.lower() not in new_norm_lower]
print(len(not_in_new), len(not_in_new2))
print("Parameters in separated_params not in new_parameters:")
for item in not_in_new2:
    print("-", item)
