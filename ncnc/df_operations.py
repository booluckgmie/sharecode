import pandas as pd

def select_columns(df):
    print("Task 1: Selecting Columns")

    columns = ["Company_Name", "Employee_Rating"]
    df_filtered = df[columns]

    return df_filtered

def get_top_company(df):
    print("Task 2: Finding Top Company")

    grouped_rating = (
        df.groupby("Company_Name")["Employee_Rating"]
        .mean()
        .reset_index()
    )

    top_employer = grouped_rating.nlargest(n=1, columns=["Employee_Rating"])
    return top_employer

# def service_provider_perct(df):
#     print("Task 3: Calculating Service Provider Percentage")

#     total = len(df)
#     if total == 0:
#         return pd.DataFrame(columns=["SERVICE_PROVIDER", "PERCENTAGE"])

#     percentage = (
#         df["SERVICE_PROVIDER"]
#         .value_counts(normalize=True)
#         .mul(100)
#         .round(2)
#         .reset_index()
#     )

#     percentage.columns = ["SERVICE_PROVIDER", "PERCENTAGE"]
#     return percentage

import pandas as pd

def service_provider_perct(input_dataframe: pd.DataFrame) -> float:
    print("Task 3: Calculating Service Provider Percentage")
    if 'SERVICE_PROVIDER' in input_dataframe.columns:
        # Example calculation: assume 1 for service provider, 0 otherwise
        # You'll need to adjust this based on your actual data and definition of a service provider
        service_providers = input_dataframe[input_dataframe['Service_Provider'] == 1].shape[0]
        total_rows = input_dataframe.shape[0]
        if total_rows > 0:
            return (service_providers / total_rows) * 100
    return 0.0 # Return 0 if column not found or no service providers
