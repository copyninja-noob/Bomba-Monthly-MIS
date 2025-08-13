import streamlit as st
import pandas as pd
import os
import plotly.express as px
import numpy as np
import openpyxl

st.set_page_config(page_title="Bomba Foods Profitability Dashboard", layout="wide")

# Inject CSS for sticky header and scrollable table container
st.markdown(
    '''
    <style>
    .freeze-header-table-container {
        max-height: 600px;
        overflow-y: auto;
    }
    .freeze-header-table-container table {
        width: 100%;
        border-collapse: collapse;
    }
    thead th {
        position: sticky !important;
        top: 0;
        z-index: 2;
        background: #003366 !important;
        color: white !important;
    }
    </style>
    ''',
    unsafe_allow_html=True
)

# Load all sheets from Excel except Niko
file_path = os.path.join(os.path.dirname(__file__), "Bomba Foods-MIS.xlsx")
if not os.path.exists(file_path):
    st.error(f"Excel file '{file_path}' not found in this directory.")
    st.stop()

# Load all sheets and filter out P&L (Niko)
all_sheets = pd.read_excel(file_path, sheet_name=None)
sheets_data = {name: df for name, df in all_sheets.items() if name != 'P&L (Niko)'}

# Convert 'Month' column to string for all dataframes if it is datetime
def ensure_month_str(df):
    if 'Month' in df.columns and pd.api.types.is_datetime64_any_dtype(df['Month']):
        df['Month'] = df['Month'].dt.strftime('%Y-%m')
    return df

branch_frames = []
sheets_data_str = {}
for branch, df in sheets_data.items():
    df = ensure_month_str(df.copy())
    df['Branch'] = branch
    branch_frames.append(df)
    sheets_data_str[branch] = df

full_df = pd.concat(branch_frames, ignore_index=True)
full_df = ensure_month_str(full_df)

st.title("Bomba Foods Profitability Dashboard")

branch_names = list(sheets_data.keys())
branch_option = st.sidebar.selectbox(
    "Select Branch",
    branch_names
)

# Determine unhidden columns for the selected branch using openpyxl
import openpyxl
excel_path = file_path
wb = openpyxl.load_workbook(excel_path, read_only=False, data_only=True)
ws = wb[branch_option]

# Get indexes of unhidden columns (1-based for openpyxl)
unhidden_col_indexes = [
    idx for idx, col in enumerate(ws.iter_cols(1, ws.max_column), 1)
    if ws.column_dimensions[openpyxl.utils.get_column_letter(idx)].hidden is not True
]

# Map to DataFrame column names (0-based for pandas)
df_cols = list(sheets_data_str[branch_option].columns)
unhidden_cols = [df_cols[idx-1] for idx in unhidden_col_indexes if idx-1 < len(df_cols)]

df_to_show = sheets_data_str[branch_option][unhidden_cols].copy()

# --- Approval and Download logic (above table) ---
if 'approvals' not in st.session_state:
    st.session_state['approvals'] = {branch: False for branch in branch_names}
if 'approval_inputs' not in st.session_state:
    st.session_state['approval_inputs'] = {branch: '' for branch in branch_names}
if 'show_code_input' not in st.session_state:
    st.session_state['show_code_input'] = {branch: False for branch in branch_names}

st.subheader(f"Data Table - {branch_option}")

