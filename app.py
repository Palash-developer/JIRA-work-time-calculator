import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io

st.set_page_config(page_title="QC Metric Calculator", layout="wide")
st.title("QC Metric Calculator")
st.markdown("### One upload, zero hassle – Palash's automation takes care of the rest.")

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

        # Convert 'Created' and 'Updated' columns to datetime
        # Handle DD-MM-YY format (day-month-year with 2-digit year)
        def parse_date_dd_mm_yy(date_val):
            """Parse dates in DD-MM-YY format (e.g., 11-12-25 = 11 Dec 2025)"""
            if pd.isna(date_val):
                return pd.NaT
            
            if isinstance(date_val, pd.Timestamp):
                return date_val
            
            date_str = str(date_val).strip()
            
            # First, try to parse DD-MM-YY format explicitly (most common in your data)
            import re
            # Pattern: DD-MM-YY HH:MM or DD-MM-YY
            match = re.match(r'^(\d{1,2})-(\d{1,2})-(\d{2})(\s+(\d{1,2}):(\d{2}))?', date_str)
            if match:
                dd, mm, yy = match.groups()[0], match.groups()[1], match.groups()[2]
                time_part = match.groups()[4] if match.groups()[4] and match.groups()[5] else ''
                min_part = match.groups()[5] if match.groups()[5] else ''
                
                # Convert 2-digit year: 00-50 -> 2000-2050, 51-99 -> 1951-1999
                year = int(yy)
                if year <= 50:
                    year = 2000 + year
                else:
                    year = 1900 + year
                
                # Format: YYYY-MM-DD HH:MM
                if time_part:
                    fixed_date = f"{year}-{mm.zfill(2)}-{dd.zfill(2)} {time_part.zfill(2)}:{min_part}"
                else:
                    fixed_date = f"{year}-{mm.zfill(2)}-{dd.zfill(2)}"
                
                parsed = pd.to_datetime(fixed_date, errors='coerce')
                if pd.notna(parsed) and 1900 <= parsed.year <= 2100:
                    return parsed
            
            # Fallback: Try pandas parsing with dayfirst=True
            parsed = pd.to_datetime(date_str, errors='coerce', dayfirst=True)
            if pd.notna(parsed) and 1900 <= parsed.year <= 2100:
                return parsed
            
            return pd.NaT
        
        # Parse dates in DD-MM-YY format
        created_datetime = df['Created'].apply(parse_date_dd_mm_yy)
        updated_datetime = df['Updated'].apply(parse_date_dd_mm_yy)
        
        # Remove rows where date couldn't be parsed
        invalid = created_datetime.isna() | updated_datetime.isna()
        if invalid.any():
            st.warning(f"{invalid.sum()} row(s) had unreadable dates and were removed.")
            df = df[~invalid].reset_index(drop=True)
            created_datetime = created_datetime[~invalid].reset_index(drop=True)
            updated_datetime = updated_datetime[~invalid].reset_index(drop=True)
        
        # Extract only the date part (slice timestamps to dates, ignore time)
        # Convert to date strings in 'YYYY-MM-DD' format for business day calculation
        df['Created_date'] = created_datetime.dt.strftime('%Y-%m-%d')
        df['Updated_date'] = updated_datetime.dt.strftime('%Y-%m-%d')

        # Calculate day count - slice timestamps to dates only, exclude weekends
        def calculate_days(row):
            c = row['Created_date']
            u = row['Updated_date']
            
            # Skip if dates are invalid
            if pd.isna(c) or pd.isna(u) or c == 'NaT' or u == 'NaT' or c == 'nan' or u == 'nan':
                return 0
            
            # Convert to string and ensure format is YYYY-MM-DD
            c_str = str(c)
            u_str = str(u)
            
            if c_str == u_str:
                return 1
            else:
                try:
                    # busday_count counts valid weekdays (Monday-Friday) in [start, end)
                    # It excludes the end date, so we need to add 1 day to include it
                    # Count from start to end+1 to include the end date if it's a business day
                    end_date = pd.to_datetime(u_str)
                    end_plus_one = (end_date + timedelta(days=1)).strftime('%Y-%m-%d')
                    
                    # Count business days from start to end+1 (this includes the end date)
                    count = np.busday_count(c_str, end_plus_one)
                    # Subtract 1 day for different dates (as per requirement)
                    count = max(1, count - 1)  # Ensure at least 1 day
                    return count
                except (ValueError, TypeError) as e:
                    return 0

        df['Day count'] = df.apply(calculate_days, axis=1)
        
        # Ensure Day count is numeric (convert to int)
        df['Day count'] = pd.to_numeric(df['Day count'], errors='coerce').fillna(0).astype(int)
        
        # Add Hours count column (Day count * 8)
        df['Hours count'] = df['Day count'] * 8

        # Clean up temporary columns
        df = df.drop(columns=['Created_date', 'Updated_date'])

        # Filter by Status: only consider rows with exact match 'Done' or 'Merge Request'
        if 'Status' in df.columns:
            initial_count = len(df)
            df = df[df['Status'].isin(['Done', 'Merge Request'])].reset_index(drop=True)
            filtered_count = len(df)
            if initial_count != filtered_count:
                st.info(f"Filtered by Status: {initial_count - filtered_count} row(s) excluded (Status not 'Done' or 'Merge Request'). {filtered_count} row(s) remaining.")
        else:
            st.warning("No 'Status' column found. All rows will be included in calculations.")

        # Show result
        st.success("Processing complete!")
        st.dataframe(df, use_container_width=True)

        # Filter based on severity if available (check both possible column names)
        severity_summary = []
        severity_col = None
        if 'Severity' in df.columns:
            severity_col = 'Severity'
        elif 'Custom field (Severity)' in df.columns:
            severity_col = 'Custom field (Severity)'
        
        # Initialize variables to hold severity and priority values
        major_bug_count = 0
        major_day_count = 0
        major_hours_count = 0
        minor_bug_count = 0
        minor_day_count = 0
        minor_hours_count = 0
        critical_blocker_bug_count = 0
        critical_blocker_day_count = 0
        critical_blocker_hours_count = 0
        
        highest_high_bug_count = 0
        highest_high_day_count = 0
        highest_high_hours_count = 0
        medium_bug_count = 0
        medium_day_count = 0
        medium_hours_count = 0
        low_lowest_bug_count = 0
        low_lowest_day_count = 0
        low_lowest_hours_count = 0
        
        if severity_col:
            major_bugs = df[df[severity_col] == 'Major']
            minor_bugs = df[df[severity_col] == 'Minor']
            critical_blocker_bugs = df[df[severity_col].isin(['Critical', 'Blocker'])]
            
            # Store Major values
            major_bug_count = len(major_bugs)
            major_day_count = int(major_bugs['Day count'].sum()) if len(major_bugs) > 0 else 0
            major_hours_count = int(major_bugs['Hours count'].sum()) if len(major_bugs) > 0 else 0
            
            # Store Minor values
            minor_bug_count = len(minor_bugs)
            minor_day_count = int(minor_bugs['Day count'].sum()) if len(minor_bugs) > 0 else 0
            minor_hours_count = int(minor_bugs['Hours count'].sum()) if len(minor_bugs) > 0 else 0
            
            # Store Critical/Blocker values
            critical_blocker_bug_count = len(critical_blocker_bugs)
            critical_blocker_day_count = int(critical_blocker_bugs['Day count'].sum()) if len(critical_blocker_bugs) > 0 else 0
            critical_blocker_hours_count = int(critical_blocker_bugs['Hours count'].sum()) if len(critical_blocker_bugs) > 0 else 0

            severity_summary.append({
                "Severity": "Major", 
                "Bug count": major_bug_count, 
                "Day count": major_day_count,
                "Hours count": major_hours_count
            })
            severity_summary.append({
                "Severity": "Minor", 
                "Bug count": minor_bug_count, 
                "Day count": minor_day_count,
                "Hours count": minor_hours_count
            })
            severity_summary.append({
                "Severity": "Critical/Blocker", 
                "Bug count": critical_blocker_bug_count, 
                "Day count": critical_blocker_day_count,
                "Hours count": critical_blocker_hours_count
            })

        # Filter based on priority if available
        priority_summary = []
        if 'Priority' in df.columns:
            highest_high_bugs = df[df['Priority'].isin(['Highest', 'High'])]
            medium_bugs = df[df['Priority'] == 'Medium']
            low_lowest_bugs = df[df['Priority'].isin(['Low', 'Lowest'])]
            
            # Store Highest/High values
            highest_high_bug_count = len(highest_high_bugs)
            highest_high_day_count = int(highest_high_bugs['Day count'].sum()) if len(highest_high_bugs) > 0 else 0
            highest_high_hours_count = int(highest_high_bugs['Hours count'].sum()) if len(highest_high_bugs) > 0 else 0
            
            # Store Medium values
            medium_bug_count = len(medium_bugs)
            medium_day_count = int(medium_bugs['Day count'].sum()) if len(medium_bugs) > 0 else 0
            medium_hours_count = int(medium_bugs['Hours count'].sum()) if len(medium_bugs) > 0 else 0
            
            # Store Low/Lowest values
            low_lowest_bug_count = len(low_lowest_bugs)
            low_lowest_day_count = int(low_lowest_bugs['Day count'].sum()) if len(low_lowest_bugs) > 0 else 0
            low_lowest_hours_count = int(low_lowest_bugs['Hours count'].sum()) if len(low_lowest_bugs) > 0 else 0

            priority_summary.append({
                "Priority": "Highest/High", 
                "Bug count": highest_high_bug_count, 
                "Day count": highest_high_day_count,
                "Hours count": highest_high_hours_count
            })
            priority_summary.append({
                "Priority": "Medium", 
                "Bug count": medium_bug_count, 
                "Day count": medium_day_count,
                "Hours count": medium_hours_count
            })
            priority_summary.append({
                "Priority": "Low/Lowest", 
                "Bug count": low_lowest_bug_count, 
                "Day count": low_lowest_day_count,
                "Hours count": low_lowest_hours_count
            })

        # Display Severity and Priority counts in tabular format (with dropdown design)
        if severity_summary:
            severity_df = pd.DataFrame(severity_summary)
            with st.expander("📈 Severity-based Counts", expanded=False):
                st.dataframe(severity_df, use_container_width=True, hide_index=True)

        if priority_summary:
            priority_df = pd.DataFrame(priority_summary)
            with st.expander("📊 Priority-based Counts", expanded=False):
                st.dataframe(priority_df, use_container_width=True, hide_index=True)

        # Calculate metrics for QA Metric Calculator using stored variables
        # Bug count: actual row count from Excel
        total_bugs = len(df)
        total_hours = int(df['Hours count'].sum()) if 'Hours count' in df.columns else 0
        total_day_count = int(df['Day count'].sum()) if 'Day count' in df.columns else 0
        
        # Display all variable values in UI tables (compact design)
        st.markdown("---")
        with st.expander("📊 Calculation Variables Summary", expanded=False):
            # Use columns for compact side-by-side layout
            col1, col2, col3 = st.columns(3)
            
            with col1:
                # SEVERITY-BASED VARIABLES table
                severity_vars_data = {
                    "Variable": [
                        "major_bug_count",
                        "major_day_count",
                        "major_hours_count",
                        "minor_bug_count",
                        "minor_day_count",
                        "minor_hours_count",
                        "critical_blocker_bug_count",
                        "critical_blocker_day_count",
                        "critical_blocker_hours_count"
                    ],
                    "Value": [
                        major_bug_count,
                        major_day_count,
                        major_hours_count,
                        minor_bug_count,
                        minor_day_count,
                        minor_hours_count,
                        critical_blocker_bug_count,
                        critical_blocker_day_count,
                        critical_blocker_hours_count
                    ]
                }
                severity_vars_df = pd.DataFrame(severity_vars_data)
                st.markdown("**SEVERITY-BASED:**")
                st.dataframe(severity_vars_df, use_container_width=True, hide_index=True)
            
            with col2:
                # PRIORITY-BASED VARIABLES table
                priority_vars_data = {
                    "Variable": [
                        "highest_high_bug_count",
                        "highest_high_day_count",
                        "highest_high_hours_count",
                        "medium_bug_count",
                        "medium_day_count",
                        "medium_hours_count",
                        "low_lowest_bug_count",
                        "low_lowest_day_count",
                        "low_lowest_hours_count"
                    ],
                    "Value": [
                        highest_high_bug_count,
                        highest_high_day_count,
                        highest_high_hours_count,
                        medium_bug_count,
                        medium_day_count,
                        medium_hours_count,
                        low_lowest_bug_count,
                        low_lowest_day_count,
                        low_lowest_hours_count
                    ]
                }
                priority_vars_df = pd.DataFrame(priority_vars_data)
                st.markdown("**PRIORITY-BASED:**")
                st.dataframe(priority_vars_df, use_container_width=True, hide_index=True)
            
            with col3:
                # TOTAL CALCULATED VALUES table
                total_vars_data = {
                    "Variable": [
                        "total_bugs",
                        "total_day_count"
                    ],
                    "Value": [
                        total_bugs,
                        total_day_count
                    ]
                }
                total_vars_df = pd.DataFrame(total_vars_data)
                st.markdown("**TOTAL VALUES:**")
                st.dataframe(total_vars_df, use_container_width=True, hide_index=True)
        
        # Store calculated values in session state for QA Metric Calculator
        # Mapping matches the image exactly using stored variables:
        # - Critical = Critical/Blocker bug count from Severity table
        # - Major = Major bug count from Severity table
        # - High Hours/Count = Highest/High hours/bug count from Priority table
        # - Medium Hours/Count = Medium hours/bug count from Priority table
        # - Low Hours/Count = Low/Lowest hours/bug count from Priority table
        st.session_state.qa_metrics = {
            'pages': 0,  # Manual input
            'bugs': total_bugs,  # Actual row count from Excel
            'devHrs': float(total_hours),
            'testHrs': float(total_hours),
            'critical': critical_blocker_bug_count,  # From Severity: Critical/Blocker bug count
            'major': major_bug_count,  # From Severity: Major bug count
            'highHrs': float(highest_high_hours_count),  # From Priority: Highest/High hours count
            'highCount': highest_high_bug_count,  # From Priority: Highest/High bug count
            'medHrs': float(medium_hours_count),  # From Priority: Medium hours count
            'medCount': medium_bug_count,  # From Priority: Medium bug count
            'lowHrs': float(low_lowest_hours_count),  # From Priority: Low/Lowest hours count
            'lowCount': low_lowest_bug_count  # From Priority: Low/Lowest bug count
        }
        
        # Store the calculated variables for use in calculations
        st.session_state.calculated_vars = {
            'total_bugs': total_bugs,  # Actual row count from Excel
            'critical_blocker_bug_count': critical_blocker_bug_count,
            'major_bug_count': major_bug_count,
            'highest_high_hours_count': highest_high_hours_count,
            'highest_high_bug_count': highest_high_bug_count,
            'medium_hours_count': medium_hours_count,
            'medium_bug_count': medium_bug_count,
            'low_lowest_hours_count': low_lowest_hours_count,
            'low_lowest_bug_count': low_lowest_bug_count
        }
        
        # Show success message that fields are auto-filled
        st.success("✅ QA Metric Calculator fields have been auto-filled with calculated values!")
        
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

