import streamlit as st
import pandas as pd
import numpy as np
import io
import os
import plotly.express as px

st.set_page_config(page_title="REDCap Auditor", page_icon="", layout="wide")

# Print to PDF Hidden Elements CSS
st.markdown("""
<style>
@media print {
  [data-testid="stSidebar"] { display: none !important; }
  [data-testid="stFileUploader"] { display: none !important; }
  .stDownloadButton { display: none !important; }
  .stAlert { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
}
</style>
""", unsafe_allow_html=True)

# Check for a logo file to display centered at the top
logo_path = None
if os.path.exists("logo.png"):
  logo_path = "logo.png"
elif os.path.exists("logo.jpg"):
  logo_path = "logo.jpg"
elif os.path.exists("logo.jpeg"):
  logo_path = "logo.jpeg"

if logo_path:
  # Use columns to enforce center alignment
  # Changing the ratio (e.g., [1, 1, 1] vs [1, 2, 1]) adjusts the logo size
  lcol1, lcol2, lcol3 = st.columns([1, 1, 1])
  with lcol2:
    st.image(logo_path, use_container_width=True)

st.title("REDCap Monthly Audit Comparison")
st.write("Upload last month's Excel file and this month's CSV to compare changes.")

with st.expander("Instructions for Conducting the Audit", expanded=True):
  st.markdown("""
  **This Month's Data**
  1. Log into REDCap and Navigate to the Control Center.
  2. Scroll the submenu labelled "External Modules"
  3. Click on "Admin Dashboard"
  4. Click on "Users by Project"
  5. Click on "Export: CSV"to download the current CSV file of REDCap Projects
  6. Upload the file to "Upload This Month's Data"

  <u>**Last Month's Data**</u><br>
  1. Upload the CSV from the last month to the first upload field
  """, unsafe_allow_html=True)

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
    2: 'Inactive/Archived',
    '0': 'Developmental Mode',
    '1': 'Production Mode',
    '2': 'Inactive/Archived'
  },
  'Purpose': {
    0: 'Practice/Just For Fun',
    1: 'Other',
    2: 'Research',
    3: 'Quality Improvement',
    4: 'Operational Support',
    '0': 'Practice/Just For Fun',
    '1': 'Other',
    '2': 'Research',
    '3': 'Quality Improvement',
    '4': 'Operational Support'
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
      if 'PID'not in df_old.columns or 'PID'not in df_new.columns:
        st.error("Error: Both files must contain a 'PID'column for comparison.")
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
        
        # Identify spam generators
        spam_users_counts = {}
        for pid in new_pids:
          users_str = str(new_data.loc[pid, 'Usernames']).strip() if 'Usernames'in new_data.columns else ''
          if users_str and users_str != 'nan':
            for u in users_str.split(';'):
              u = u.strip()
              if u:
                spam_users_counts[u] = spam_users_counts.get(u, 0) + 1
        
        # Track newly archived 
        newly_archived = 0
        for pid in common_pids:
          s_old = str(old_data.loc[pid, 'Status']).strip() if 'Status'in old_data.columns else ''
          s_new = str(new_data.loc[pid, 'Status']).strip() if 'Status'in new_data.columns else ''
          if s_old != s_new and s_new in ['Inactive/Archived', '2', '2.0']:
            newly_archived += 1
            
        st.success(f"Analysis Complete! Found {len(new_pids)} new records, {len(deleted_pids)} deleted records, and {len(common_pids)} existing records to compare.")
        
        # Show some metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("New Records", len(new_pids))
        m2.metric("Deleted Records", len(deleted_pids))
        m3.metric("Compared Records", len(common_pids))
        m4.metric("Newly Archived", newly_archived)

        st.write("### Executive Dashboard")
        try:
          col_chart1, col_chart2 = st.columns(2)
          
          with col_chart1:
            if 'Purpose'in new_data.columns:
              purpose_dist = new_data['Purpose'].value_counts().reset_index()
              purpose_dist.columns = ['Purpose', 'Count']
              fig_pie = px.pie(purpose_dist, values='Count', names='Purpose', title='Project Purpose Distribution', hole=0.4)
              st.plotly_chart(fig_pie, use_container_width=True)
              
          with col_chart2:
            if 'Status'in new_data.columns:
              status_dist = new_data['Status'].value_counts().reset_index()
              status_dist.columns = ['Status', 'Count']
              fig_bar = px.bar(status_dist, x='Status', y='Count', title='Project Status Overview', color='Status')
              st.plotly_chart(fig_bar, use_container_width=True)
              
          if 'Total Records'in new_data.columns:
            tr_data = new_data.copy()
            tr_data['Total Records'] = pd.to_numeric(tr_data['Total Records'], errors='coerce')
            
            # Histogram
            fig_hist = px.histogram(tr_data, x="Total Records", nbins=50, title="Data Volume Distribution")
            st.plotly_chart(fig_hist, use_container_width=True)
            
            # Leaderboards
            with st.expander("Server Leaderboards (Top 15 Largest Projects)", expanded=False):
              # Exclude practice projects if purpose is mapped
              non_practice = tr_data[tr_data['Purpose'] != 'Practice/Just For Fun'] if 'Purpose'in tr_data.columns else tr_data
              top_15 = non_practice.sort_values(by='Total Records', ascending=False).head(15)
              disp_cols = [c for c in ['Project Title', 'Status', 'Total Records', 'Purpose', 'Usernames'] if c in top_15.columns]
              st.dataframe(top_15[disp_cols], use_container_width=True)
        
        except Exception as e:
          st.warning(f"Could not render Executive Dashboard: {str(e)}")

        # We will output the new data with highlights
        df_combined = new_data.copy()
        df_combined['Audit Flag'] = ''
        
        # Calculate changes count without side effects in styler
        changes_count = 0
        for pid in common_pids:
          flags = []
          status_new = str(new_data.loc[pid, 'Status']).strip() if 'Status'in new_data.columns else ''
          purpose_new = str(new_data.loc[pid, 'Purpose']).strip() if 'Purpose'in new_data.columns else ''
          
          # 1. Dev Mode Data Collection
          if status_new in ['Developmental Mode', '0', '0.0']:
            if 'Total Records'in new_data.columns and 'Total Records'in old_data.columns:
              val_old = old_data.loc[pid, 'Total Records']
              val_new = new_data.loc[pid, 'Total Records']
              if pd.notna(val_old) and pd.notna(val_new):
                try:
                  if float(val_new) > float(val_old):
                    flags.append('Dev Mode Collecting Data')
                except ValueError:
                  pass

            if 'Creation Time'in new_data.columns:
              ctime = new_data.loc[pid, 'Creation Time']
              if pd.notna(ctime):
                try:
                  dt = pd.to_datetime(ctime)
                  if (pd.Timestamp.now() - dt).days > 730:
                    flags.append('⏳ Stale Dev Project (>2 yrs)')
                except Exception:
                  pass

          # 2. Extreme Growth
          if 'Total Records'in new_data.columns and 'Total Records'in old_data.columns:
            try:
              val_old = float(old_data.loc[pid, 'Total Records']) if pd.notna(old_data.loc[pid, 'Total Records']) else 0
              val_new = float(new_data.loc[pid, 'Total Records']) if pd.notna(new_data.loc[pid, 'Total Records']) else 0
              if (val_new - val_old) >= 1000:
                flags.append('Extreme Growth (>1000 diff)')
            except ValueError:
              pass

          # 3. Dormant Project
          if 'Days Since Last Event'in new_data.columns:
            days = new_data.loc[pid, 'Days Since Last Event']
            if pd.notna(days):
              try:
                if float(days) > 180:
                  flags.append('Dormant Project (>180 Days)')
              except ValueError:
                pass
                
          # 4. Practice Project Collecting Data
          if purpose_new in ['Practice/Just For Fun', '0', '0.0']:
            if 'Total Records'in new_data.columns:
              recs = new_data.loc[pid, 'Total Records']
              if pd.notna(recs):
                try:
                  if float(recs) > 5:
                    flags.append('Practice Project with >5 Records')
                except ValueError:
                  pass

          # 5. Orphaned Project
          users_str = str(new_data.loc[pid, 'Usernames']).strip() if 'Usernames'in new_data.columns else ''
          if users_str == ''or pd.isna(new_data.loc[pid, 'Usernames']) or users_str == 'nan':
            flags.append('Orphaned Project (No Users)')
          else:
            if len(users_str.split(';')) >= 30:
              flags.append('Massive Project (>=30 Users)')
            
          # 5.5 Suspended Users Check
          susp_col = 'user_suspended_time#group#hidden'
          if susp_col in new_data.columns:
            susp_str = str(new_data.loc[pid, susp_col]).strip()
            if susp_str != 'nan'and susp_str != '':
              susp_list = susp_str.split(';')
              susp_count = sum(1 for x in susp_list if x.strip() != '')
              if susp_count > 0:
                total_users = len(susp_list)
                if susp_count == total_users and total_users > 0:
                  flags.append('ALL Users Suspended (Orphan Risk)')
                else:
                  flags.append(f'{susp_count} User(s) Suspended')

          # 6. Empty Production Project
          if status_new in ['Production Mode', '1', '1.0']:
            if 'Total Records'in new_data.columns:
              recs = new_data.loc[pid, 'Total Records']
              if pd.notna(recs):
                try:
                  if float(recs) == 0:
                    flags.append('Empty Production Project')
                except ValueError:
                  pass

          # 7. User Changes
          if 'Usernames'in new_data.columns and 'Usernames'in old_data.columns:
            old_users_str = str(old_data.loc[pid, 'Usernames'])
            new_users_str = str(new_data.loc[pid, 'Usernames'])
            old_users_str = ''if old_users_str == 'nan'else old_users_str
            new_users_str = ''if new_users_str == 'nan'else new_users_str
            
            old_set = set([u.strip() for u in old_users_str.split(';') if u.strip()])
            new_set = set([u.strip() for u in new_users_str.split(';') if u.strip()])
            
            added = new_set - old_set
            removed = old_set - new_set
            
            if added:
              flags.append(f"Added User(s): {', '.join(added)}")
            if removed:
              flags.append(f"Removed User(s): {', '.join(removed)}")
              
          if flags:
            df_combined.loc[pid, 'Audit Flag'] = '| '.join(flags)

          # Calculate generic cell changes
          for col in new_data.columns:
            if col in old_data.columns:
              val_old = old_data.loc[pid, col]
              val_new = new_data.loc[pid, col]
              if pd.isna(val_old) and pd.isna(val_new):
                continue
              if str(val_old) != str(val_new):
                changes_count += 1
        
        for pid in new_pids:
          flags = []
          status_new = str(new_data.loc[pid, 'Status']).strip() if 'Status'in new_data.columns else ''
          purpose_new = str(new_data.loc[pid, 'Purpose']).strip() if 'Purpose'in new_data.columns else ''
          
          if status_new in ['Developmental Mode', '0', '0.0']:
            if 'Total Records'in new_data.columns:
              val_new = new_data.loc[pid, 'Total Records']
              if pd.notna(val_new):
                try:
                  if float(val_new) > 0:
                    flags.append('Dev Mode Collecting Data')
                except ValueError:
                  pass
                  
            if 'Creation Time'in new_data.columns:
              ctime = new_data.loc[pid, 'Creation Time']
              if pd.notna(ctime):
                try:
                  dt = pd.to_datetime(ctime)
                  if (pd.Timestamp.now() - dt).days > 730:
                    flags.append('⏳ Stale Dev Project (>2 yrs)')
                except Exception:
                  pass

          if 'Days Since Last Event'in new_data.columns:
            days = new_data.loc[pid, 'Days Since Last Event']
            if pd.notna(days):
              try:
                if float(days) > 180:
                  flags.append('Dormant Project (>180 Days)')
              except ValueError:
                pass

          if purpose_new in ['Practice/Just For Fun', '0', '0.0']:
            if 'Total Records'in new_data.columns:
              recs = new_data.loc[pid, 'Total Records']
              if pd.notna(recs):
                try:
                  if float(recs) > 5:
                    flags.append('Practice Project with >5 Records')
                except ValueError:
                  pass

          users_str = str(new_data.loc[pid, 'Usernames']).strip() if 'Usernames'in new_data.columns else ''
          if users_str == ''or pd.isna(new_data.loc[pid, 'Usernames']) or users_str == 'nan':
            flags.append('Orphaned Project (No Users)')
          else:
            if len(users_str.split(';')) >= 30:
              flags.append('Massive Project (>=30 Users)')
            
          susp_col = 'user_suspended_time#group#hidden'
          if susp_col in new_data.columns:
            susp_str = str(new_data.loc[pid, susp_col]).strip()
            if susp_str != 'nan'and susp_str != '':
              susp_list = susp_str.split(';')
              susp_count = sum(1 for x in susp_list if x.strip() != '')
              if susp_count > 0:
                total_users = len(susp_list)
                if susp_count == total_users and total_users > 0:
                  flags.append('ALL Users Suspended (Orphan Risk)')
                else:
                  flags.append(f'{susp_count} User(s) Suspended')

          if status_new in ['Production Mode', '1', '1.0']:
            if 'Total Records'in new_data.columns:
              recs = new_data.loc[pid, 'Total Records']
              if pd.notna(recs):
                try:
                  if float(recs) == 0:
                    flags.append('Empty Production Project')
                except ValueError:
                  pass
                  
          if flags:
            df_combined.loc[pid, 'Audit Flag'] = '| '.join(flags)

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
            if 'Audit Flag'in data.columns and data.loc[pid, 'Audit Flag'] != '':
              is_diff.loc[pid, 'Audit Flag'] = flag_style
              if 'Total Records'in is_diff.columns:
                is_diff.loc[pid, 'Total Records'] = flag_style
                
          return is_diff

        # Apply styling
        styled_df = df_combined.style.apply(highlight_diff, axis=None)
        
        # Check for any audit violations
        audit_flags = df_combined[df_combined['Audit Flag'] != '']
        if not audit_flags.empty:
          st.error(f"**High Priority**: Found {len(audit_flags)} project(s) with active Auditing Violations (Dormancy, User Changes, Dev Tracking, etc)!")
          
          st.write("#### Active Auditing Alert Flags")
          st.write("These projects correspond to high-priority REDCap server violations. Please review.")
          
          try:
              all_flags = []
              for flag_str in audit_flags['Audit Flag']:
                  flags = [f.strip() for f in str(flag_str).split('|') if f.strip()]
                  all_flags.extend(flags)
              
              if all_flags:
                  flag_counts = pd.Series(all_flags).value_counts().reset_index()
                  flag_counts.columns = ['Violation Type', 'Count']
                  
                  fig_viol = px.bar(flag_counts, x='Count', y='Violation Type', orientation='h', 
                                    title='Compliance Vulnerability Breakdown', color='Count',
                                    color_continuous_scale='Reds')
                  fig_viol.update_layout(yaxis={'categoryorder':'total ascending'})
                  st.plotly_chart(fig_viol, use_container_width=True)
          except Exception as e:
              st.warning(f"Could not render Violations Chart: {str(e)}")
          
          focus_cols = ['Project Title', 'Status', 'Total Records', 'Purpose', 'Usernames', 'Audit Flag']
          display_cols = [col for col in focus_cols if col in audit_flags.columns]
          
          # Also include PID which is currently the index.
          st.dataframe(audit_flags[display_cols], use_container_width=True)
          
          csv_export = audit_flags[display_cols].to_csv(index=True)
          st.download_button(
            label="Download Violations Only (CSV)",
            data=csv_export,
            file_name="REDCap_High_Priority_Violations.csv",
            mime="text/csv",
          )
          
          
          with st.expander("Generate Compliance Emails", expanded=False):
            st.write("Copy and paste these templates to reach out to the project owners:")
            for pid, row in audit_flags.iterrows():
              title = row.get('Project Title', f"Project {pid}")
              viol = row.get('Audit Flag', '')
              
              viol_formatted = "\n".join([f"- **{v.strip()}**" for v in str(viol).split('|') if v.strip()])
              
              template = f"**Subject:** REDCap Auditing Alert - Action Required for '{title}'\n\nHello Team,\n\nOur automated server sweep flagged your project for the following compliance vulnerability:\n\n{viol_formatted}\n\nPlease review your project settings or contact administration to resolve this issue.\n\nThank you,\n\nREDCap Administration"
              st.info(template)
              
          st.divider()

        if len(deleted_pids) > 0:
          st.write("#### Deleted Projects Log")
          st.write("These projects existed last month but were fully completely deleted or purged this month.")
          del_cols = [c for c in ['Project Title', 'Status', 'Total Records', 'Purpose', 'Usernames'] if c in old_data.columns]
          st.dataframe(old_data.loc[deleted_pids, del_cols], use_container_width=True)
          st.divider()

        if spam_users_counts:
          spam_df = pd.DataFrame(list(spam_users_counts.items()), columns=['Username', 'New Projects Created This Month'])
          spam_filtered = spam_df[spam_df['New Projects Created This Month'] >= 5].sort_values(by='New Projects Created This Month', ascending=False)
          if not spam_filtered.empty:
            st.warning("**Spam/Training Alert**: The following users created 5 or more new projects this month. They may need training on longitudinal data collection.")
            st.dataframe(spam_filtered, use_container_width=True, hide_index=True)
            st.divider()

        if changes_count > 0:
          st.info(f"Detected **{changes_count}** specific cell changes across all records.")
        else:
          st.info("No cell changes detected in the common records.")

        # Sidebar User Investigator Integration
        st.sidebar.title("User Investigator")
        st.sidebar.write("Audit a specific researcher's portfolio.")
        search_user = st.sidebar.text_input("Enter exact Username:")
        if search_user:
          st.sidebar.write("---")
          if 'Usernames'in new_data.columns:
            mask = new_data['Usernames'].str.lower().fillna('').apply(lambda x: search_user.lower() in [u.strip().lower() for u in x.split(';')])
            user_df = new_data[mask]
            if user_df.empty:
              st.sidebar.warning(f"No projects found for '{search_user}'.")
            else:
              # Calculate metrics for the user
              total_user_records = pd.to_numeric(user_df.get('Total Records', pd.Series()), errors='coerce').sum()
              st.sidebar.success(f"Found **{len(user_df)}** projects.")
              st.sidebar.info(f"Managing **{int(total_user_records):,}** Total Records.")
              
              st.write(f"### Investigator Profile: `{search_user}`")
              st.write(f"Displaying all {len(user_df)} projects currently mapped to this user footprint.")
              user_display_cols = [c for c in ['Project Title', 'Status', 'Total Records', 'Purpose', 'Usernames', 'Audit Flag'] if c in df_combined.columns]
              st.dataframe(df_combined.loc[user_df.index, user_display_cols], use_container_width=True)
              st.divider()

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
          label="Download Highlighted Audit Report (Excel)",
          data=excel_data,
          file_name="REDCap_Audit_Report.xlsx",
          mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          use_container_width=True,
          type="primary"
        )
        
    except Exception as e:
      st.error(f"An error occurred while processing the files. Ensure the formats are correct and 'PID'column exists.\n\nError Details: {e}")