# Approval logic above table
col1, col2 = st.columns([1,6])
with col1:
    if not st.session_state['approvals'][branch_option]:
        if st.button('Approval', key=f'approval_btn_{branch_option}'):
            st.session_state['show_code_input'][branch_option] = True
        if st.session_state['show_code_input'][branch_option]:
            code = st.text_input('Enter approval code:', type='password', key=f'approval_code_input_{branch_option}')
            if st.button('Submit', key=f'code_submit_{branch_option}'):
                if code == 'Bomba':
                    st.session_state['approvals'][branch_option] = True
                    st.session_state['show_code_input'][branch_option] = False
                else:
                    st.error('Incorrect code!')
    else:
        approved_col, reset_col = st.columns([2,1])
        with approved_col:
            st.button('Approved', key=f'approved_btn_{branch_option}', disabled=True)
        with reset_col:
            if st.button('Reset', key=f'reset_btn_{branch_option}'):
                st.session_state['approvals'][branch_option] = False
                st.session_state['show_code_input'][branch_option] = False
                st.session_state['approval_inputs'][branch_option] = ''
        # Download Excel (only visible/unhidden columns)
        import io
        from openpyxl import load_workbook
        from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        # Write to Excel
        towrite = io.BytesIO()
        df_to_show.to_excel(towrite, index=False, engine='openpyxl')
        towrite.seek(0)
        wb = load_workbook(towrite)
        ws = wb.active
        # Header formatting
        header_fill = PatternFill(start_color='003366', end_color='003366', fill_type='solid')
        header_font = Font(bold=True, color='FFFFFF', size=14)
        # Month column formatting
        from datetime import datetime
        month_fmt = '%b-%y'
        for cell in ws[1]:
            # Try to parse as date for month columns
            try:
                # If header looks like a date, format as 'Apr-25'
                if isinstance(cell.value, str):
                    try:
                        dt = pd.to_datetime(cell.value)
                        cell.value = dt.strftime(month_fmt)
                    except Exception:
                        pass
                elif isinstance(cell.value, datetime):
                    cell.value = cell.value.strftime(month_fmt)
            except Exception:
                pass
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal='center', vertical='center')
        # If any month columns have date values, format them too
        for c in range(1, ws.max_column+1):
            col_val = ws.cell(row=1, column=c).value
            if col_val:
                try:
                    dt = pd.to_datetime(col_val, errors='coerce')
                    if not pd.isnull(dt):
                        # Format all values in this column if they are dates
                        for r in range(2, ws.max_row+1):
                            v = ws.cell(row=r, column=c).value
                            if isinstance(v, datetime):
                                ws.cell(row=r, column=c).number_format = 'mmm-yy'
                except Exception:
                    pass
        # Border for all cells
        thin = Side(border_style="thin", color="000000")
        for row in ws.iter_rows():
            for cell in row:
                cell.border = Border(top=thin, left=thin, right=thin, bottom=thin)
        # Row/column/number formatting logic
        particulars_col = None
        for idx, cell in enumerate(ws[1], 1):
            if str(cell.value).strip().lower() == 'particulars':
                particulars_col = idx
                break
        if particulars_col:
            sales_block = False
            blue_block = False
            green1_block = False
            green2_block = False
            red_block = False
            for r in range(2, ws.max_row+1):
                val = ws.cell(row=r, column=particulars_col).value
                style = None
                if isinstance(val, str):
                    txt = val.strip().lower()
                    # Header logic copied from dashboard
                    if txt == 'net sale':
                        style = {'fill': PatternFill(start_color='e75480', end_color='e75480', fill_type='solid'), 'font': Font(bold=True)}
                    elif txt == 'cost of food sold':
                        style = {'font': Font(bold=True, underline='single')}
                    elif txt == 'total food cost':
                        style = {'fill': PatternFill(start_color='4f81bd', end_color='4f81bd', fill_type='solid'), 'font': Font(bold=True, color='FFFFFF')}
                    elif txt in ['add: opening inventory', 'less: closing inventory']:
                        style = {'fill': PatternFill(start_color='d6f0ff', end_color='d6f0ff', fill_type='solid')}
                    elif txt == 'net food cost':
                        style = {'fill': PatternFill(start_color='4f81bd', end_color='4f81bd', fill_type='solid'), 'font': Font(bold=True, color='FFFFFF')}
                    elif txt == 'cost of drinks sold':
                        style = {'font': Font(bold=True, underline='single')}
                    elif txt == 'total drinks cost' or txt == 'net drink cost':
                        style = {'fill': PatternFill(start_color='5cb85c', end_color='5cb85c', fill_type='solid'), 'font': Font(bold=True, color='FFFFFF')}
                    elif txt == 'gross profit':
                        style = {'fill': PatternFill(start_color='d9534f', end_color='d9534f', fill_type='solid'), 'font': Font(bold=True, color='FFFFFF')}
                    elif txt == 'expenses':
                        style = {'font': Font(bold=True, underline='single')}
                    elif txt == 'total non operating cost':
                        style = {'fill': PatternFill(start_color='ff9900', end_color='ff9900', fill_type='solid'), 'font': Font(bold=True)}
                    elif txt == 'net profit':
                        style = {'fill': PatternFill(start_color='b30000', end_color='b30000', fill_type='solid'), 'font': Font(bold=True, color='FFFFFF')}
                    # Block coloring logic
                    if txt == 'sales':
                        sales_block = True
                    if sales_block:
                        style = style or {'fill': PatternFill(start_color='fff9c4', end_color='fff9c4', fill_type='solid')}
                        if txt == 'total sales and service charges':
                            style = {'fill': PatternFill(start_color='ffe066', end_color='ffe066', fill_type='solid'), 'font': Font(bold=True)}
                            sales_block = False
                    pink_rows = ['less: discount', 'less: adjusted ( net of gst)', 'net discount']
                    if txt in pink_rows:
                        style = {'fill': PatternFill(start_color='ffe6f0', end_color='ffe6f0', fill_type='solid')}
                        if txt == 'net discount':
                            style['font'] = Font(bold=True)
                    if txt == 'grocery [fcl]':
                        blue_block = True
                    if blue_block:
                        style = {'fill': PatternFill(start_color='d6f0ff', end_color='d6f0ff', fill_type='solid')}
                    if txt == 'drinks [fcd]':
                        blue_block = False
                    if txt == 'drinks [fcd] - alco':
                        green1_block = True
                    if green1_block:
                        style = {'fill': PatternFill(start_color='e6ffe6', end_color='e6ffe6', fill_type='solid')}
                    if txt == 'drinks [fcd] - non alco':
                        green1_block = False
                    if txt == 'add: opening inventory (alco)':
                        green2_block = True
                    if green2_block:
                        style = {'fill': PatternFill(start_color='e6ffe6', end_color='e6ffe6', fill_type='solid')}
                    if txt == 'add: closing inventory (non-alco)':
                        green2_block = False
                    if txt == 'bank charges/credit card charges':
                        red_block = True
                    if red_block:
                        style = {'fill': PatternFill(start_color='ffe6e6', end_color='ffe6e6', fill_type='solid')}
                    if txt == 'license fees':
                        red_block = False
                    # Apply style to the row
                    if style:
                        for c in range(1, ws.max_column+1):
                            if 'fill' in style:
                                ws.cell(row=r, column=c).fill = style['fill']
                            if 'font' in style:
                                ws.cell(row=r, column=c).font = style['font']
        # Number formatting
        for c in range(1, ws.max_column+1):
            col_name = ws.cell(row=1, column=c).value
            if col_name and (isinstance(col_name, str) and ('%' in col_name or col_name.strip().startswith('%') or col_name.strip().endswith('%'))):
                for r in range(2, ws.max_row+1):
                    ws.cell(row=r, column=c).number_format = '0.00%'
            else:
                for r in range(2, ws.max_row+1):
                    try:
                        val = ws.cell(row=r, column=c).value
                        if isinstance(val, (int, float)):
                            ws.cell(row=r, column=c).number_format = '#,##,##0'
                    except Exception:
                        pass
        # Autosize columns
        for col in ws.columns:
            max_length = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            ws.column_dimensions[col_letter].width = max_length + 2
        # Save to buffer
        styled_buf = io.BytesIO()
        wb.save(styled_buf)
        styled_buf.seek(0)
        st.download_button(
            label='Download Table (Excel)',
            data=styled_buf,
            file_name=f'{branch_option}_table.xlsx',
            mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            key=f'download_excel_{branch_option}'
        )