# QA Metric Calculator Section
st.markdown("---")
st.subheader("📊 QA Metric Calculator")

# Initialize session state if not exists
if 'qa_metrics' not in st.session_state:
    st.session_state.qa_metrics = {
        'pages': 0,
        'bugs': 0,
        'devHrs': 0.0,
        'testHrs': 0.0,
        'critical': 0,
        'major': 0,
        'highHrs': 0.0,
        'highCount': 0,
        'medHrs': 0.0,
        'medCount': 0,
        'lowHrs': 0.0,
        'lowCount': 0
    }

if 'calculated_vars' not in st.session_state:
    st.session_state.calculated_vars = {
        'critical_blocker_bug_count': 0,
        'major_bug_count': 0,
        'highest_high_hours_count': 0,
        'highest_high_bug_count': 0,
        'medium_hours_count': 0,
        'medium_bug_count': 0,
        'low_lowest_hours_count': 0,
        'low_lowest_bug_count': 0
    }

# Get values from session state (auto-filled from file upload)
qa = st.session_state.qa_metrics

# Initialize calculation results in session state
if 'qa_calculated' not in st.session_state:
    st.session_state.qa_calculated = False
    st.session_state.qa_results = []

# Calculate metrics function
def calculate_qa_metrics(page_story_count, dev_hrs, test_hrs):
    metrics = []
    
    # Get stored calculated variables from session state
    calc_vars = st.session_state.get('calculated_vars', {})
    total_bugs = calc_vars.get('total_bugs', 0)  # Actual row count from Excel
    critical_blocker_bug_count = calc_vars.get('critical_blocker_bug_count', 0)
    major_bug_count = calc_vars.get('major_bug_count', 0)
    highest_high_hours_count = calc_vars.get('highest_high_hours_count', 0)
    highest_high_bug_count = calc_vars.get('highest_high_bug_count', 0)
    medium_hours_count = calc_vars.get('medium_hours_count', 0)
    medium_bug_count = calc_vars.get('medium_bug_count', 0)
    low_lowest_hours_count = calc_vars.get('low_lowest_hours_count', 0)
    low_lowest_bug_count = calc_vars.get('low_lowest_bug_count', 0)
    
    # Defect Density (Critical) - page_story_count && critical ? (critical_blocker_bug_count / page_story_count).toFixed(2) : "-"
    val = (critical_blocker_bug_count / page_story_count) if (page_story_count and critical_blocker_bug_count) else "-"
    result = f"{val:.2f}" if isinstance(val, (int, float)) else val
    metrics.append({"name": "Defect Density (Critical)", "value": result})
    
    # Defect Density (Total) - page_story_count && total_bugs ? (total_bugs / page_story_count).toFixed(2) : "-"
    val = (total_bugs / page_story_count) if (page_story_count and total_bugs) else "-"
    result = f"{val:.2f}" if isinstance(val, (int, float)) else val
    metrics.append({"name": "Defect Density (Total)", "value": result})
    
    # MTFB - High (hrs) - highHrs && highCount ? (highest_high_hours_count / highest_high_bug_count).toFixed(2) : "-"
    val = (highest_high_hours_count / highest_high_bug_count) if (highest_high_hours_count and highest_high_bug_count) else "-"
    result = f"{val:.2f}" if isinstance(val, (int, float)) else val
    metrics.append({"name": "MTFB - High (hrs)", "value": result})
    
    # MTFB - Medium (hrs) - medHrs && medCount ? (medium_hours_count / medium_bug_count).toFixed(2) : "-"
    val = (medium_hours_count / medium_bug_count) if (medium_hours_count and medium_bug_count) else "-"
    result = f"{val:.2f}" if isinstance(val, (int, float)) else val
    metrics.append({"name": "MTFB - Medium (hrs)", "value": result})
    
    # MTFB - Low (hrs) - lowHrs && lowCount ? (low_lowest_hours_count / low_lowest_bug_count).toFixed(2) : "-"
    val = (low_lowest_hours_count / low_lowest_bug_count) if (low_lowest_hours_count and low_lowest_bug_count) else "-"
    result = f"{val:.2f}" if isinstance(val, (int, float)) else val
    metrics.append({"name": "MTFB - Low (hrs)", "value": result})
    
    # Severity Ratio (Critical) % - total_bugs && critical ? ((critical_blocker_bug_count / total_bugs) * 100).toFixed(2) + "%" : "-"
    val = ((critical_blocker_bug_count / total_bugs) * 100) if (total_bugs and critical_blocker_bug_count) else "-"
    result = f"{val:.2f}%" if isinstance(val, (int, float)) else val
    metrics.append({"name": "Severity Ratio (Critical) %", "value": result})
    
    # Severity Ratio (Major) % - total_bugs && major ? ((major_bug_count / total_bugs) * 100).toFixed(2) + "%" : "-"
    val = ((major_bug_count / total_bugs) * 100) if (total_bugs and major_bug_count) else "-"
    result = f"{val:.2f}%" if isinstance(val, (int, float)) else val
    metrics.append({"name": "Severity Ratio (Major) %", "value": result})
    
    # Defect Rate - total_bugs && devHrs && testHrs ? (total_bugs / (Number(devHrs) + Number(testHrs))).toFixed(2) : "-"
    val = (total_bugs / (float(dev_hrs) + float(test_hrs))) if (total_bugs and dev_hrs and test_hrs) else "-"
    result = f"{val:.2f}" if isinstance(val, (int, float)) else val
    metrics.append({"name": "Defect Rate", "value": result})
    
    # Defect Detection Rate - total_bugs && testHrs ? (total_bugs / testHrs).toFixed(2) : "-"
    val = (total_bugs / test_hrs) if (total_bugs and test_hrs) else "-"
    result = f"{val:.2f}" if isinstance(val, (int, float)) else val
    metrics.append({"name": "Defect Detection Rate", "value": result})
    
    return metrics

