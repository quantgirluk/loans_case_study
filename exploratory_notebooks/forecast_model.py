import datetime

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from abc import ABC
import logging

import warnings

warnings.filterwarnings("ignore")


class Loan:
    def __init__(self, loan_data):
        self.loans_data = loan_data
        self.months_post_reversion = loan_data['Months_Post_Reversion']
        self.seasoning = loan_data['Seasoning']
        self.current_balance = loan_data['current_balance']
        self.fixed_pre_reversion = loan_data['Fixed Pre-Reversion Rate']
        self.post_reversion = loan_data['Post Reversion Margin']
        self.months_to_maturity = loan_data['Months to Maturity']
        self.repayment_method = loan_data['repayment_method']


class Model_Inputs:
    def __init__(self, model_inputs):
        self.model_inputs = model_inputs
        self.CDR = model_inputs['CDR']
        self.CPR = model_inputs['CPR']
        self.months_for_reversion = model_inputs['months_for_reversion']
        self.boe_rates_forecast = model_inputs['boe_rates_forecast']


class ForecastModel(ABC):

    def __init__(self, inputs):
        self.model_inputs = inputs
        self.CDR = inputs.CDR
        self.CPR = inputs.CPR
        self.months_for_reversion = inputs.months_for_reversion
        self.boe_rates_forecast = inputs.boe_rates_forecast
        self.forecast_length = len(self.boe_rates_forecast)

    def forecast(self, loan):

        N = self.forecast_length
        opening_balance = np.zeros(N)
        interest_rate = np.zeros(N)
        remaining_term = np.zeros(N)
        time_past_reversion = np.zeros(N)
        scheduled_interest = np.zeros(N)
        scheduled_payment = np.zeros(N)
        scheduled_principal = np.zeros(N)
        closing_balance = np.zeros(N)

        EOP = np.zeros(N)
        Defaults = np.zeros(N)
        ExpBPPD = np.zeros(N)
        ExpBPPP = np.zeros(N)
        EP = np.zeros(N)
        ECPB = np.zeros(N)

        for i in range(N):
            if i == 0:
                opening_balance[i] = loan.current_balance
                EOP[i] = loan.current_balance
            else:
                opening_balance[i] = closing_balance[i - 1]
                EOP[i] = ECPB[i - 1]

            remaining_term[i] = np.max(loan.months_to_maturity - 1, 0)
            time_past_reversion[i] = loan.months_post_reversion
            if time_past_reversion[i] > 0:
                interest_rate[i] = self.boe_rates_forecast[i] + loan.post_reversion
            else:
                interest_rate[i] = loan.fixed_pre_reversion

            scheduled_interest[i] = opening_balance[i] * (interest_rate[i] / 12)
            scheduled_payment[i] = scheduled_interest[i]
            closing_balance[i] = opening_balance[i] - scheduled_principal[i]

            Defaults[i] = (1. - (1. - self.CDR[i]) ** (1 / 12)) * EOP[i]
            ExpBPPD[i] = EOP[i] - Defaults[i]
            ExpBPPP[i] = ExpBPPD[i] - 0.  # Only interest for now
            EP[i] = (1. - (1. - self.CPR[i]) ** (1 / 12)) * ExpBPPP[i]
            ECPB[i] = ExpBPPP[i] - EP[i]

        forecas_table = pd.DataFrame({'Expected_Opening_Perfornace': EOP,
                                      'Expected Closing Default Balance': ECPB,
                                      'Defaults': Defaults,
                                      'Expected Balance Post Period Defaults': ExpBPPP,
                                      'Expected Balance Pre Period Prepays': ExpBPPP,
                                      'Expected Prepayments': EP
                                      })

        return forecas_table


def main():
    from portfolio_model import Loans_Portfolio
    cob = datetime.date(2022, 12, 31)  # 31/12/2022
    ss_path = '../data/2024_Strat_Casestudy.xlsx'

    portfolio = Loans_Portfolio(cob_date=cob, data_path=ss_path)

    CPR = portfolio.construct_portfolio_cpr(index='time_to_reversion')
    CDR = portfolio.construct_portfolio_cdr(index='time_to_reversion')
    n = len(CDR)

    model_inputs = Model_Inputs({
        'CPR': CPR.cpr.reset_index(drop=True),
        'CDR': CDR.cdr.reset_index(drop=True),
        'months_for_reversion': CPR.index,
        'boe_rates_forecast': np.full(n, 0.02) # fixed for now

    })

    loan_data = Loan({
        'Months_Post_Reversion': -22,
        'Seasoning': 2,
        'current_balance': 100000,
        'Fixed Pre-Reversion Rate': 0.0394,
        'Post Reversion Margin': 0.0494,
        'Months to Maturity': 178,
        'repayment_method': 'Interest Only'
    })

    model = ForecastModel(model_inputs)
    df = model.forecast(loan_data)

    print('End')


if __name__ == '__main__':
    main()
