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
    return pd.read_excel(xls, sheet_name=sheet_name)


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
            # Dev Time Difference
            table['Dev Time Difference'] = table['ACTUAL'] - table['ESTIMATE']

            st.subheader("Sprint Health")
            col1, col2 = st.columns(2)

            with col1:
                total_estimate = table['ESTIMATE'].sum()
                total_actual = table['ACTUAL'].sum()
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
                    color=['ESTIMATE', 'ACTUAL'],
                )
                velocity_fig.update_layout(bargap=0.7)
                velocity_fig.update_traces(textposition='outside')
                velocity_fig.update_layout(showlegend=False, xaxis_title='', yaxis_title='Effort (hours)')
                st.plotly_chart(velocity_fig)

            with col2:
                # Convert RISKS to lowercase
                table['RISKS'] = table['RISKS'].str.lower()

                # Shorten the risks for display (e.g., take the first 5 characters and append "...")
                table['Risk Short'] = table['RISKS'].apply(lambda x: x[:5] + '...' if len(x) > 5 else x)

                # Count the number of occurrences of each risk type
                risk_counts = table['RISKS'].value_counts().reset_index()
                risk_counts.columns = ['Risk Type', 'Count']

                # Add shortened risk names for hover display
                risk_counts['Risk Short'] = risk_counts['Risk Type'].apply(lambda x: x[:15] + '...' if len(x) > 5 else x)

                # Color map for different risk types
                color_map = {
                    'risk': 'red',
                    'no risks': 'green',
                    'not yet identified': 'yellow'
                }

                # Create the pie chart using shortened names for display and full names on hover
                fig = px.pie(
                    risk_counts, 
                    names='Risk Short',  # Use shortened names for display
                    values='Count', 
                    title='Risk Distribution',
                    color_discrete_map=color_map, 
                    hole=0.4, 
                    height=500
                )
                
                fig.update_traces(
                                customdata=risk_counts[['Risk Type']],  # Pass the full risk type as customdata
                                hovertemplate="<b>%{customdata[0]}</b><br>Count: %{value}<extra></extra>"  # Display full risk type on hover
                                )

                # Update the pie chart colors (optional customization for known risks)
                fig.update_traces(marker=dict(colors=['red', 'green', 'yellow']))

                # Display the pie chart
                st.plotly_chart(fig)

                
            # Create a new DataFrame for plotting
                plot_data = table[['TASK_NAME', 'ESTIMATE', 'ACTUAL']].copy()
                plot_data['TASK-NAME'] = plot_data['TASK_NAME'].str.slice(0, 5) + '...'
                

                # Replace NaN in ACTUAL with 0 for plotting purposes (this will leave room for showing "In Progress")
                plot_data['ACTUAL'] = plot_data['ACTUAL'].fillna(0)
                plot_data['ESTIMATE'] = plot_data['ESTIMATE'].fillna(0)

                # Create a new column to represent task status when actual and estimate are missing
                plot_data['Status'] = plot_data.apply(
                    lambda row: 'Yet to Start' if row['ESTIMATE'] == 0 and row['ACTUAL'] == 0
                    else 'In Progress' if row['ACTUAL'] == 0
                    else 'Completed', axis=1
                )

                # Add a custom value for 'Actual' where it's missing to differentiate
                plot_data['Actual'] = plot_data.apply(
                    lambda row: 0.01 if row['Status'] == 'In Progress' else row['ACTUAL'], axis=1
                )

                # Create the grouped bar chart with task progress (Estimate and Actual side by side)
                fig = px.bar(
                    plot_data,
                    x='TASK-NAME',
                    y=['ESTIMATE', 'Actual'],
                    barmode='group',
                    title="Estimate vs Actual Task Time",
                    labels={'value': 'Hours', 'variable': 'Type'},
                    text_auto=True,
                    height=600,
                    hover_data={'TASK-NAME': False,'TASK_NAME': True}
                )

                # Update the bar colors and labels
                fig.update_traces(marker=dict(color=['yellow', '#ff7f0e']), selector=dict(name='ACTUAL'))
                fig.for_each_trace(lambda trace: trace.update(textposition='outside'))

                # Show in-progress as a specific color or label
                for i in range(len(plot_data)):
                    if plot_data['Status'].iloc[i] == 'In Progress':
                        fig.add_annotation(
                            x=plot_data['TASK-NAME'].iloc[i],
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
                            x=plot_data['TASK-NAME'].iloc[i],
                            y=0.15,  # Position the text slightly above the zero line
                            text="Yet to Start",
                            showarrow=False,
                            font=dict(color="orange"),
                            align="center",
                            textangle=-90, 
                            yshift=30 ,
                            
                        )

            st.plotly_chart(fig)

            # Task/Module Time Visualization
            col3, col4 = st.columns(2)

            with col3:
                st.subheader("Task Time/Module Time")
                table['TASK-NAME'] = table['TASK_NAME'].str.slice(0, 5) + '...'

                task_time_fig = px.bar(table, x='TASK-NAME', y='ESTIMATE', title="Time per Task",
                                       hover_data={'TASK-NAME': False, 'TASK_NAME': True})
                st.plotly_chart(task_time_fig)

            with col4:
                st.subheader("Dev Time (Actual)")

                dev_time_fig = px.bar(
                    table,
                    x='TASK-NAME',
                    y='ACTUAL',
                    title="Dev Time",
                    hover_data={'TASK-NAME': False, 'TASK_NAME': True}
                )
                dev_time_fig.update_layout(xaxis_title='Task Name', yaxis_title='Dev Time (hours)')
                st.plotly_chart(dev_time_fig)

        else:
            st.error("The selected sheet is empty.")

    except Exception as e:
        st.error(f"An error occurred while visualizing the data: {e}")