# Side-by-side layout: Input fields on left, Results on right
left_col, right_col = st.columns(2)

with left_col:
    st.markdown("#### Input Fields")
    
    # Use text_input to avoid +/- buttons, then validate and convert
    page_story_count_str = st.text_input(
        "Pages/Stories [Count]", 
        value=str(int(qa.get('pages', 0))), 
        key="page_story_count_input",
        help="Enter a non-negative integer"
    )
    # Validate and convert to int
    try:
        page_story_count = max(0, int(float(page_story_count_str))) if page_story_count_str else 0
    except (ValueError, TypeError):
        page_story_count = 0
        st.warning("Pages/Stories must be a valid number. Using 0.")
    
    dev_hrs_str = st.text_input(
        "Development Hours [hrs]", 
        value=str(float(qa['devHrs'])), 
        key="dev_hrs_input",
        help="Enter a non-negative number"
    )
    # Validate and convert to float
    try:
        dev_hrs = max(0.0, float(dev_hrs_str)) if dev_hrs_str else 0.0
    except (ValueError, TypeError):
        dev_hrs = 0.0
        st.warning("Development Hours must be a valid number. Using 0.0.")
    
    test_hrs_str = st.text_input(
        "Testing Hours [hrs]", 
        value=str(float(qa['testHrs'])), 
        key="test_hrs_input",
        help="Enter a non-negative number"
    )
    # Validate and convert to float
    try:
        test_hrs = max(0.0, float(test_hrs_str)) if test_hrs_str else 0.0
    except (ValueError, TypeError):
        test_hrs = 0.0
        st.warning("Testing Hours must be a valid number. Using 0.0.")
    
    # Calculate button
    if st.button("Calculate Metrics", type="primary", use_container_width=True):
        st.session_state.qa_calculated = True
        st.session_state.qa_results = calculate_qa_metrics(page_story_count, dev_hrs, test_hrs)

with right_col:
    st.markdown("#### Calculated Metrics")
    
    if st.session_state.qa_calculated and st.session_state.qa_results:
        # Create a DataFrame for better display 
        metrics_df = pd.DataFrame(st.session_state.qa_results)
        metrics_df.columns = ["Metric Name", "Value"]
        st.table(metrics_df)
    else:
        st.info("Enter values and click 'Calculate Metrics' to see results.")

# Footer with copyright notice
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: gray; padding: 20px;'>© 2025 All rights reserved by Palash Dutta Banik</div>",
    unsafe_allow_html=True
)

