import streamlit as st
import pandas as pd
import plotly.express as px
import requests

st.set_page_config(layout="wide")
st.title("Welcome to Data Visualization Dashboard")

def calculate_velocity(total_actual, total_estimate):
    return total_actual / total_estimate if total_estimate != 0 else 0

# Fetch all sheets from the shared Google Sheet URL
def export_url(shared_url):
    doc_id = shared_url.split('/')[5]
    url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=xlsx"
    xls = pd.ExcelFile(url)
    return xls

# Function to load the selected sheet
def load_sheet(xls, sheet_name):
    df = pd.read_excel(xls, sheet_name=sheet_name)
    df.columns = map(str.lower, df.columns)  # Convert all column names to lowercase
    return df

# Get Google Sheet URL
shared_url = st.text_input("Enter the URL for the Google Sheet:")

# Check if a valid sheet is selected and prevent refresh
if 'selected_sheet' not in st.session_state:
    st.session_state.selected_sheet = None

# Load Google Sheet data and sheet names when URL is provided
if shared_url:
    try:
        xls = export_url(shared_url)
        sheet_names = xls.sheet_names  # List of all sheet names

        if sheet_names:
            # Allow the user to select a sheet from available sheets
            selected_sheet = st.selectbox("Select a sheet", sheet_names)

            # Update session state when the user selects a sheet
            if selected_sheet:
                st.session_state.selected_sheet = selected_sheet
        else:
            st.error("No sheets found in the Google Sheet.")

    except Exception as e:
        st.error(f"An error occurred while loading the Google Sheet: {e}")

