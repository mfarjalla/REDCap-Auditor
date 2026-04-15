import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="REDCap Auditor", page_icon="🔍", layout="wide")

st.title("REDCap Monthly Audit Comparison")
st.write("Upload last month's Excel file and this month's CSV to compare changes.")

col1, col2 = st.columns(2)

with col1:
    old_file = st.file_uploader("Upload Last Month's Data (Excel/CSV)", type=["xlsx", "csv", "xls"])

with col2:
    new_file = st.file_uploader("Upload This Month's Data (Excel/CSV)", type=["xlsx", "csv", "xls"])

# --- Define Your Coding Book Here ---
# Add any columns and their value mappings below. Both numbers and strings are handled.
CODEBOOK = {
    'Status': {
        0: 'Developmental Mode',
        1: 'Production Mode',
        '0': 'Developmental Mode',
        '1': 'Production Mode'
    }
}
# -----------------------------------

@st.cache_data
def load_data(file):
    if file.name.endswith('.csv'):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)
        
    # Apply the coding book mapping
    for col, mapping in CODEBOOK.items():
        if col in df.columns:
            # We use replace so that unmapped values remain untouched
            df[col] = df[col].replace(mapping)
            
    return df

if old_file and new_file:
    with st.spinner("Analyzing changes..."):
        try:
            df_old = load_data(old_file)
            df_new = load_data(new_file)
            
            # Check if PID exists
            if 'PID' not in df_old.columns or 'PID' not in df_new.columns:
                st.error("Error: Both files must contain a 'PID' column for comparison.")
            else:
                # Store original dataframes for reference, but create copies for indexing
                old_data = df_old.copy()
                new_data = df_new.copy()
                
                # Convert PID to string to ensure matching works properly
                old_data['PID'] = old_data['PID'].astype(str)
                new_data['PID'] = new_data['PID'].astype(str)
                
                # Drop rows where PID is NaN
                old_data = old_data.dropna(subset=['PID'])
                new_data = new_data.dropna(subset=['PID'])
                
                old_data.set_index('PID', inplace=True)
                new_data.set_index('PID', inplace=True)
                
                common_pids = old_data.index.intersection(new_data.index)
                new_pids = new_data.index.difference(old_data.index)
                deleted_pids = old_data.index.difference(new_data.index)
                
                st.success(f"Analysis Complete! Found {len(new_pids)} new records, {len(deleted_pids)} deleted records, and {len(common_pids)} existing records to compare.")
                
                # Show some metrics
                m1, m2, m3 = st.columns(3)
                m1.metric("New Records", len(new_pids))
                m2.metric("Deleted Records", len(deleted_pids))
                m3.metric("Compared Records", len(common_pids))

                # We will output the new data with highlights
                df_combined = new_data.copy()
                df_combined['Audit Flag'] = ''
                
                # Calculate changes count without side effects in styler
                changes_count = 0
                for pid in common_pids:
                    # Check for Dev Mode flags
                    status_new = str(new_data.loc[pid, 'Status']).strip() if 'Status' in new_data.columns else ''
                    if status_new in ['Developmental Mode', '0', '0.0']:
                        if 'Total Records' in new_data.columns and 'Total Records' in old_data.columns:
                            val_old = old_data.loc[pid, 'Total Records']
                            val_new = new_data.loc[pid, 'Total Records']
                            if pd.notna(val_old) and pd.notna(val_new):
                                try:
                                    if float(val_new) > float(val_old):
                                        df_combined.loc[pid, 'Audit Flag'] = '⚠️ Data Collection in Dev Mode'
                                except ValueError:
                                    pass

                    for col in new_data.columns:
                        if col in old_data.columns:
                            val_old = old_data.loc[pid, col]
                            val_new = new_data.loc[pid, col]
                            if pd.isna(val_old) and pd.isna(val_new):
                                continue
                            if str(val_old) != str(val_new):
                                changes_count += 1
                
                for pid in new_pids:
                    # Check for Dev Mode flags in completely new projects
                    status_new = str(new_data.loc[pid, 'Status']).strip() if 'Status' in new_data.columns else ''
                    if status_new in ['Developmental Mode', '0', '0.0']:
                        if 'Total Records' in new_data.columns:
                            val_new = new_data.loc[pid, 'Total Records']
                            if pd.notna(val_new):
                                try:
                                    if float(val_new) > 0:
                                        df_combined.loc[pid, 'Audit Flag'] = '⚠️ Data Collection in Dev Mode'
                                except ValueError:
                                    pass

                def highlight_diff(data):
                    # Initialize empty dataframe for styles (same shape as output)
                    is_diff = pd.DataFrame('', index=data.index, columns=data.columns)
                    
                    # Yellow background for changed cells
                    changed_style = 'background-color: #ffe066; color: black;'
                    # Green background for completely new rows
                    new_style = 'background-color: #8ce99a; color: black;'
                    # Red background for Audit violations
                    flag_style = 'background-color: #ff6b6b; color: white; font-weight: bold;'
                    
                    for pid in common_pids:
                        for col in data.columns:
                            # Skip highlighting cell change if the col is Audit Flag, we handle that later
                            if col == 'Audit Flag':
                                continue
                            # Only compare if the column existed in the old file too
                            if col in old_data.columns:
                                val_old = old_data.loc[pid, col]
                                val_new = data.loc[pid, col]
                                
                                # Handle NaNs properly so we don't flag NaN -> NaN as a change
                                if pd.isna(val_old) and pd.isna(val_new):
                                    continue
                                    
                                # If the values are different, highlight
                                if str(val_old) != str(val_new):
                                    is_diff.loc[pid, col] = changed_style
                                    
                    for pid in new_pids:
                        is_diff.loc[pid, :] = new_style
                        
                    # Apply Dev Mode Audit violation styles
                    for pid in data.index:
                        if 'Audit Flag' in data.columns and data.loc[pid, 'Audit Flag'] != '':
                            is_diff.loc[pid, 'Audit Flag'] = flag_style
                            if 'Total Records' in is_diff.columns:
                                is_diff.loc[pid, 'Total Records'] = flag_style
                                
                    return is_diff

                # Apply styling
                styled_df = df_combined.style.apply(highlight_diff, axis=None)
                
                # Check for any audit violations
                audit_flags = df_combined[df_combined['Audit Flag'] != '']
                if not audit_flags.empty:
                    st.error(f"🚨 **High Priority**: Found {len(audit_flags)} project(s) in Development Mode with an increase in Total Records!")
                    
                    st.write("#### Dev Mode Violations")
                    st.write("These projects are in Development Mode but show an increase in records since the last report. Please review.")
                    
                    focus_cols = ['Project Title', 'Status', 'Total Records', 'Purpose', 'Usernames', 'Audit Flag']
                    display_cols = [col for col in focus_cols if col in audit_flags.columns]
                    
                    # Also include PID which is currently the index.
                    st.dataframe(audit_flags[display_cols], use_container_width=True)
                    st.divider()

                if changes_count > 0:
                    st.info(f"Detected **{changes_count}** specific cell changes across all records.")
                else:
                    st.info("No cell changes detected in the common records.")

                st.write("### Data Preview")
                st.write("*(Highlights might not render perfectly in your web browser, but they will be fully visible in the downloaded Excel file.)*")
                # Reset index for display so PID shows up as a column in the preview
                st.dataframe(styled_df, use_container_width=True)

                # Generate Excel buffer
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    # Write the styled dataframe to Excel
                    styled_df.to_excel(writer, sheet_name='Audit Report')
                excel_data = output.getvalue()
                
                st.download_button(
                    label="📥 Download Highlighted Audit Report (Excel)",
                    data=excel_data,
                    file_name="REDCap_Audit_Report.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    type="primary"
                )
                
        except Exception as e:
            st.error(f"An error occurred while processing the files. Ensure the formats are correct and 'PID' column exists.\n\nError Details: {e}")