# The table display remains below this logic

# Determine row and column visibility from Excel
import openpyxl
from openpyxl.utils import get_column_letter

excel_path = file_path
wb = openpyxl.load_workbook(excel_path, read_only=False, data_only=True)
ws = wb[branch_option]

# Debug: Print hidden columns for verification
debug_hidden_cols = []
for idx in range(1, ws.max_column + 1):
    col_letter = get_column_letter(idx)
    is_hidden = ws.column_dimensions[col_letter].hidden if col_letter in ws.column_dimensions else False
    debug_hidden_cols.append((idx, col_letter, is_hidden))

# Debug: Print hidden rows for verification
debug_hidden_rows = []
for row_idx in range(1, ws.max_row + 1):
    is_hidden = ws.row_dimensions[row_idx].hidden if row_idx in ws.row_dimensions else False
    debug_hidden_rows.append((row_idx, is_hidden))

# Print debug info (only visible in terminal/console)
print(f"\nDebug - Column visibility for {branch_option}:")
for idx, col_letter, is_hidden in debug_hidden_cols:
    print(f"Column {col_letter} (index {idx}): {'HIDDEN' if is_hidden else 'visible'}")

print(f"\nDebug - Row visibility for {branch_option} (first 20 rows):")
for row_idx, is_hidden in debug_hidden_rows[:20]:
    print(f"Row {row_idx}: {'HIDDEN' if is_hidden else 'visible'}")
