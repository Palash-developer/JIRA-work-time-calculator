import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import io

st.set_page_config(page_title="Palash's Bug Day Count Calculator", layout="wide")
st.title("Palash's Bug Day Count Calculator + Summary Dashboard")

st.markdown(""" 
Upload your Excel file → the app will:
- Ignore the time part (only use dates)
- Count **1** if Created = Updated (same day)
- Count only **business days** (Monday–Friday) between different dates
- Overwrite or create the **Day count** column
""")

uploaded_file = st.file_uploader("Choose Excel or CSV file", type=["xlsx", "xls", "csv"])

if uploaded_file is not None:
    try:
        # Read file based on extension
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)

        # Must have these two columns
        if not {'Created', 'Updated'}.issubset(df.columns):
            st.error("Excel must contain 'Created' and 'Updated' columns")
            st.stop()

        # Convert 'Created' and 'Updated' columns to datetime, handling mixed formats
        def parse_mixed_date(date_str):
            """Parse dates that can be in DD-MM-YYYY or YYYY-MM-DD format
            Uses smart detection: if first number > 12, it's DD-MM-YYYY
            """
            if pd.isna(date_str):
                return pd.NaT
            
            # Convert to string if not already
            date_str = str(date_str).strip()
            
            # If it's already a datetime object from pandas, return it
            if isinstance(date_str, pd.Timestamp):
                return date_str
            
            # Remove any timezone info if present
            if 'T' in date_str and '+' in date_str:
                date_str = date_str.split('+')[0].split('T')[0]
            
            # Smart format detection for DD-MM-YYYY vs YYYY-MM-DD
            # Check if it starts with a 4-digit year (YYYY-MM-DD format)
            if len(date_str) >= 4 and date_str[0:4].isdigit() and int(date_str[0:4]) > 1900:
                # Likely YYYY-MM-DD format
                formats = [
                    '%Y-%m-%d %H:%M:%S',      # 2025-10-10 10:46:00
                    '%Y-%m-%d %H:%M',         # 2025-10-10 10:46
                    '%Y-%m-%d',                # 2025-10-10
                    '%Y/%m/%d %H:%M:%S',      # 2025/10/10 10:46:00
                    '%Y/%m/%d %H:%M',         # 2025/10/10 10:46
                    '%Y/%m/%d',               # 2025/10/10
                ]
            else:
                # Try to detect DD-MM-YYYY by checking if first number > 12
                parts = date_str.replace('/', '-').split()[0].split('-')  # Get date part only
                if len(parts) >= 3:
                    try:
                        first_num = int(parts[0])
                        second_num = int(parts[1])
                        # If first number > 12, must be DD-MM-YYYY
                        if first_num > 12:
                            formats = [
                                '%d-%m-%Y %H:%M',          # 13-10-2025 19:51
                                '%d-%m-%Y',                # 13-10-2025
                                '%d/%m/%Y %H:%M',          # 13/10/2025 19:51
                                '%d/%m/%Y',                # 13/10/2025
                            ]
                        # If second number > 12, must be MM-DD-YYYY
                        elif second_num > 12:
                            formats = [
                                '%m-%d-%Y %H:%M',          # 10-13-2025 19:51
                                '%m-%d-%Y',                # 10-13-2025
                                '%m/%d/%Y %H:%M',          # 10/13/2025 19:51
                                '%m/%d/%Y',                # 10/13/2025
                            ]
                        else:
                            # Ambiguous - try DD-MM-YYYY first (more common in your data)
                            formats = [
                                '%d-%m-%Y %H:%M',          # 10-10-2025 19:51
                                '%d-%m-%Y',                # 10-10-2025
                                '%d/%m/%Y %H:%M',          # 10/10/2025 19:51
                                '%d/%m/%Y',                # 10/10/2025
                                '%m-%d-%Y %H:%M',          # 10-10-2025 19:51 (alternative)
                                '%m-%d-%Y',                # 10-10-2025 (alternative)
                            ]
                    except (ValueError, IndexError):
                        # Fallback to all formats
                        formats = [
                            '%d-%m-%Y %H:%M', '%d-%m-%Y',
                            '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d',
                            '%d/%m/%Y %H:%M', '%d/%m/%Y',
                            '%Y/%m/%d %H:%M:%S', '%Y/%m/%d %H:%M', '%Y/%m/%d',
                        ]
                else:
                    # Fallback to all formats
                    formats = [
                        '%d-%m-%Y %H:%M', '%d-%m-%Y',
                        '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d',
                        '%d/%m/%Y %H:%M', '%d/%m/%Y',
                        '%Y/%m/%d %H:%M:%S', '%Y/%m/%d %H:%M', '%Y/%m/%d',
                    ]
            
            # Try parsing with detected formats
            for fmt in formats:
                try:
                    parsed = pd.to_datetime(date_str, format=fmt)
                    # Validate: year should be reasonable (1900-2100)
                    if 1900 <= parsed.year <= 2100:
                        return parsed
                except (ValueError, TypeError, AttributeError):
                    continue
            
            # If all formats fail, try pandas' automatic parsing (last resort)
            try:
                parsed = pd.to_datetime(date_str, errors='coerce')
                if pd.notna(parsed) and 1900 <= parsed.year <= 2100:
                    return parsed
            except:
                pass
            
            return pd.NaT
        
        # Parse dates and handle NaT properly
        created_dates = df['Created'].apply(parse_mixed_date)
        updated_dates = df['Updated'].apply(parse_mixed_date)
        
        # Convert to date strings only for valid dates
        df['Created_date'] = created_dates.dt.strftime('%Y-%m-%d')
        df['Updated_date'] = updated_dates.dt.strftime('%Y-%m-%d')
        
        # Replace 'NaT' strings with actual NaN
        df['Created_date'] = df['Created_date'].replace('NaT', pd.NA)
        df['Updated_date'] = df['Updated_date'].replace('NaT', pd.NA)

        # Remove rows where date couldn't be parsed (very rare)
        invalid = df['Created_date'].isna() | df['Updated_date'].isna()
        if invalid.any():
            st.warning(f"{invalid.sum()} row(s) had unreadable dates and were removed.")
            df = df[~invalid].reset_index(drop=True)

        # Calculate day count exactly like your original file
        def calculate_days(row):
            c = row['Created_date']
            u = row['Updated_date']
            if c == u:
                return 1
            else:
                # busday_count counts valid weekdays in [start, end)
                return np.busday_count(c, u)

        df['Day count'] = df.apply(calculate_days, axis=1)
        
        # Ensure Day count is numeric (convert to int)
        df['Day count'] = pd.to_numeric(df['Day count'], errors='coerce').fillna(0).astype(int)

        # Clean up temporary columns
        df = df.drop(columns=['Created_date', 'Updated_date'])

        # Show result
        st.success("Processing complete!")
        st.dataframe(df, use_container_width=True)

        # Filter based on severity if available
        severity_summary = []
        if 'Severity' in df.columns:
            major_bugs = df[df['Severity'] == 'Major']
            minor_bugs = df[df['Severity'] == 'Minor']
            critical_blocker_bugs = df[df['Severity'].isin(['Critical', 'Blocker'])]

            severity_summary.append({
                "Severity": "Major", 
                "Bug count": len(major_bugs), 
                "Day count": int(major_bugs['Day count'].sum()) if len(major_bugs) > 0 else 0
            })
            severity_summary.append({
                "Severity": "Minor", 
                "Bug count": len(minor_bugs), 
                "Day count": int(minor_bugs['Day count'].sum()) if len(minor_bugs) > 0 else 0
            })
            severity_summary.append({
                "Severity": "Critical/Blocker", 
                "Bug count": len(critical_blocker_bugs), 
                "Day count": int(critical_blocker_bugs['Day count'].sum()) if len(critical_blocker_bugs) > 0 else 0
            })

        # Filter based on priority if available
        priority_summary = []
        if 'Priority' in df.columns:
            highest_high_bugs = df[df['Priority'].isin(['Highest', 'High'])]
            medium_bugs = df[df['Priority'] == 'Medium']
            low_lowest_bugs = df[df['Priority'].isin(['Low', 'Lowest'])]

            priority_summary.append({
                "Priority": "Highest/High", 
                "Bug count": len(highest_high_bugs), 
                "Day count": int(highest_high_bugs['Day count'].sum()) if len(highest_high_bugs) > 0 else 0
            })
            priority_summary.append({
                "Priority": "Medium", 
                "Bug count": len(medium_bugs), 
                "Day count": int(medium_bugs['Day count'].sum()) if len(medium_bugs) > 0 else 0
            })
            priority_summary.append({
                "Priority": "Low/Lowest", 
                "Bug count": len(low_lowest_bugs), 
                "Day count": int(low_lowest_bugs['Day count'].sum()) if len(low_lowest_bugs) > 0 else 0
            })

        # Display Severity and Priority counts in tabular format
        if severity_summary:
            st.subheader("Severity-based Counts")
            severity_df = pd.DataFrame(severity_summary)
            st.table(severity_df)

        if priority_summary:
            st.subheader("Priority-based Counts")
            priority_df = pd.DataFrame(priority_summary)
            st.table(priority_df)

        # Download button for the updated data
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        output.seek(0)

        st.download_button(
            label="Download Updated Excel",
            data=output,
            file_name="day_count_calculated.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"Error: {e}")

else:
    st.info("Please upload an Excel file")
