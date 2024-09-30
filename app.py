import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

import streamlit as st
import pandas as pd
import os


# Import the AI Assistant tab content
from ai_assistant import ai_assistant_tab

# Set the page configuration
st.set_page_config(page_title="Client Management Dashboard", layout="wide")

# Title of the dashboard
st.title("Client Management Data Dashboard")

# Load sensitive data from Streamlit secrets
openai_api_key = st.secrets["OPENAI_API_KEY"]
openai_assistant_id = st.secrets["OPENAI_ASSISTANT_ID"]
sheet_url = st.secrets["SHEET_URL"]

# Function to load data from Google Sheets
@st.cache_data(ttl=3600)  # Cache data for 1 hour
def load_data(url):
    try:
        df = pd.read_csv(url)
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

# Load data from the Google Sheet
if sheet_url:
    df = load_data(sheet_url)
else:
    st.error("Please provide the Google Sheet URL in the Streamlit secrets.")


if df is not None:
    # Convert 'trial_date' to datetime
    df['trial_date'] = pd.to_datetime(df['trial_date'], errors='coerce')

    # Handle missing values in marketplace columns
    marketplaces = ['amazon', 'ebay', 'shopify', 'other_marketplace', 'other_webstore']
    df[marketplaces] = df[marketplaces].fillna(0).astype(float)

    # Sidebar filters
    st.sidebar.header("Filter Data")
    countries = st.sidebar.multiselect(
        "Select Countries",
        options=df['country'].dropna().unique(),
        default=df['country'].dropna().unique()
    )

    # Filter the data based on selections
    df_filtered = df[df['country'].isin(countries)]

    # Create tabs (insert 'AI Assistant' in the second position)
    tabs = st.tabs([
        "Overview",
        "AI Assistant",
        "Client Segmentation",
        "Activity and Usage",
        "Cohort Retention Analysis"
    ])

    # --- Overview Tab ---
    with tabs[0]:
        st.header("Key Metrics (KPIs)")
        col1, col2, col3, col4 = st.columns(4)

        # Total Clients
        total_clients = df_filtered['client_id'].nunique()
        col1.metric("Total Clients", total_clients)

        # Active vs Inactive Clients
        active_clients = df_filtered[df_filtered['active'] == 1]['client_id'].nunique()
        inactive_clients = total_clients - active_clients
        col2.metric("Active Clients", active_clients)
        col2.metric("Inactive Clients", inactive_clients)

        # Conversion Rate (Trial to Paid)
        converted_clients = df_filtered[(df_filtered['trial_date'].notna()) & (df_filtered['paid'] == 1)]['client_id'].nunique()
        trial_clients = df_filtered[df_filtered['trial_date'].notna()]['client_id'].nunique()
        if trial_clients > 0:
            conversion_rate = (converted_clients / trial_clients) * 100
        else:
            conversion_rate = 0
        col3.metric("Conversion Rate", f"{conversion_rate:.2f}%")

        # Marketplace Connections
        marketplace_connections = df_filtered[marketplaces].gt(0).any(axis=1).sum()
        marketplace_percentage = (marketplace_connections / total_clients) * 100 if total_clients > 0 else 0
        col4.metric("Marketplace Connections", f"{marketplace_percentage:.2f}%")

        # Time-Based Trends
        st.header("Time-Based Trends")

        # Trial Signup Trend Over Time
        st.subheader("Trial Signup Trend Over Time")
        trial_trend = df_filtered[df_filtered['trial_date'].notna()].copy()
        trial_trend['trial_month'] = trial_trend['trial_date'].dt.to_period('M').dt.to_timestamp()
        trial_counts = trial_trend.groupby('trial_month')['client_id'].nunique().reset_index()
        fig_trial_trend = px.line(
            trial_counts,
            x='trial_month',
            y='client_id',
            title='New Trial Signups Over Time',
            markers=True
        )
        fig_trial_trend.update_layout(xaxis_title='Month', yaxis_title='Number of Signups')
        st.plotly_chart(fig_trial_trend, use_container_width=True)

        # Conversion Rate Over Time
        st.subheader("Conversion Rate Over Time")
        conversion_data = trial_trend.copy()
        conversion_data['converted'] = conversion_data['paid']
        conversion_rate_over_time = conversion_data.groupby('trial_month').agg(
            trial_clients=('client_id', 'nunique'),
            converted_clients=('converted', 'sum')
        ).reset_index()
        conversion_rate_over_time['conversion_rate'] = (
            conversion_rate_over_time['converted_clients'] / conversion_rate_over_time['trial_clients']
        ) * 100
        fig_conversion_rate = px.line(
            conversion_rate_over_time,
            x='trial_month',
            y='conversion_rate',
            title='Conversion Rate Over Time',
            markers=True
        )
        fig_conversion_rate.update_layout(xaxis_title='Month', yaxis_title='Conversion Rate (%)')
        st.plotly_chart(fig_conversion_rate, use_container_width=True)

    # --- AI Assistant Tab ---
    with tabs[1]:
        # Call the function from ai_assistant.py
        ai_assistant_tab(df_filtered)

    # --- Client Segmentation Tab ---
    with tabs[2]:
        st.header("Client Segmentation")

        # Country Distribution
        st.subheader("Country Distribution")
        country_distribution = df_filtered['country'].value_counts().reset_index()
        country_distribution.columns = ['Country', 'Number of Clients']
        fig_country = px.pie(
            country_distribution,
            values='Number of Clients',
            names='Country',
            title='Clients by Country',
            color_discrete_sequence=px.colors.sequential.RdBu
        )
        st.plotly_chart(fig_country, use_container_width=True)

        # Signup Source Analysis
        st.subheader("Signup Source Analysis")
        if 'click_source' in df_filtered.columns:
            click_source_counts = df_filtered['click_source'].value_counts().reset_index()
            click_source_counts.columns = ['Click Source', 'Number of Clients']
            fig_click_source = px.pie(
                click_source_counts,
                values='Number of Clients',
                names='Click Source',
                title='Clients by Signup Source',
                color_discrete_sequence=px.colors.sequential.Viridis
            )
            st.plotly_chart(fig_click_source, use_container_width=True)
        else:
            st.write("The 'click_source' column is not available in the data.")

    # --- Activity and Usage Tab ---
    with tabs[3]:
        st.header("Activity and Usage")

        # Client Activation Rates by Marketplace
        st.subheader("Client Activation Rates by Marketplace")
        activation_data = df_filtered.copy()
        activation_data['active_status'] = activation_data['active'].map({1: 'Active', 0: 'Inactive'})
        marketplace_activation = activation_data.groupby('active_status')[marketplaces].sum().reset_index()
        marketplace_activation = pd.melt(
            marketplace_activation,
            id_vars='active_status',
            var_name='Marketplace',
            value_name='Connections'
        )
        fig_activation = px.bar(
            marketplace_activation,
            x='Marketplace',
            y='Connections',
            color='active_status',
            barmode='group',
            title='Activation Rates by Marketplace'
        )
        st.plotly_chart(fig_activation, use_container_width=True)

        # Mobile vs. Desktop Signup
        st.subheader("Mobile vs. Desktop Signup")
        signup_method_counts = df_filtered['mobile_signup'].value_counts().reset_index()
        signup_method_counts.columns = ['mobile_signup', 'count']
        signup_method_counts['Signup Method'] = signup_method_counts['mobile_signup'].map({1: 'Mobile', 0: 'Desktop'})
        fig_signup_method = px.pie(
            signup_method_counts,
            values='count',
            names='Signup Method',
            title='Mobile vs. Desktop Signup',
            color_discrete_sequence=px.colors.sequential.Teal
        )
        st.plotly_chart(fig_signup_method, use_container_width=True)

        # Top Performing Marketplaces
        st.subheader("Top Performing Marketplaces")
        marketplace_totals = df_filtered[marketplaces].sum().reset_index()
        marketplace_totals.columns = ['Marketplace', 'Total Connections']
        fig_marketplace = px.bar(
            marketplace_totals,
            x='Marketplace',
            y='Total Connections',
            title='Total Marketplace Connections',
            color='Total Connections',
            color_continuous_scale='Blues'
        )
        fig_marketplace.update_layout(xaxis_title='Marketplace', yaxis_title='Total Connections')
        st.plotly_chart(fig_marketplace, use_container_width=True)


    # --- Cohort Retention Analysis Tab ---
    with tabs[4]:
        st.header("Cohort Retention Analysis")

        # Convert 'trial_date' to datetime and group by cohort month
        df_filtered['trial_month'] = df_filtered['trial_date'].dt.to_period('M')
        cohort_data = df_filtered.groupby('trial_month').agg(
            total_users=('client_id', 'size'),
            connected=('connected', 'sum'),
            active=('active', 'sum'),
            paid=('paid', 'sum')
        ).reset_index()

        cohort_data['connected_rate'] = cohort_data['connected'] / cohort_data['total_users'] * 100
        cohort_data['active_rate'] = cohort_data['active'] / cohort_data['total_users'] * 100
        cohort_data['paid_rate'] = cohort_data['paid'] / cohort_data['total_users'] * 100

        fig_cohort_retention = go.Figure()
        fig_cohort_retention.add_trace(go.Scatter(x=cohort_data['trial_month'].astype(str),
                                                y=cohort_data['connected_rate'], mode='lines+markers', name='Connected Rate'))
        fig_cohort_retention.add_trace(go.Scatter(x=cohort_data['trial_month'].astype(str),
                                                y=cohort_data['active_rate'], mode='lines+markers', name='Active Rate'))
        fig_cohort_retention.add_trace(go.Scatter(x=cohort_data['trial_month'].astype(str),
                                                y=cohort_data['paid_rate'], mode='lines+markers', name='Paid Rate'))

        fig_cohort_retention.update_layout(
            title="Cohort Retention Analysis",
            xaxis_title="Cohort Month",
            yaxis_title="Retention Rate (%)",
            legend_title="Retention Stage"
        )

        # Display the plot
        st.plotly_chart(fig_cohort_retention, use_container_width=True)

else:
    st.write("Please upload a CSV file to begin.")