if len(debug_hidden_rows) > 20:
    print(f"... and {len(debug_hidden_rows) - 20} more rows")

# Get indexes of unhidden columns (1-based for openpyxl)
unhidden_col_indexes = [
    idx for idx in range(1, ws.max_column + 1)
    if not (get_column_letter(idx) in ws.column_dimensions and 
           ws.column_dimensions[get_column_letter(idx)].hidden is True)
]

# Get indexes of unhidden rows (1-based for openpyxl)
unhidden_row_indexes = [
    row_idx for row_idx in range(1, ws.max_row + 1)
    if not (row_idx in ws.row_dimensions and ws.row_dimensions[row_idx].hidden is True)
]

# Map to DataFrame column names (0-based for pandas)
df_cols = list(sheets_data_str[branch_option].columns)
unhidden_cols = [df_cols[idx-1] for idx in unhidden_col_indexes if idx-1 < len(df_cols)]

# Debug: Print which columns and rows will be shown
print("\nDebug - Columns to be shown in dashboard:", unhidden_cols)
print(f"Debug - Showing {len(unhidden_row_indexes)} out of {ws.max_row} rows")

import numpy as np
import re
from datetime import datetime

# Create a copy of the data with only visible columns and rows
df_to_show = sheets_data_str[branch_option].iloc[[i-1 for i in unhidden_row_indexes if i-1 < len(sheets_data_str[branch_option])]]
df_to_show = df_to_show[unhidden_cols].copy()

def indian_number_format(val):
    try:
        x = int(round(float(val)))
        s = str(x)[::-1]
        groups = []
        groups.append(s[:3])
        s = s[3:]
        while s:
            groups.append(s[:2])
            s = s[2:]
        return ','.join(groups)[::-1]
    except Exception:
        return ''

def format_percent(val):
    try:
        if pd.isnull(val) or val == '' or float(val) == 0:
            return ''
        return f"{float(val)*100:.2f}%"
    except Exception:
        return ''

def excel_month_fmt(col):
    # If column is datetime or looks like a month, format as 'Apr-25'
    if isinstance(col, datetime):
        return col.strftime('%b-%y')
    if isinstance(col, str):
        try:
            dt = pd.to_datetime(col)
            return dt.strftime('%b-%y')
        except Exception:
            return col
    return col

# Format headers
new_cols = []
for col in df_to_show.columns:
    new_cols.append(excel_month_fmt(col))
df_to_show.columns = new_cols

# Format values
skip_cols = []
for col in df_to_show.columns:
    if col.lower() == 'particulars' or col.lower() == 'branch' or col == '%' or str(col).strip().startswith('%') or str(col).strip().endswith('%'):
        skip_cols.append(col)

# Find index of 'Net Profit' row in 'PARTICULARS' column (case-insensitive)
net_profit_idx = None
for i, val in enumerate(df_to_show['PARTICULARS']):
    if isinstance(val, str) and val.strip().lower().startswith('net profit'):
        net_profit_idx = i
        break

