import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

st.set_page_config(layout="wide")
st.title("Welcome to Data Visualization Dashboard")

USERNAME = os.getenv("USERNAME")
TOKEN = os.getenv("TOKEN")
BASE_URL = "https://api.github.com"

@st.cache_data
def fetch_pull_requests(repo_name):
    url = f"{BASE_URL}/repos/{USERNAME}/{repo_name}/pulls?state=all"
    prs = []
    while url:
        response = requests.get(url, auth=(USERNAME, TOKEN))
        prs += response.json()
        url = response.links.get('next', {}).get('url')
    return prs

@st.cache_data
def fetch_pr_comments(repo_name, pr_number):
    url = f"{BASE_URL}/repos/{USERNAME}/{repo_name}/issues/{pr_number}/comments"
    comments = []
    while url:
        response = requests.get(url, auth=(USERNAME, TOKEN))
        comments += response.json()
        url = response.links.get('next', {}).get('url')
    return comments

@st.cache_data
def get_repo_data(repo_name):
    repo_data = []
    prs = fetch_pull_requests(repo_name)
    for pr in prs:
        comments = fetch_pr_comments(repo_name, pr['number'])
        first_comment_created_at = comments[0]['created_at'] if comments else None
        repo_data.append({
            'PR Number': pr['number'],
            'PR Title': pr['title'],
            'PR State': pr['state'],  # This will help create the PR status
            'Created At': pr['created_at'],
            'Updated At': pr['updated_at'],
            'Merged At': pr['merged_at'],
            'First Comment At': first_comment_created_at,
        })

    df = pd.DataFrame(repo_data)
    return df

def get_repo_name_from_url(repo_url):
    return repo_url.split('/')[-1]

def calculate_velocity(total_actual, total_estimate):
    return total_actual / total_estimate if total_estimate != 0 else 0

def calculate_pr_status(pr_duration, expected_time):
    return "Bad PR merged" if pr_duration > expected_time else "Good PR merged"

def export_url(shared_url):
    doc_id = shared_url.split('/')[5]
    url = f"https://docs.google.com/spreadsheets/d/{doc_id}/export?format=xlsx"
    xls = pd.ExcelFile(url)
    table = pd.read_excel(xls)
    return table

repo_url = st.text_input("Enter the GitHub repository URL or the repository name:")
shared_url = st.text_input("Enter the URL for the Google Sheet:")

