import pandas as pd
import numpy as np


def consolidate_data(ss_name='../data/2024_Strat_Casestudy.xlsx', loan_id=None):
    
    static = pd.read_excel(ss_name, sheet_name='DATA-Static', skiprows=2, usecols="B:I",)
    
    historic_balances = pd.read_excel(ss_name, sheet_name='DATA-Month End Balances', index_col=0)
    balances = historic_balances.stack().reset_index(name='Balance').set_index(['loan_id', 'level_1'])
    
    historic_due = pd.read_excel(ss_name, sheet_name='DATA-Payment Due', index_col=0)
    historic_due.index.rename('loan_id', inplace=True)
    due_payments = historic_due.stack().reset_index(
    name='Payment_Due').set_index(['loan_id', 'level_1'])
    
    historic_made = pd.read_excel(ss_name,
                    sheet_name='DATA-Payment Made', index_col=0)
    made_payments = historic_made.stack().reset_index(
    name='Payment_Made').set_index(['loan_id', 'level_1'])
    
    all_historic_data = pd.concat([balances, due_payments, made_payments], axis=1).reset_index()
    data = all_historic_data.merge(static, left_on=['loan_id'], right_on='loan_id')
    
    if loan_id:
        
        data = data[data.loan_id == loan_id]
    
    return data


def extendend_data_single_loan(data):
    
    df = data.copy()
    
    df['Payment_Made'] = df['Payment_Made'].fillna(0)
    df['payment_made_cumsum'] = df['Payment_Made'].cumsum()
    df['current_balance'] = df['original_balance'] - df['payment_made_cumsum']
    df['seasoning'] = df['level_1'].dt.to_period('M').astype(int) - df['origination_date'].dt.to_period('M').astype(int)
    df['missed_payment'] = df['Payment_Due'] > df['Payment_Made']
    df['not_missed'] = ~df['missed_payment']
    df['n_missed_payments'] = df['missed_payment'].groupby((~df['missed_payment']).cumsum()).cumsum()
    df['prepaid_in_month'] = (df['Payment_Due'] < df['Payment_Made']) & (df['Balance'] == 0)
    df['default_in_month'] = (df.n_missed_payments == 3)
    df['defaulted'] = df.default_in_month.cumsum() 
    df['not_defaulted'] = ~df['defaulted']
    df['recovery_in_month'] = (df.defaulted==True) & (df.Payment_Made >0)
    df['time_to_reversion'] = df['level_1'].dt.to_period('M').astype(int) - df['reversion_date'].dt.to_period('M').astype(int)
    df['is_post_seller_purchsae_date'] = (df['level_1'] > df['investor_1_acquisition_date'])
    
    
    postdefault_recoveries = sum(df['defaulted']*df['Payment_Made'])
    df['postdefault_recoveries'] = postdefault_recoveries
    
    if df.prepaid_in_month.any():   
        prepayment_date = df[df.prepaid_in_month == True]['level_1'].iloc[0]
    else:
        prepayment_date = np.nan
    df['prepayment_date']=prepayment_date  
    
    # df['prepayment_date_nan'] = np.isnat(df.prepayment_date)
    
    # df['before_prepaid'] = (df['level_1'] < df['prepayment_date'])
        
    if df.default_in_month.any():
        date_of_default = df[df.default_in_month == True]['level_1'].item()
    else:
        date_of_default = np.nan
    df['date_of_default'] = date_of_default
    # df['before_default'] = (df['level_1'] < df['date_of_default'])
    
    if df.default_in_month.any():
        exposure_at_default = df[df.default_in_month == True]['current_balance'].item()
    else: 
        exposure_at_default = np.nan
    df['exposure_at_default'] = exposure_at_default
        
    
    if postdefault_recoveries and exposure_at_default: 
        recovery_percent = postdefault_recoveries/exposure_at_default
    else:
        recovery_percent = np.nan
    df['recovery_percent'] = recovery_percent
    
    
    return df



def create_extended_data_portfolio(debug=False, n_loans=5):
    
    data = consolidate_data()
    ids = data['loan_id'].unique()
    
    if debug:
        ids = ids[:n_loans]
    
    extended_subdatas = []
    
    for idx in ids:
        
        subdata = data[data['loan_id'] == idx]
        extended = extendend_data_single_loan(subdata)
        extended_subdatas.append(extended)
        
    extended_data = pd.concat(extended_subdatas)
    
    return extended_data