# Apply formatting for rows before or at 'Net Profit'
for col in df_to_show.columns:
    if col in skip_cols:
        # Format % columns
        if col == '%' or str(col).strip().startswith('%') or str(col).strip().endswith('%'):
            df_to_show.loc[:net_profit_idx, col] = df_to_show.loc[:net_profit_idx, col].apply(format_percent)
        else:
            df_to_show.loc[:net_profit_idx, col] = df_to_show.loc[:net_profit_idx, col].replace([None, np.nan], '')
    else:
        # Format all other columns as Indian numbers
        df_to_show.loc[:net_profit_idx, col] = df_to_show.loc[:net_profit_idx, col].apply(lambda x: indian_number_format(x) if pd.notnull(x) and x != '' else '')

# For rows after Net Profit, do not move names; format numbers only
if net_profit_idx is not None:
    for i in range(net_profit_idx+1, len(df_to_show)):
        row = df_to_show.iloc[i]
        for col in df_to_show.columns:
            val = row[col]
            # Only format if it's a number
            try:
                # If value is numeric, format as Indian number
                if isinstance(val, (int, float)) and not pd.isnull(val):
                    df_to_show.at[i, col] = indian_number_format(val)
                # If value is string but represents a number
                elif isinstance(val, str) and val.replace(',', '').replace('.', '').isdigit():
                    df_to_show.at[i, col] = indian_number_format(val)
                # Else leave as-is (expense name or blank)
            except Exception:
                pass

# Ensure all None and np.nan are shown as blanks
df_to_show = df_to_show.replace([None, np.nan], '')