if st.button("Visualize"):
    if repo_url and shared_url:
        try:
            repo_name = get_repo_name_from_url(repo_url) if "github.com" in repo_url else repo_url
            repo_df = get_repo_data(repo_name)
            table = export_url(shared_url)

            if not table.empty:
                # Dev Time Difference
                table['Dev Time Difference'] = table['ACTUAL'] - table['ESTIMATE']

                # PR Data Mapping
                table['PR Title'] = repo_df['PR Title']
                table['PR Opened Date'] = pd.to_datetime(repo_df['Created At'], utc=True).dt.tz_convert(None)
                table['PR Merged Date'] = pd.to_datetime(repo_df['Merged At'], utc=True).dt.tz_convert(None)
                table['First Comment At'] = pd.to_datetime(repo_df['First Comment At'], utc=True).dt.tz_convert(None)
                table['PR Duration'] = (table['PR Merged Date'] - table['PR Opened Date']).dt.total_seconds() / 3600
                table['PR Comments Resolved Duration'] = (table['PR Merged Date'] - table['First Comment At']).dt.total_seconds() / 3600
                table['Total PR Comments'] = repo_df.apply(lambda row: len(fetch_pr_comments(repo_name, row['PR Number'])), axis=1)
                
                pr_with_most_comments = table.loc[table['Total PR Comments'].idxmax()]
                
                pr_title_with_most_comments = pr_with_most_comments['PR Title']
                
                total_comments_in_pr = pr_with_most_comments['Total PR Comments']

                pr_duration_resolving_comments = pr_with_most_comments['PR Comments Resolved Duration']
                
                # average time to resolve one comment
                if total_comments_in_pr > 0:
                    avg_time_per_comment = (pr_duration_resolving_comments / total_comments_in_pr)  # 0.30 is adding extra for factor of safety 
                else:
                    avg_time_per_comment = 0 
                    
                table['Expected Time to Resolve Comments'] = (table['Total PR Comments'] * avg_time_per_comment) +0.30  # 30 min is adding extra for factor of safety

                # Add the correct PR STATUS column
                table['PR STATUS'] = repo_df['PR State'].replace({
                    'open': 'Open PR',
                    'closed': 'Closed PR',
                    'merged': 'Merged PR'
                })


                col1,col2= st.columns(2)

                with col1:
                    # Sprint Health
                    st.subheader("Sprint Health")
                    #velocity_table = table.dropna(subset=['ACTUAL'])
                    total_estimate = table['ESTIMATE'].sum()
                    total_actual = table['ACTUAL'].sum()
                    velocity = calculate_velocity(total_actual, total_estimate)

                    time_difference = total_estimate - total_actual
                    hours = int(abs(time_difference))
                    minutes = int((abs(time_difference) - hours) * 60)

                    time_status = "**On Time**" if time_difference == 0 else \
                                f"**Behind Schedule** by {hours}h {minutes}m" if time_difference > 0 else \
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
                    # Risks
                    table['RISKS'] = table['RISKS'].str.lower()
                    risk_counts = table['RISKS'].value_counts().reset_index()
                    risk_counts.columns = ['Risk Type', 'Count']

                    color_map = {
                    'risk': 'red',      
                    'no risks': 'green',  
                    'not yet identified': 'yellow'    
                    }

                    fig = px.pie(risk_counts, names='Risk Type', values='Count', title='Risk Distribution', color_discrete_map=color_map,hole=0.4)
                    fig.update_traces(marker=dict(colors=['green', 'red', 'yellow']))
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


                

                col3,col4= st.columns(2)
                
                with col3:
                    # Task Time/Module Time
                    st.subheader("Task Time/Module Time")
                    table['TASK-NAME'] = table['TASK_NAME'].str.slice(0, 5) + '...'
                    
                    task_time_fig = px.bar(table, x='TASK-NAME', y='ESTIMATE', title="Time per Task", hover_data={'TASK-NAME': False,'TASK_NAME': True} )
                    st.plotly_chart(task_time_fig)

                with col4:
                    # Dev Time
                    st.subheader("Dev Time (Actual)")
                
                    dev_time_fig = px.bar(
                        table,
                        x='TASK-NAME',
                        y='ACTUAL',
                        title="Dev Time",
                        hover_data={'TASK-NAME': False,'TASK_NAME': True}
                    )
                    #dev_time_fig.update_traces(marker_color='yellow')
                    dev_time_fig.update_layout(xaxis_title='Task Name', yaxis_title='Dev Time (hours)')
                    st.plotly_chart(dev_time_fig)

                


                st.subheader("PR Efficiency")
                col5,col6= st.columns(2)
                # PR and PR Comments
                with col5:
                    pr_efficiency_fig = px.bar(table, x='PR Title', y='PR Duration', title="PR Duration", color='PR STATUS')
                    pr_efficiency_fig.update_layout(bargap=0.5)
                    st.plotly_chart(pr_efficiency_fig)


                with col6:
                    pr_comments_fig = px.bar(
                            table,
                            x='PR Title',
                            y=['PR Comments Resolved Duration', 'Expected Time to Resolve Comments'],
                            barmode='group',
                            title="PR Comments Resolved Duration"
                        )
                    pr_comments_fig.update_layout(bargap=0.3)
                    pr_comments_fig.update_layout(xaxis_title='PR Title', yaxis_title='Resolution Time (hours)')
                    st.plotly_chart(pr_comments_fig)
                    
                    
                    
                    
                    
                    
                    
                    
                    
                




        except Exception as e:
            st.error(f"An error occurred: {e}")
    else:
        st.warning("Please enter both the GitHub repository URL and Google Sheet URL.")