# Show visualizations only when a sheet is selected
if st.session_state.selected_sheet and st.button("Visualize"):
    try:
        table = load_sheet(xls, st.session_state.selected_sheet)

        if not table.empty:
            # Ensure 'actual' and 'estimate' are numeric
            table['actual'] = pd.to_numeric(table['actual'], errors='coerce')
            table['estimate'] = pd.to_numeric(table['estimate'], errors='coerce')

            # Dev Time Difference
            table['dev time difference'] = table['actual'] - table['estimate']

            st.subheader("Sprint Health")
            col1, col2 = st.columns(2)

            with col1:
                total_estimate = table['estimate'].sum()
                total_actual = table['actual'].sum()
                velocity = calculate_velocity(total_actual, total_estimate)

                time_difference = total_estimate - total_actual
                hours = int(abs(time_difference))
                minutes = int((abs(time_difference) - hours) * 60)

                time_status = "**On Time**" if velocity == 0 else \
                              f"**Behind Schedule** by {hours}h {minutes}m" if velocity > 0 else \
                              f"**Ahead of Time** by {hours}h {minutes}m"

                st.write(f"Velocity: {velocity:.2f}")
                st.write(f"Sprint status: {time_status}")

                velocity_fig = px.bar(
                    x=['ESTIMATE', 'ACTUAL'],
                    y=[total_estimate, total_actual],
                    labels={'x': 'Type of Effort', 'y': 'Effort (hours)'},
                    title='Team Sprint Velocity',
                    text=[total_estimate, total_actual],
                )
                velocity_fig.update_layout(bargap=0.7)
                velocity_fig.update_traces(textposition='outside')
                velocity_fig.update_layout(showlegend=False, xaxis_title='', yaxis_title='Effort (hours)')
                st.plotly_chart(velocity_fig)

            with col2:
                table['risks'] = table['risks'].fillna('').str.lower()
                risk_counts = table['risks'].value_counts().reset_index()
                risk_counts.columns = ['Risk Type', 'Count']
                risk_counts['Risk Type'] = risk_counts['Risk Type'].replace({
                    'no risks': 'No Risk',
                    '': 'No Risk',
                    'nil': 'No Risk',
                    'not yet identified': 'Not Yet Identified'
                })

                color_map = {
                    'Not Yet Identified': 'yellow',
                    'No Risk': 'green',
                    'risk': 'red' 
                }

                risk_counts['Risk Type'] = risk_counts['Risk Type'].where(
                    risk_counts['Risk Type'].isin(['No Risk', 'Not Yet Identified']),
                    'risk'
                )

                fig = px.pie(
                    risk_counts, 
                    names='Risk Type',  
                    values='Count', 
                    title='Risk Distribution',
                    color='Risk Type', 
                    color_discrete_map=color_map, 
                    hole=0.4, 
                    height=500
                )
                fig.update_traces(
                    hovertemplate="<b>%{label}</b><br>Count: %{value}<extra></extra>" 
                )
                st.plotly_chart(fig)

            # Create a new DataFrame for plotting
            plot_data = table[['task_name', 'estimate', 'actual']].copy()
            plot_data['task_name'] = plot_data['task_name'].fillna('')  # Fill NaN with empty strings
            plot_data['task-name'] = plot_data['task_name'].str.slice(0, 5) + '...'

            # Replace NaN in 'actual' with 0 for plotting purposes
            plot_data['actual'] = plot_data['actual'].fillna(0)
            plot_data['estimate'] = plot_data['estimate'].fillna(0)

            # Create a new column to represent task status
            plot_data['Status'] = plot_data.apply(
                lambda row: 'Yet to Start' if row['estimate'] == 0 and row['actual'] == 0
                else 'In Progress' if row['actual'] == 0
                else 'Completed', axis=1
            )

            # Add a custom value for 'Actual' where it's missing to differentiate
            plot_data['Actual'] = plot_data.apply(
                lambda row: 0.01 if row['Status'] == 'In Progress' else row['actual'], axis=1
            )

            # Create the grouped bar chart with task progress (Estimate and Actual side by side)
            fig = px.bar(
                plot_data,
                x='task-name',
                y=['estimate', 'Actual'],
                barmode='group',
                title="Estimate vs Actual Task Time",
                labels={'value': 'Hours', 'variable': 'Type'},
                text_auto=True,
                height=600,
                hover_data={'task-name': False, 'task_name': True}
            )

            # Update the bar colors and labels
            fig.update_traces(marker=dict(color=['yellow', '#ff7f0e']), selector=dict(name='actual'))
            fig.for_each_trace(lambda trace: trace.update(textposition='outside'))

            # Show in-progress and yet to start as specific colors or labels
            for i in range(len(plot_data)):
                if plot_data['Status'].iloc[i] == 'In Progress':
                    fig.add_annotation(
                        x=plot_data['task-name'].iloc[i],
                        y=0.15, 
                        text="In Progress",
                        showarrow=False,
                        font=dict(color="yellow"),
                        align="center",
                        textangle=-90,  
                        yshift=50,
                        xshift=20,
                    )
                elif plot_data['Status'].iloc[i] == 'Yet to Start':
                    fig.add_annotation(
                        x=plot_data['task-name'].iloc[i],
                        y=0.15,  # Position the text slightly above the zero line
                        text="Yet to Start",
                        showarrow=False,
                        font=dict(color="orange"),
                        align="center",
                        textangle=-90, 
                        yshift=30,
                    )

            st.plotly_chart(fig)

            # Task/Module Time Visualization
            col3, col4 = st.columns(2)

            with col3:
                st.subheader("Task Time/Module Time")
                table['task-name'] = table['task_name'].str.slice(0, 5) + '...'

                task_time_fig = px.bar(table, x='task-name', y='estimate', title="Time per Task",
                                        hover_data={'task-name': False, 'task_name': True})
                st.plotly_chart(task_time_fig)

            with col4:
                st.subheader("Dev Time (Actual)")

                dev_time_fig = px.bar(
                    table,
                    x='task-name',
                    y='actual',
                    title="Dev Time",
                    hover_data={'task-name': False, 'task_name': True}
                )
                dev_time_fig.update_layout(xaxis_title='Task Name', yaxis_title='Dev Time (hours)')
                st.plotly_chart(dev_time_fig)

        else:
            st.error("The selected sheet is empty.")
    except Exception as e:
        st.error(f"An error occurred while visualizing the data: {e}")