def highlight_sales_block(df):
    sales_start = "SALES"
    sales_end = "TOTAL SALES AND SERVICE CHARGES"
    pink_rows = ["LESS: DISCOUNT", "LESS: ADJUSTED ( NET OF GST)", "NET DISCOUNT"]
    highlight = False
    highlights = []
    for _, row in df.iterrows():
        row_styles = ['' for _ in row]
        if isinstance(row['PARTICULARS'], str):
            particulars = row['PARTICULARS'].strip().lower()
            # Deep pink Net Sale row
            if particulars == "net sale":
                row_styles = ['background-color: #e75480; font-weight: bold' for _ in row]
            # Bold and underline COST OF FOOD SOLD
            elif particulars == "cost of food sold":
                row_styles = ['font-weight: bold; text-decoration: underline' for _ in row]
            # Deeper blue and bold TOTAL FOOD COST
            elif particulars == "total food cost":
                row_styles = ['background-color: #4f81bd; color: white; font-weight: bold' for _ in row]
            # Light blue for inventory rows
            elif particulars in ["add: opening inventory", "less: closing inventory"]:
                row_styles = ['background-color: #d6f0ff' for _ in row]
            # Deeper blue and bold NET FOOD COST
            elif particulars == "net food cost":
                row_styles = ['background-color: #4f81bd; color: white; font-weight: bold' for _ in row]
            else:
                # Light blue block: GROCERY [FCL] to DRINKS [FCD]
                blue_start = "grocery [fcl]"
                blue_end = "drinks [fcd]"
                if not hasattr(highlight_sales_block, 'in_blue_block'):
                    highlight_sales_block.in_blue_block = False
                if blue_start == particulars:
                    highlight_sales_block.in_blue_block = True
                if highlight_sales_block.in_blue_block:
                    row_styles = ['background-color: #d6f0ff' for _ in row]
                if blue_end == particulars:
                    highlight_sales_block.in_blue_block = False

                # Light green block: DRINKS [FCD] - ALCO to DRINKS [FCD] - NON ALCO
                green1_start = "drinks [fcd] - alco"
                green1_end = "drinks [fcd] - non alco"
                if not hasattr(highlight_sales_block, 'in_green1_block'):
                    highlight_sales_block.in_green1_block = False
                if green1_start == particulars:
                    highlight_sales_block.in_green1_block = True
                if highlight_sales_block.in_green1_block:
                    row_styles = ['background-color: #e6ffe6' for _ in row]
                if green1_end == particulars:
                    highlight_sales_block.in_green1_block = False

                # Light green block: ADD: OPENING INVENTORY (ALCO) to ADD: CLOSING INVENTORY (NON-ALCO)
                green2_start = "add: opening inventory (alco)"
                green2_end = "add: closing inventory (non-alco)"
                if not hasattr(highlight_sales_block, 'in_green2_block'):
                    highlight_sales_block.in_green2_block = False
                if green2_start == particulars:
                    highlight_sales_block.in_green2_block = True
                if highlight_sales_block.in_green2_block:
                    row_styles = ['background-color: #e6ffe6' for _ in row]
                if green2_end == particulars:
                    highlight_sales_block.in_green2_block = False

                # Bold and underline COST OF DRINKS SOLD
                if particulars == "cost of drinks sold":
                    row_styles = ['font-weight: bold; text-decoration: underline' for _ in row]
                # Deeper green and bold TOTAL DRINKS COST
                elif particulars == "total drinks cost":
                    row_styles = ['background-color: #5cb85c; color: white; font-weight: bold' for _ in row]
                # Deeper green and bold NET DRINK COST
                elif particulars == "net drink cost":
                    row_styles = ['background-color: #5cb85c; color: white; font-weight: bold' for _ in row]
                # Deep red and bold Gross Profit
                elif particulars == "gross profit":
                    row_styles = ['background-color: #d9534f; color: white; font-weight: bold' for _ in row]
                # Bold and underline Expenses
                elif particulars == "expenses":
                    row_styles = ['font-weight: bold; text-decoration: underline' for _ in row]
                # Light red block: BANK CHARGES/CREDIT CARD CHARGES to LICENSE FEES
                else:
                    red_start = "bank charges/credit card charges"
                    red_end = "license fees"
                    if not hasattr(highlight_sales_block, 'in_red_block'):
                        highlight_sales_block.in_red_block = False
                    if red_start == particulars:
                        highlight_sales_block.in_red_block = True
                    if highlight_sales_block.in_red_block:
                        row_styles = ['background-color: #ffe6e6' for _ in row]
                    if red_end == particulars:
                        highlight_sales_block.in_red_block = False
                    # Bold and orange TOTAL NON OPERATING COST
                    if particulars == "total non operating cost":
                        row_styles = ['background-color: #ff9900; font-weight: bold' for _ in row]
                    # Bold and deep red NET PROFIT
                    elif particulars == "net profit":
                        row_styles = ['background-color: #b30000; color: white; font-weight: bold' for _ in row]

                # Pink block
                for pink in pink_rows:
                    if pink.lower() == particulars:
                        if pink == "NET DISCOUNT":
                            row_styles = ['background-color: #ffe6f0; font-weight: bold' for _ in row]
                        else:
                            row_styles = ['background-color: #ffe6f0' for _ in row]
                        break
                else:  # Only check sales block if not pink or net sale or cost of food sold or blue/green/red blocks
                    if sales_start.lower() in particulars:
                        highlight = True
                    if highlight:
                        if sales_end.lower() in particulars:
                            row_styles = ['background-color: #ffe066; font-weight: bold' for _ in row]
                            highlight = False
                        else:
                            row_styles = ['background-color: #fff9c4' for _ in row]
        highlights.append(row_styles)
    return pd.DataFrame(highlights, columns=df.columns)

def style_table(df):
    styler = df.style.set_table_styles([
        {
            'selector': 'th',
            'props': [
                ('background-color', '#003366'),
                ('color', 'white'),
                ('font-weight', 'bold'),
                ('font-size', '16px')
            ]
        }
    ]).hide(axis='index')
    return styler.apply(highlight_sales_block, axis=None)

st.subheader(f"Data Table - {branch_option}")
st.markdown(
    f'<div class="freeze-header-table-container">{style_table(df_to_show).to_html(escape=False)}</div>',
    unsafe_allow_html=True
)

# Summary Reports & Charts
st.markdown("---")
st.header("Summary Reports & Charts")

# KPI Tiles for latest month (selected branch only)
branch_df = sheets_data_str[branch_option]

# Identify month columns (exclude non-month columns)
non_month_cols = ['PARTICULARS', 'Branch', 'Month']
month_cols = [col for col in branch_df.columns if col not in non_month_cols]

