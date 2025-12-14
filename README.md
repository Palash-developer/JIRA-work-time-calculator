🐞 Palash’s Bug Day Count Calculator & Summary Dashboard

A Streamlit-based dashboard to calculate bug resolution day counts and generate severity- and priority-wise summaries from Excel or CSV files.

This tool is designed for QA, testing, and defect tracking analysis, handling mixed date formats and business-day calculations automatically.

✨ Features

📂 Upload Excel (.xlsx, .xls) or CSV files

📅 Automatically ignores time and works with dates only

🧮 Calculates Day Count

Same Created & Updated date → 1 day

Different dates → Business days only (Mon–Fri)

🔁 Overwrites or creates a Day count column

📊 Summary tables:

Severity-based (Major, Minor, Critical/Blocker)

Priority-based (Highest/High, Medium, Low/Lowest)

⬇️ Download processed data as Excel

🧠 Smart handling of mixed date formats:

DD-MM-YYYY

YYYY-MM-DD

With or without time

📁 Required Columns

Your input file must contain:

Column Name Description
Created Bug created date
Updated Bug updated / resolved date

Optional (for summaries):

Severity

Priority

🚀 How to Run Locally
1️⃣ Clone the repository
git clone https://github.com/your-username/bug-day-count-calculator.git
cd bug-day-count-calculator

2️⃣ Install dependencies
pip install -r requirements.txt

3️⃣ Run the Streamlit app
streamlit run app.py

The app will open automatically in your browser.

📦 Requirements
streamlit
pandas
numpy
openpyxl

☁️ Free Hosting Options

This app can be hosted 100% free on:

✅ Streamlit Community Cloud (recommended)

✅ Render

✅ Hugging Face Spaces

👉 Just connect your GitHub repo and deploy.

🧪 Business Logic (Day Count Rules)
Scenario Day Count
Created = Updated 1
Different dates Business days only (Mon–Fri)
Weekends Excluded

Uses:

numpy.busday_count()

📊 Output

Updated dataset with Day count

Severity-wise and Priority-wise summary tables

Downloadable Excel output

🧑‍💻 Author

Palash Dutta Banik
QA | Mobile & Web Automation | Security Testing | Performance Testing | Building Apps

If you want, I can also:

Add badges (Python, Streamlit, License)

Create a one-click Streamlit Cloud deploy guide

Optimize the app for large Excel files

Just say the word 👍
