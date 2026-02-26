import re
import pandas as pd
import os

def parse_markdown_tables(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    sections = {}
    current_section = "General"
    current_subsection = ""
    
    # Mappings for section titles to sheet names
    sheet_mapping = {
        "1. KPI 问法": "KPI_Recognition",
        "2. 时间描述": "Time_Range",
        "3. 范围描述": "Scope_Parsing",
        "4. 组合场景": "Combination",
        "5. 多轮对话": "Multi_Turn",
        "6. 边界与反例": "Negative_Tests",
        "7. 补充场景": "Robustness"
    }

    # Buffer for table rows
    table_lines = []
    
    for line in lines:
        line = line.strip()
        
        # Detect Section (## )
        if line.startswith("## "):
            # Process previous table if exists
            if table_lines:
                process_table(table_lines, current_section, current_subsection, sections)
                table_lines = []
            
            # Set new section
            raw_title = line[3:].strip()
            # Find matching key in mapping
            matched_key = next((k for k in sheet_mapping if raw_title.startswith(k)), None)
            
            # Update section name based on mapping or fallback
            if matched_key:
                current_section = sheet_mapping[matched_key]
            else:
                # Sanitize title for sheet name (max 31 chars, no invalid chars)
                clean_title = re.sub(r'[\\/*?:\[\]]', '_', raw_title)
                current_section = clean_title[:30]
            
            current_subsection = ""
            
        # Detect Subsection (### )
        elif line.startswith("### "):
            # Process previous table if exists
            if table_lines:
                process_table(table_lines, current_section, current_subsection, sections)
                table_lines = []
            current_subsection = line[4:].strip()

        # Detect Table Row (starts with |)
        elif line.startswith("|"):
            table_lines.append(line)
        
        # Empty line or text - end of table
        else:
            if table_lines:
                process_table(table_lines, current_section, current_subsection, sections)
                table_lines = []

    # Process last table
    if table_lines:
        process_table(table_lines, current_section, current_subsection, sections)

    return sections

def process_table(lines, section, subsection, sections_dict):
    if len(lines) < 2:
        return

    # Extract headers
    # Strip whitespace, then strip outer pipes, then split
    header_line = lines[0].strip().strip("|")
    headers = [h.strip() for h in header_line.split("|")]
    
    # Skip separator line (lines[1]) if it contains '---'
    start_data_idx = 1
    if len(lines) > 1 and "---" in lines[1]:
        start_data_idx = 2
        
    data = []
    for row_line in lines[start_data_idx:]:
        content = row_line.strip().strip("|")
        # Split by pipe
        cells = [c.strip() for c in content.split("|")]
        
        # Create row dictionary
        row_data = {}
        for i, header in enumerate(headers):
            if i < len(cells):
                row_data[header] = cells[i]
            else:
                row_data[header] = "" # Handle missing cells
        
        # Add subsection info if available
        if subsection:
            row_data["Subsection"] = subsection
            
        data.append(row_data)

    if not data:
        return

    df = pd.DataFrame(data)
    
    if section not in sections_dict:
        sections_dict[section] = []
    sections_dict[section].append(df)

def main():
    md_path = "/Users/sophia/projects/aiproject/open-webui/docs/kpi-bot-su-hour-per-tool-testcases.md"
    xlsx_path = "/Users/sophia/projects/aiproject/open-webui/docs/kpi-bot-su-hour-per-tool-testcases.xlsx"
    
    print(f"Reading from {md_path}...")
    sections = parse_markdown_tables(md_path)
    
    if not sections:
        print("No tables found in markdown file.")
        return

    print(f"Found {len(sections)} sections with tables: {list(sections.keys())}")

    try:
        with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
            for section_name, dfs in sections.items():
                # Concatenate all dfs for this section
                full_df = pd.concat(dfs, ignore_index=True)
                
                # Fill NaNs with empty strings (important for merged schemas)
                full_df = full_df.fillna("")
                
                # Reorder columns: put ID first, Subsection second
                cols = full_df.columns.tolist()
                
                # Helper to move col to index
                def move_col(c, idx):
                    if c in cols:
                        cols.remove(c)
                        cols.insert(idx, c)
                
                # Move ID to 0
                move_col("ID", 0)
                # Move Subsection to 1
                move_col("Subsection", 1)
                # Move "User Input" or similar to 2 (optional, but good for readability)
                # User Input might be named "用户输入" or "第 1 轮用户输入"
                if "用户输入" in cols:
                    move_col("用户输入", 2)
                
                full_df = full_df[cols]
                
                full_df.to_excel(writer, sheet_name=section_name, index=False)
                print(f"Sheet '{section_name}' written with {len(full_df)} rows.")

        print(f"Successfully converted to {xlsx_path}")
        
    except Exception as e:
        print(f"Error writing Excel file: {e}")

if __name__ == "__main__":
    main()