# Try to parse columns as dates and find the latest
month_col_dates = []
for col in month_cols:
    try:
        dt = pd.to_datetime(col, format='%b-%y', errors='coerce')
        if not pd.isnull(dt):
            month_col_dates.append((col, dt))
    except Exception:
        continue
if month_col_dates:
    # Sort and pick the latest
    month_col_dates.sort(key=lambda x: x[1])
    latest_month_col, latest_month_dt = month_col_dates[-1]
    # KPIs and their row labels
    kpi_labels = [
        ('Total Sales and Service Charge', 'TOTAL SALES AND SERVICE CHARGES'),
        ('Net Food Cost', 'NET FOOD COST'),
        ('Net Drink Cost', 'NET DRINK COST'),
        ('Gross Profit', 'GROSS PROFIT'),
        ('Total Non Operating Cost', 'TOTAL NON OPERATING COST'),
        ('Net Profit', 'NET PROFIT'),
    ]
    kpi_results = []
    for kpi_name, row_label in kpi_labels:
        row = branch_df[branch_df['PARTICULARS'].str.strip().str.upper() == row_label]
        if not row.empty and latest_month_col in row.columns:
            value = row[latest_month_col].values[0]
            if value is not None and value != '' and value != 0:
                try:
                    value_fmt = indian_number_format(value)
                except Exception:
                    value_fmt = str(value)
            else:
                value_fmt = '-'
        else:
            value_fmt = '-'
        kpi_results.append((kpi_name, value_fmt))
    # Show tiles: 3 per row, smaller, colored
    st.markdown(f'#### Latest Month KPIs ({latest_month_col})')
    colors = [
        '#e3f2fd', '#fff9c4', '#ffe0b2', '#c8e6c9', '#f8bbd0', '#d1c4e9'
    ]
    tile_html = """
    <style>
    .kpi-row {{ display: flex; flex-wrap: wrap; gap: 1rem; margin-bottom: 1rem; }}
    .kpi-tile {{
        flex: 1 1 calc(33% - 1rem);
        min-width: 180px;
        background: {bg};
        border-radius: 12px;
        padding: 0.7rem 0.5rem 0.5rem 0.5rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.04);
        text-align: center;
        margin-bottom: 0.5rem;
    }}
    .kpi-label {{ font-size: 1rem; color: #333; margin-bottom: 0.2rem; font-weight: 600; }}
    .kpi-value {{ font-size: 1.5rem; color: #003366; font-weight: bold; letter-spacing: 1px; }}
    @media (max-width: 800px) {{
        .kpi-tile {{ flex: 1 1 100%; min-width: 140px; }}
    }}
    </style>
    <div class="kpi-row">
    {tiles}
    </div>
    """
    tiles = ""
    for idx, (kpi_name, value_fmt) in enumerate(kpi_results):
        bg = colors[idx % len(colors)]
        tiles += f'<div class="kpi-tile" style="background:{bg}"><div class="kpi-label">{kpi_name}</div><div class="kpi-value">{value_fmt}</div></div>'
    st.markdown(tile_html.format(tiles=tiles, bg='{bg}'), unsafe_allow_html=True)

# Total Sales by Branch (Excluding Niko)
if 'Sale' in full_df.columns and not full_df.empty:
    sales_by_branch = full_df.groupby('Branch', as_index=False)['Sale'].sum()
    if not sales_by_branch.empty:
        fig_sales = px.bar(sales_by_branch, x='Branch', y='Sale', title="Total Sales by Branch (Excluding Niko)")
        st.plotly_chart(fig_sales, use_container_width=True)

# Monthly Profit Trend (Excluding Niko)
if 'Month' in full_df.columns and 'Profit' in full_df.columns and not full_df.empty:
    fig_profit = px.line(full_df, x='Month', y='Profit', color='Branch', title="Monthly Profit by Branch (Excluding Niko)")
    st.plotly_chart(fig_profit, use_container_width=True)

if not full_df.empty:
    st.info("Dashboard showing all branches except Niko")
